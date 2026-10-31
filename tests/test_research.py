import json,math,tempfile,unittest
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'scripts')]
from test_qwen_api import FakeClient,Response,config
from worldnav.trajectory_plan import compile_plan
from worldnav.research_policy import make_policy
from worldnav.qwen_api import RequestBudget,PredictionFailure
from worldnav.data import Observation
from worldnav.geometry import integrate
from PIL import Image
from run_qwen_api import initialize,execute_case
from run_api_sprint import sprint_summary
from unittest.mock import patch
from worldnav.evaluation import load_metrics


def plan(**updates):
 value={'segments':[{'landmark':'corner','turn_before':math.pi/2,'distance':1.1,'step':.3}], 'stop_condition':'before door'}
 value.update(updates);return json.dumps(value)

class ResearchPolicyTests(unittest.TestCase):
 def test_compiler_preserves_distance_and_turn_before_motion(self):
  actions=compile_plan(plan());xy,yaw=integrate(actions)
  self.assertAlmostEqual(xy[-1][0],0);self.assertAlmostEqual(xy[-1][1],1.1)
  self.assertAlmostEqual(sum(math.hypot(a[0],a[1]) for a in actions),1.1)
  self.assertTrue(all(math.hypot(a[0],a[1])<=.3 for a in actions))
 def test_compiler_rejects_oversized_plan_without_truncating(self):
  with self.assertRaises(ValueError):compile_plan(plan(segments=[{'landmark':'long hall','turn_before':0,'distance':40,'step':.05}]))
 def test_compiler_rejects_missing_fields_nonfinite_and_boolean(self):
  for field,value in [('distance',True),('turn_before',float('nan')),('step',0)]:
   segment={'landmark':'door','turn_before':0,'distance':1,'step':.2};segment[field]=value
   with self.assertRaises(ValueError):compile_plan(plan(segments=[segment]))
  with self.assertRaises(ValueError):compile_plan('{"segments":[]}')
 def test_compiler_does_not_accept_actions_or_dummy_stop(self):
  with self.assertRaises(ValueError):compile_plan('{"actions":[[0,0,0]]}')
  with self.assertRaises(ValueError):compile_plan(plan(segments=[{'landmark':'stop','turn_before':0,'distance':0,'step':.2}]))
 def test_structured_policy_uses_only_observation_and_own_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   cfg=config();cfg.update(policy_kind='structured_route',prompt_version='research_structured_v1')
   client=FakeClient([Response(plan())]);policy=make_policy(cfg,RequestBudget(Path(tmp)/'ledger'),client)
   result=policy.predict(Observation(Image.new('RGB',(3,3)),'Turn left then stop at door'))
   self.assertEqual(result['actions'],compile_plan(plan()))
   self.assertIn('image_url',str(client.calls[0]['messages'][1]))
   self.assertNotIn('reference',str(client.calls[0]['messages'][1]))
 def test_native_json_passed_explicitly_and_default_unchanged(self):
  with tempfile.TemporaryDirectory() as tmp:
   cfg=config();cfg['response_format']={'type':'json_object'};client=FakeClient([Response()])
   make_policy(cfg,RequestBudget(Path(tmp)/'ledger'),client).predict(Observation(Image.new('RGB',(3,3)),'Go'))
   self.assertEqual(client.calls[0]['response_format'],{'type':'json_object'})
 def test_alternate_vision_model_keeps_credential_destination(self):
  with tempfile.TemporaryDirectory() as tmp:
   cfg=config();cfg.update(model='qwen/qwen3-vl-32b-instruct',policy_kind='vision_comparison');client=FakeClient([Response()])
   make_policy(cfg,RequestBudget(Path(tmp)/'ledger'),client).predict(Observation(Image.new('RGB',(3,3)),'Go'))
   self.assertEqual(client.calls[0]['model'],cfg['model'])
   cfg['base_url']='https://other.invalid/v1'
   with self.assertRaises(ValueError):make_policy(cfg,RequestBudget(Path(tmp)/'ledger'),client)
 def test_single_split_smoke_does_not_silently_drop_cases(self):
  with tempfile.TemporaryDirectory() as tmp:
   cases=[{'split':'val_seen','episode_id':'a'}]
   frozen=initialize(Path(tmp)/'run',{'episodes':cases},config())
   self.assertEqual(frozen['episodes'],cases)

 def test_single_case_summary_has_no_divide_by_zero_for_missing_split(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';item={'split':'val_seen','episode_id':'a','instruction_style':0}
   cfg=config();cfg.update(prompt_version='qwen_worldnav_zero_shot_v1')
   frozen=initialize(run,{'episodes':[item],'seed':1,'manifest_kind':'mock','sources':{}},cfg)
   budget=RequestBudget(run/'logs/request_budget');client=FakeClient([Response('{"actions":[[1,0,0]]}')])
   with patch('run_qwen_api.load_observation',return_value=Observation(Image.new('RGB',(3,3)),'Go')),patch('run_qwen_api.load_reference',return_value={'position':[[0,0],[1,0]],'yaw':[0,0]}):
    execute_case(make_policy(cfg,budget,client),item,Path(tmp),run,1,load_metrics())
   summary=sprint_summary(run,frozen,budget,cfg)
   self.assertIsNone(summary['per_split']['val_unseen']['score_all_planned_failure_zero'])
   self.assertEqual(summary['planned_cases'],1)

 def test_public_audit_checks_embedded_ppt_xml(self):
  import zipfile,io
  from audit_public import audit_blob
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
   archive.writestr('ppt/slides/slide1.xml','<text>'+('sk-'+'a'*30)+'</text>')
  self.assertTrue(any('sensitive' in e for e in audit_blob('reports/demo.pptx',buffer.getvalue())))

 def test_metric_sensitivity_subdivision_keeps_body_frame_polyline_endpoint(self):
  from audit_metric_sensitivity import subdivide
  actions=[[1,.2,.7],[0,0,-.3],[.4,-.1,-.8]]
  xy,yaw=integrate(actions);other,heading=integrate(subdivide(actions))
  self.assertAlmostEqual(xy[-1][0],other[-1][0]);self.assertAlmostEqual(xy[-1][1],other[-1][1]);self.assertAlmostEqual(yaw[-1],heading[-1])
  self.assertAlmostEqual(sum(math.dist(a,b) for a,b in zip(xy,xy[1:])),sum(math.dist(a,b) for a,b in zip(other,other[1:])))

 def test_budget_exhaustion_retains_already_billed_response(self):
  with tempfile.TemporaryDirectory() as tmp:
   cfg=config();cfg['format_retries']=1
   client=FakeClient([Response('invalid JSON')]);budget=RequestBudget(Path(tmp)/'ledger',1)
   with self.assertRaises(PredictionFailure) as caught:
    make_policy(cfg,budget,client).predict(Observation(Image.new('RGB',(3,3)),'Go'))
   self.assertEqual(caught.exception.category,'request_budget_exhausted')
   self.assertEqual(len(caught.exception.record['attempts']),1)
   self.assertTrue(caught.exception.record['attempts'][0]['api_success'])
   self.assertEqual(client.calls[0]['model'],cfg['model']);self.assertEqual(budget.used,1)
