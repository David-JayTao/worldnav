import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'scripts')]
from test_qwen_api import FakeClient,Response,config
from worldnav.qwen_api import QwenAPIPolicy,RequestBudget,PredictionFailure
from worldnav.data import Observation
from worldnav.prompts import get_prompt
from PIL import Image
from worldnav.runner import dump
from run_qwen_api import initialize
from run_api_sprint import recover_persisted_response,archive_incomplete_or_failed


class SprintTests(unittest.TestCase):
    def test_development_manifest_has_no_formal_trajectory_overlap(self):
        root=Path(__file__).resolve().parents[1]
        formal=json.loads((root/'configs/eval_100.json').read_text())['episodes']
        dev=json.loads((root/'configs/dev_12.json').read_text())['episodes']
        self.assertEqual(len(dev),12)
        self.assertFalse({e['trajectory_sha256'] for e in formal}&{e['trajectory_sha256'] for e in dev})
        for split in ('val_seen','val_unseen'):
            self.assertEqual([sum(e['split']==split and e['instruction_style']==i for e in dev) for i in range(3)],[2,2,2])

    def test_interrupt_recovery_reuses_raw_output_without_api(self):
        item=dict(episode_id='one',split='val_seen',instruction_style=0)
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';initialize(run,dict(episodes=[item,dict(item,episode_id='two',split='val_unseen')]),config())
            dump(run/'claims/val_seen__one.json',dict(episode_id='one'))
            raw=dict(attempts=[dict(api_success=True,latency_seconds=1,raw_response=Response('{"actions":[[1,0,0]]}').raw)])
            dump(run/'raw_responses/val_seen__one.json',raw)
            def ref(*args):
                self.assertTrue((run/'predictions/val_seen__one.json').exists())
                return dict(position=[[0,0],[1,0]],yaw=[0,0])
            from worldnav.evaluation import load_metrics
            with patch('run_api_sprint.load_reference',side_effect=ref),patch('run_api_sprint.load_observation',return_value=Observation(Image.new('RGB',(2,2)),'Go')):
                self.assertTrue(recover_persisted_response(run,item,Path(tmp),load_metrics()))
            row=json.loads((run/'cases/val_seen__one.json').read_text())
            self.assertTrue(row['recovered_from_persisted_response']);self.assertEqual(row['status'],'evaluated')
            self.assertAlmostEqual(row['evaluation_metrics']['Score'],100)

    def test_failed_artifacts_are_archived_before_retry(self):
        item=dict(episode_id='one',split='val_seen')
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);p=run/'raw_responses/val_seen__one.json';dump(p,{'attempts':[]})
            archive_incomplete_or_failed(run,item)
            self.assertFalse(p.exists())
            self.assertTrue((run/'history/val_seen__one/attempt_1/raw_responses/val_seen__one.json').exists())
    def test_expanded_budget_needs_specific_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):RequestBudget(tmp,200)
            budget=RequestBudget(tmp,200,'worldnav_sprint_20261031')
            for _ in range(11):budget.reserve()
            self.assertEqual(budget.used,11)

    def test_network_failure_then_success_retries_finitely(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=config();cfg.update(network_retries=2,retry_backoff_seconds=0)
            client=FakeClient([TimeoutError('temporary'),Response()])
            result=QwenAPIPolicy(cfg,RequestBudget(tmp),client).predict(Observation(Image.new('RGB',(2,2)),'Go'))
            self.assertEqual(len(result['api_record']['attempts']),2)

    def test_429_reduces_concurrency_then_recovers(self):
        class RateLimitError(Exception):status_code=429
        with tempfile.TemporaryDirectory() as tmp:
            cfg=config();cfg.update(network_retries=1,retry_backoff_seconds=0,max_concurrency=4)
            policy=QwenAPIPolicy(cfg,RequestBudget(tmp),FakeClient([RateLimitError(),Response()]))
            result=policy.predict(Observation(Image.new('RGB',(2,2)),'Go'))
            self.assertEqual(policy.limiter.limit,2);self.assertEqual(result['retry_count'],1)

    def test_authorization_failure_stops_later_paid_requests(self):
        class AuthorizationError(Exception):status_code=401
        with tempfile.TemporaryDirectory() as tmp:
            client=FakeClient([AuthorizationError()]);policy=QwenAPIPolicy(config(),RequestBudget(tmp),client)
            obs=Observation(Image.new('RGB',(2,2)),'Go')
            for _ in range(2):
                with self.assertRaises(PredictionFailure):policy.predict(obs)
            self.assertEqual(len(client.calls),1)

    def test_prompts_are_distinct_and_v1_unchanged(self):
        from worldnav.qwen_api import SYSTEM_PROMPT
        versions=[get_prompt(v) for v in ('qwen_worldnav_zero_shot_v1','qwen_worldnav_structured_v2','qwen_worldnav_scale_v3')]
        self.assertEqual(versions[0],SYSTEM_PROMPT);self.assertEqual(len(set(versions)),3)
        with self.assertRaises(ValueError):get_prompt('not-a-version')

    def test_atomic_dump_does_not_replace_existing_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'case.json';dump(p,{'actions':[1]})
            with self.assertRaises(FileExistsError):dump(p,{'actions':[2]})
            self.assertEqual(json.loads(p.read_text()),{'actions':[1]})
            self.assertFalse(list(Path(tmp).glob('*.tmp')))
