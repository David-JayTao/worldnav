import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from worldnav.geometry import integrate,world_delta_to_local,canonical_reference,wrap_angle
from worldnav.actions import decode_action,adapt_action,normalize_generation_output
from worldnav.protocol import validate,validate_zip,load_json
from worldnav.evaluation import evaluate
from worldnav.checkpoint import verify_checkpoint
from download_validation import check_range


class GeometryTests(unittest.TestCase):
    def test_forward_at_ninety_degrees(self):
        xy,yaw=integrate([[2,0,0]],(3,4,math.pi/2))
        np.testing.assert_allclose(xy[-1],[3,6],atol=1e-12)

    def test_left_is_positive(self):
        xy,_=integrate([[0,2,0]],(3,4,math.pi/2))
        np.testing.assert_allclose(xy[-1],[1,4],atol=1e-12)

    def test_translation_precedes_rotation(self):
        xy,_=integrate([[1,0,math.pi/2],[1,0,0]])
        np.testing.assert_allclose(xy,[[0,0],[1,0],[1,1]],atol=1e-12)

    def test_canonical_reference_rotation(self):
        xy,yaw=canonical_reference([[3,4],[3,6],[2,6]],[math.pi/2,math.pi,math.pi])
        np.testing.assert_allclose(xy,[[0,0],[2,0],[2,1]],atol=1e-12)

    def test_world_delta_conversion(self):
        np.testing.assert_allclose(world_delta_to_local([0,1,0],math.pi/2),[1,0,0],atol=1e-12)

    def test_heading_continuity(self):
        _,yaw=integrate([[0,0,.2],[0,0,.2]],(0,0,3.1))
        self.assertAlmostEqual(yaw[-1],3.5)
        self.assertAlmostEqual(wrap_angle(math.pi),-math.pi)

    def test_invalid_numbers(self):
        with self.assertRaises(ValueError):integrate([[float('nan'),0,0]])

    def test_reference_identity_metric(self):
        metrics=evaluate([[1,0,math.pi/2],[1,0,0]],[[5,7],[6,7],[6,8]],[0,math.pi/2,math.pi/2])
        self.assertAlmostEqual(metrics['Score'],100,places=6)

    def test_short_prediction_is_scored(self):
        metrics=evaluate([],[[0,0],[1,0],[2,0]],[0,0,0])
        self.assertEqual(metrics['SR'],0)
        self.assertGreater(metrics['ATE'],0)


class ActionTests(unittest.TestCase):
    def test_valid_tokens(self):
        self.assertEqual(decode_action('Move by dx: <dx_pos_bin_12>, dy: <dy_neg_bin_03>, dyaw: <dyaw_pos_bin_20>'),[.12,-.03,.2])

    def test_missing_tokens_rejected(self):
        with self.assertRaises(ValueError):decode_action('<dx_pos_bin_12>')

    def test_duplicate_tokens_rejected(self):
        with self.assertRaises(ValueError):decode_action('<dx_pos_bin_12><dx_pos_bin_13><dy_pos_bin_00><dyaw_pos_bin_00>')

    def test_outside_vocabulary(self):
        with self.assertRaises(ValueError):decode_action('<dx_pos_bin_999><dy_pos_bin_00><dyaw_pos_bin_00>')

    def test_stop(self):
        self.assertIsNone(decode_action('Stop'))
        with self.assertRaises(ValueError):decode_action('Do not stop <dx_pos_bin_01>')

    def test_uses_predicted_yaw(self):
        result=adapt_action([0,1,.1],'canonical_world',math.pi/2)
        np.testing.assert_allclose(result,[1,0,.1],atol=1e-12)

    def test_tuple_generation(self):
        array=np.zeros((1,10),dtype=int)
        self.assertIs(normalize_generation_output((array,None)),array)
        with self.assertRaises(ValueError):normalize_generation_output(np.zeros(10))


class ProtocolTests(unittest.TestCase):
    def setUp(self):self.data={'split':'val_seen','episodes':[{'episode_id':'a','actions':[[1,0,0]]}]}

    def test_valid(self):self.assertEqual(validate(self.data,'val_seen',['a'],True)['episodes'],1)

    def test_action_bounds(self):
        for action in ([2,2,0],[0,0,6.3],[True,0,0],[float('inf'),0,0],[0,0]):
            with self.subTest(action=action):
                self.data['episodes'][0]['actions']=[action]
                with self.assertRaises(ValueError):validate(self.data,'val_seen')

    def test_max_actions(self):
        self.data['episodes'][0]['actions']*=65
        with self.assertRaises(ValueError):validate(self.data,'val_seen')

    def test_duplicate_unknown_missing_ids(self):
        with self.assertRaises(ValueError):validate(self.data,'val_seen',['b'],True)
        with self.assertRaises(ValueError):validate(self.data,'val_seen',['a','b'],True)
        self.data['episodes']*=2
        with self.assertRaises(ValueError):validate(self.data,'val_seen')

    def test_json_constants_and_duplicate_keys(self):
        for text in ('{"a":NaN}','{"a":1,"a":2}'):
            with self.assertRaises(ValueError):load_json(text)

    def test_full_requires_manifest(self):
        with self.assertRaises(ValueError):validate(self.data,'val_seen',full=True)

    def test_zip_layout_and_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('nested/val_seen.json',json.dumps(self.data))
            with self.assertRaises(ValueError):validate_zip(p,1,{})
            with self.assertRaises(ValueError):validate_zip(p,3,{})

    def test_valid_phase1_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.zip'
            with zipfile.ZipFile(p,'w') as z:
                for split in ('val_seen','val_unseen'):
                    z.writestr(split+'.json',json.dumps(dict(split=split,episodes=self.data['episodes'])))
            self.assertEqual(len(validate_zip(p,1,dict(val_seen=['a'],val_unseen=['a']))),2)


class DownloadAndCheckpointTests(unittest.TestCase):
    def test_resume_valid(self):check_range(206,{'Content-Range':'bytes 5-9/10','Content-Length':'5'},5,10)

    def test_resume_ignored(self):
        with self.assertRaises(ValueError):check_range(200,{},5,10)

    def test_resume_wrong_offset(self):
        with self.assertRaises(ValueError):check_range(206,{'Content-Range':'bytes 0-9/10'},5,10)

    def test_missing_checkpoint(self):
        with self.assertRaises(ValueError):verify_checkpoint(None)

    def test_template_is_not_checkpoint(self):
        with self.assertRaises(ValueError):verify_checkpoint(ROOT/'configs/checkpoint.example.json')


if __name__=='__main__':unittest.main()
