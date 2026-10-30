"""SinapisAI Qwen vision policy. No GPU, reference data or network fallbacks."""
import base64
import hashlib
import io
import json
import os
import re
import time
import threading
from pathlib import Path
from .policy import BasePolicy
from .protocol import load_json, validate

SYSTEM_PROMPT = '''You are an open-loop robot navigation policy. Given ONLY an initial
egocentric RGB image and a navigation instruction, predict the complete route
until the instruction is fulfilled. There is no map, goal image, numeric starting
pose, or intermediate feedback. Use visible geometry and the instruction to plan
translations and turns; do not describe the image instead of predicting motion.
Return ONLY a JSON object with exactly one key: {"actions": [[dx, dy, dyaw], ...]}.
Each command FIRST translates in the robot's CURRENT local frame, THEN updates
yaw. dx is forward, dy is leftward; negative values are backward/rightward.
Translation uses dataset coordinate units (meter-like); dyaw is radians,
positive counterclockwise (left), negative clockwise (right).
Use a variable number of commands, at most 64. For every command,
sqrt(dx*dx+dy*dy) <= 2.46 and abs(dyaw) <= 6.29.
For a turn before moving, use a rotation-only command followed by translation.
Choose a sensible step granularity to represent the route, not just an endpoint.
End the route by ending the list. Do not emit a Stop token or a dummy zero action.
A [0,0,0] command is a stationary step, NOT termination. An empty list represents
no movement only if the instruction genuinely requires that.
Do not include explanations, reasoning, markdown, extra keys, or nonfinite numbers.'''


def redact(value):
    """Redact credentials even if a remote error or response echoes one."""
    if isinstance(value,dict):
        return {k:('[REDACTED]' if k.lower() in {'authorization','api_key','access_token'} else redact(v))
                for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    if not isinstance(value,str): return value
    secret=os.getenv('SINAPISAI_API_KEY')
    if secret: value=value.replace(secret,'[REDACTED]')
    value=re.sub(r'(?i)Bearer\s+\S+','Bearer [REDACTED]',value)
    value=re.sub(r'(?:sk-|hf_|github_pat_)[A-Za-z0-9_-]{16,}','[REDACTED]',value)
    return value


def parse_actions(content):
    if not isinstance(content,str) or not content.strip(): raise ValueError('Empty model content')
    result=load_json(content)
    if not isinstance(result,dict) or set(result)!={'actions'}:
        raise ValueError('Expected exactly the actions key')
    validate({'split':'test','episodes':[{'episode_id':'parse_check','actions':result['actions']}]},'test')
    return result['actions']


def encode_image(image,max_edge=768,quality=90):
    image=image.convert('RGB').copy();image.thumbnail((max_edge,max_edge))
    buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=quality)
    data=buffer.getvalue()
    return 'data:image/jpeg;base64,'+base64.b64encode(data).decode('ascii'),dict(
        mime='image/jpeg',bytes=len(data),width=image.width,height=image.height,
        sha256=hashlib.sha256(data).hexdigest())


class RequestBudget:
    """Reserve before dispatch; a timeout/crash still consumes its budget slot.

    Atomic slot creation prevents parallel processes from overspending. Never
    reset this ledger to resume the same experiment.
    """
    def __init__(self,path,limit=10,authorization=None):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
        if type(limit)!=int or not 1<=limit<=1000: raise ValueError('Finite request budget must be 1..1000')
        if limit>10 and authorization!='worldnav_sprint_20261031':
            raise ValueError('Requests above 10 require the explicit sprint authorization')
        self.limit=limit

    @property
    def used(self): return len(list(self.path.glob('request_*.json')))

    def reserve(self):
        for i in range(1,self.limit+1):
            try:
                with (self.path/f'request_{i:04d}.json').open('x') as f:
                    json.dump({'request_number':i,'reserved_at_unix':time.time()},f)
                return i
            except FileExistsError: continue
        raise RuntimeError('API request budget exhausted; verify price and account allowance before more calls')


class PredictionFailure(RuntimeError):
    def __init__(self,category,record):
        self.category=category;self.record=record
        super().__init__(category)


