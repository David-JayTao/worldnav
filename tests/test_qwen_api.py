import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from worldnav.data import Observation
from worldnav.qwen_api import (QwenAPIPolicy,RequestBudget,PredictionFailure,encode_image,
                              parse_actions,redact)
from run_qwen_api import initialize,execute_case,summarize
from audit_public import audit_blob


def config():return json.loads((ROOT/'configs/qwen_api.json').read_text())


class Response:
    def __init__(self,text='{"actions":[[1,0,0],[0,0,0],[0,0,0.5]]}',finish='stop'):
        self.choices=[SimpleNamespace(message=SimpleNamespace(content=text),finish_reason=finish)]
        self.raw={'choices':[{'message':{'content':text},'finish_reason':finish}],
                  'usage':{'prompt_tokens':100,'completion_tokens':50},'model':'qwen/qwen3.8-27b'}
    def model_dump(self,**kwargs):return self.raw


class FakeClient:
    def __init__(self,results):
        self.results=iter(results);self.calls=[]
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
    def create(self,**kwargs):
        self.calls.append(kwargs);value=next(self.results)
        if isinstance(value,Exception):raise value
        return value


class APIParsingTests(unittest.TestCase):
    def test_public_audit_rejects_api_artifacts_and_env_files(self):
        for name in ('runs/run/raw_responses/a.json','.env.local','.venv-cpu/pyvenv.cfg'):
            with self.subTest(name=name):self.assertTrue(audit_blob(name,b'example'))
        self.assertFalse(audit_blob('.env.example',b'API_CONFIGURED=false'))
    def test_valid_zero_action_is_not_stop(self):
        self.assertEqual(len(parse_actions('{"actions":[[0,0,0],[1,0,0]]}')),2)
    def test_invalid_json_and_action_types(self):
        for text in ('','```json\n{}\n```','{"actions":[],"x":1}',
                     '{"actions":[[NaN,0,0]]}','{"actions":[[Infinity,0,0]]}',
                     '{"actions":[[true,0,0]]}','{"actions":[[1,0]]}',
                     '{"actions":[[2,2,0]]}','{"actions":[],"actions":[]}'):
            with self.subTest(text=text),self.assertRaises((ValueError,TypeError)):parse_actions(text)
    def test_action_count_limit(self):
        with self.assertRaises(ValueError):parse_actions(json.dumps({'actions':[[0,0,0]]*65}))
    def test_image_mime_size_and_decode(self):
        uri,info=encode_image(Image.new('RGBA',(1500,800)),768)
        self.assertTrue(uri.startswith('data:image/jpeg;base64,'));self.assertEqual(info['width'],768)
        with Image.open(io.BytesIO(base64.b64decode(uri.split(',')[1]))) as im:
            self.assertEqual(im.format,'JPEG');self.assertEqual(im.size,(info['width'],info['height']))
    def test_credentials_redacted_recursively(self):
        with patch.dict('os.environ',{'SINAPISAI_API_KEY':'private-test-value'}):
            value=redact({'a':['private-test-value'],'Authorization':'Bearer private-test-value'})
        self.assertNotIn('private-test-value',json.dumps(value))


class APIPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.budget=RequestBudget(Path(self.tmp.name)/'ledger',10)
        self.obs=Observation(Image.new('RGB',(8,8)),'Turn left')
    def test_mock_multimodal_request_and_no_ground_truth(self):
        client=FakeClient([Response()]);result=QwenAPIPolicy(config(),self.budget,client).predict(self.obs)
        self.assertEqual(len(result['actions']),3);request=client.calls[0]
        self.assertEqual(request['model'],'qwen/qwen3.8-27b')
        content=request['messages'][1]['content'];self.assertEqual([x['type'] for x in content],['text','image_url'])
        self.assertEqual(set(request),{'model','messages','temperature','max_tokens'})
        self.assertEqual(self.budget.used,1)
    def test_timeout_records_failure_without_retry(self):
        client=FakeClient([TimeoutError('timed out')]);policy=QwenAPIPolicy(config(),self.budget,client)
        with self.assertRaises(PredictionFailure) as caught:policy.predict(self.obs)
        self.assertEqual(caught.exception.category,'api_error');self.assertEqual(len(client.calls),1)
        self.assertEqual(caught.exception.record['attempts'][0]['error_type'],'TimeoutError')
    def test_format_only_retry_is_bounded(self):
        cfg=config();cfg['format_retries']=1
        client=FakeClient([Response('invalid'),Response()]);result=QwenAPIPolicy(cfg,self.budget,client).predict(self.obs)
        self.assertEqual(result['retry_count'],1);self.assertEqual(self.budget.used,2)
    def test_repeated_format_failure_has_raw_responses(self):
        cfg=config();cfg['format_retries']=1;client=FakeClient([Response('invalid'),Response('invalid')])
        with self.assertRaises(PredictionFailure) as caught:QwenAPIPolicy(cfg,self.budget,client).predict(self.obs)
        self.assertEqual(len(caught.exception.record['attempts']),2)
    def test_truncated_output_is_failure(self):
        with self.assertRaises(PredictionFailure):
            QwenAPIPolicy(config(),self.budget,FakeClient([Response(finish='length')])).predict(self.obs)
    def test_other_provider_or_model_rejected(self):
        for field,value in [('base_url','https://example.com/v1'),('model','another-model')]:
            cfg=config();cfg[field]=value
            with self.assertRaises(ValueError):QwenAPIPolicy(cfg,self.budget,FakeClient([]))
    def test_request_budget_persists_and_exhausts(self):
        for _ in range(10):self.budget.reserve()
        with self.assertRaises(RuntimeError):RequestBudget(self.budget.path).reserve()
        self.assertEqual(self.budget.used,10)
    def test_no_hidden_network_retry_on_http_error(self):
        error=RuntimeError('HTTP failure');client=FakeClient([error])
        with self.assertRaises(PredictionFailure):QwenAPIPolicy(config(),self.budget,client).predict(self.obs)
        self.assertEqual(len(client.calls),1)


class APIExperimentTests(unittest.TestCase):
    def test_success_failure_persistence_coverage_and_resume_schedule(self):
        events=[]
        items=[dict(split=s,episode_id=str(i),instruction_style=i%3) for i,s in enumerate(('val_seen','val_unseen'))]
        manifest={'episodes':items,'seed':42,'manifest_kind':'unit_test_only','sources':{}}
        observation=Observation(Image.new('RGB',(2,2)),'Go')
        def reference(*args):events.append('reference');return dict(position=[[0,0],[1,0]],yaw=[0,0])
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';frozen=initialize(run,manifest,config());budget=RequestBudget(run/'logs/request_budget')
            good=QwenAPIPolicy(config(),budget,FakeClient([Response('{"actions":[[1,0,0]]}')]))
            bad=QwenAPIPolicy(config(),budget,FakeClient([Response('not-json')]))
            from worldnav.evaluation import load_metrics
            with patch('run_qwen_api.load_observation',return_value=observation),patch('run_qwen_api.load_reference',side_effect=reference):
                one=execute_case(good,items[0],Path(tmp),run,42,load_metrics())
                two=execute_case(bad,items[1],Path(tmp),run,43,load_metrics())
            summary=summarize(run,frozen,budget)
            self.assertEqual(events,['reference']);self.assertEqual(one['status'],'evaluated')
            self.assertEqual(two['failure_category'],'invalid_prediction')
            self.assertEqual(summary['evaluated_cases'],1);self.assertEqual(summary['legal_prediction_rate'],.5)
            self.assertAlmostEqual(summary['overall']['score_failure_zero'],50)
            self.assertTrue((run/'raw_responses/val_unseen__1.json').exists())
            raw=json.loads((run/'raw_responses/val_seen__0.json').read_text())
            self.assertEqual(parse_actions(raw['attempts'][0]['raw_response']['choices'][0]['message']['content']),[[1,0,0]])
            self.assertEqual(json.loads((run/'remaining_tasks.json').read_text())['remaining_count'],0)
            with self.assertRaises(FileExistsError):initialize(run,manifest,config())
