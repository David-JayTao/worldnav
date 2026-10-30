import io
import json
from pathlib import Path
import pickle
import sys
import tarfile
import tempfile
import unittest
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from worldnav.cosmos import build_messages,parse_actions
from worldnav.data import Observation
from audit_validation import inspect_archive


class CosmosContractTests(unittest.TestCase):
    def test_prompt_only_initial_image_and_instruction(self):
        obs=Observation(Image.new('RGB',(2,2)),'Go left')
        messages=build_messages(obs)
        self.assertEqual(messages[1]['content'][0]['image'],obs.image)
        self.assertEqual(messages[1]['content'][1]['text'],obs.instruction)
        self.assertEqual(len(messages[1]['content']),2)

    def test_body_actions_unchanged(self):
        self.assertEqual(parse_actions('{"actions":[[1,0,0.5]]}'),[[1,0,0.5]])

    def test_stop_empty(self):
        self.assertEqual(parse_actions('{"actions":[]}'),[])

    def test_reject_noncontract_outputs(self):
        for value in ['```json\n{"actions":[]}\n```','{"actions":[],"reason":"x"}',
                      '{"actions":[[true,0,0]]}','{"actions":[[3,0,0]]}',
                      '{"actions":[],"actions":[]}','{"actions":[[NaN,0,0]]}',
                      '<dx_1><dy_0><dyaw_0>']:
            with self.subTest(value=value),self.assertRaises(ValueError):parse_actions(value)


class ArchiveAuditTests(unittest.TestCase):
    def make_archive(self,path,corrupt=False):
        image=io.BytesIO();Image.new('RGB',(2,2)).save(image,format='JPEG')
        raw={'position':np.array([[0.,0.],[1.,0.]]),'yaw':np.array([0.,0.]),'instruction':'Go'}
        with tarfile.open(path,'w') as archive:
            for name,data in [('0000.jpg',b'bad' if corrupt else image.getvalue()),('0001.jpg',image.getvalue()),('traj_data.pkl',pickle.dumps(raw))]:
                info=tarfile.TarInfo('val_seen/a_0/'+name);info.size=len(data);archive.addfile(info,io.BytesIO(data))

    def test_archive_counts_and_image_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x.tar';self.make_archive(path);r=inspect_archive(path,'val_seen')
            self.assertEqual((r['episodes'],r['images_decoded'],r['trajectory_files']),(1,2,1))
            self.assertEqual(r['image_pose_count_mismatches'],0)

    def test_corrupt_image_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x.tar';self.make_archive(path,True)
            with self.assertRaises(OSError):inspect_archive(path,'val_seen')