class QwenAPIPolicy(BasePolicy):
    def __init__(self,config,budget,client=None):
        self.config=config;self.budget=budget
        if (config['base_url'],config['model'],config['api_key_env']) != (
            'https://api.sinapisai.com/v1','qwen/qwen3.8-27b','SINAPISAI_API_KEY'):
            raise ValueError('Provider, model and credential destination are fixed for this experiment')
        if config.get('format_retries',0) not in (0,1): raise ValueError('Only 0 or 1 format retry allowed')
        if not 1<=config.get('max_concurrency',1)<=4: raise ValueError('Concurrency must be 1..4')
        if not 0<=config.get('network_retries',0)<=2: raise ValueError('Network retries must be 0..2')
        from .prompts import get_prompt
        self.system_prompt=get_prompt(config.get('prompt_version','qwen_worldnav_zero_shot_v1'))
        self.limiter=AdaptiveLimiter(config.get('max_concurrency',1))
        self.fatal_error=None
        if client is None:
            from openai import OpenAI
            import httpx
            client=OpenAI(base_url=config['base_url'],api_key=os.environ[config['api_key_env']],
                max_retries=0,timeout=config['timeout_seconds'],
                http_client=httpx.Client(follow_redirects=False,timeout=config['timeout_seconds']))
        self.client=client

    def predict(self,observation,seed=0):
        uri,image_info=encode_image(observation.image,self.config['max_image_edge'],self.config['jpeg_quality'])
        messages=[{'role':'system','content':self.system_prompt},
                  {'role':'user','content':[{'type':'text','text':'Navigation instruction:\n'+observation.instruction},
                                            {'type':'image_url','image_url':{'url':uri}}]}]
        record={'attempts':[],'image_encoding':image_info,'prompt_sha256':hashlib.sha256(self.system_prompt.encode()).hexdigest(),
                'model':self.config['model'],'seed_requested':seed,'seed_sent_to_provider':False}
        if self.fatal_error:
            record['fatal_error']=self.fatal_error
            raise PredictionFailure('provider_authorization_or_credit_blocked',record)
        for retry in range(self.config.get('format_retries',0)+1):
          for network_retry in range(self.config.get('network_retries',0)+1):
            number=self.budget.reserve()
            attempt={'request_number':number,'retry_index':retry,'network_retry':network_retry,'api_success':False}
            started=time.perf_counter()
            try:
                with self.limiter:
                    response=self.client.chat.completions.create(model=self.config['model'],messages=messages,
                        temperature=self.config['temperature'],max_tokens=self.config['max_tokens'])
                attempt.update(api_success=True,raw_response=redact(response.model_dump(mode='json')),
                               latency_seconds=time.perf_counter()-started)
            except Exception as exc:
                attempt.update(latency_seconds=time.perf_counter()-started,error_type=type(exc).__name__,
                    http_status=getattr(exc,'status_code',None),error_message=redact(str(exc))[:3000])
                cause=exc.__cause__
                if cause is not None:
                    attempt['connection_cause']=dict(type=type(cause).__name__,message=redact(str(cause))[:1500])
                record['attempts'].append(attempt)
                status=attempt['http_status']
                if status in (401,402,403):self.fatal_error=f'HTTP {status}'
                transient=(status in (408,409,429,500,502,503,504) or
                           type(exc).__name__ in ('APIConnectionError','APITimeoutError','TimeoutError'))
                if status==429:self.limiter.rate_limited(self.config.get('retry_backoff_seconds',2))
                if transient and network_retry<self.config.get('network_retries',0):
                    time.sleep(min(20,self.config.get('retry_backoff_seconds',2)*2**network_retry))
                    continue
                raise PredictionFailure('api_error',record) from None
            record['attempts'].append(attempt)
            try:
                if not response.choices: raise ValueError('No completion choices')
                choice=response.choices[0]
                attempt['finish_reason']=choice.finish_reason
                if choice.finish_reason not in ('stop',None): raise ValueError('Completion did not finish normally')
                actions=parse_actions(choice.message.content)
                return dict(actions=actions,termination='end_of_list',peak_gpu_memory_mib=None,
                            api_record=record,retry_count=len(record['attempts'])-1)
            except (ValueError,TypeError,AttributeError,OverflowError,IndexError) as exc:
                attempt['parse_error']=redact(str(exc))
                if retry>=self.config.get('format_retries',0):
                    raise PredictionFailure('invalid_prediction',record) from None
                # Retry format only, without labels, metrics, or modified route hints.
                previous=response.choices[0].message.content if response.choices else ''
                messages.append({'role':'assistant','content':redact(previous or '')})
                messages.append({'role':'user','content':'Return the same planned route as valid JSON with exactly the actions key and legal finite action triples. No markdown.'})
                break


class AdaptiveLimiter:
    """Reduce concurrency and pause dispatch after a real 429 response."""
    def __init__(self,maximum):
        self.maximum=maximum;self.limit=maximum;self.active=0;self.until=0
        self.condition=threading.Condition()
    def __enter__(self):
        with self.condition:
            while self.active>=self.limit or time.monotonic()<self.until:
                self.condition.wait(timeout=max(.05,min(1,self.until-time.monotonic())))
            self.active+=1
    def __exit__(self,*args):
        with self.condition:self.active-=1;self.condition.notify_all()
    def rate_limited(self,seconds):
        with self.condition:
            self.limit=max(1,self.limit//2);self.until=max(self.until,time.monotonic()+min(30,seconds))
            self.condition.notify_all()
