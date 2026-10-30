import dataclasses
import hashlib
import io
import json
from pathlib import Path
import pickle
import random
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from worldnav.data import Observation,read_reference_bytes,safe_episode_id
from worldnav.runner import new_run,run_batch
from build_eval_manifest import catalog,choose,save_unchanged


class DataTests(unittest.TestCase):
    def test_numpy_protocols(self):
        raw={'position':np.array([[0.,0.],[1.,0.]]),'yaw':np.array([0.,0.]),'instruction':'forward'}
        for protocol in (4,5):
            self.assertEqual(read_reference_bytes(pickle.dumps(raw,protocol=protocol))['instruction'],'forward')

    def test_pickle_global_rejected(self):
        with self.assertRaises(pickle.UnpicklingError):read_reference_bytes(pickle.dumps(eval))

    def test_path_traversal_rejected(self):
        for eid in ('../a','/tmp/a','a/b','..'):
            with self.assertRaises(ValueError):safe_episode_id(eid)

    def test_observation_boundary(self):
        self.assertEqual({f.name for f in dataclasses.fields(Observation)},{'image','instruction'})

    def test_zero_padded_frame_and_tar_order(self):
        raw={'position':np.array([[0.,0.],[1.,0.]]),'yaw':np.array([0.,0.]),'instruction':'forward'}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.tar'
            with tarfile.open(p,'w') as archive:
                for name,data in [('traj_data.pkl',pickle.dumps(raw)),('0000.jpg',b'example')]:
                    info=tarfile.TarInfo('val_unseen/a_0/'+name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
            rows=catalog(p,'val_unseen',p.stat().st_size)
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['source_image_name'],'0000.jpg')

    def test_partial_member_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.tar'
            with tarfile.open(p,'w') as archive:
                info=tarfile.TarInfo('val_seen/a_0/0.jpg');info.size=100;archive.addfile(info,io.BytesIO(b'x'*100))
            self.assertEqual(catalog(p,'val_seen',530),[])

    def test_selection_reproducible_balanced_unique(self):
        records=[dict(episode_id=f'route{i}_{j}',trajectory_sha256=str(i),instruction_style=j) for i in range(70) for j in range(3)]
        first=choose(records,42)
        random.Random(8).shuffle(records)
        self.assertEqual(first,choose(records,42))
        self.assertEqual(len({x['trajectory_sha256'] for x in first}),50)
        self.assertEqual([sum(x['instruction_style']==i for x in first) for i in range(3)],[17,17,16])

    def test_insufficient_groups(self):
        with self.assertRaises(ValueError):choose([],42)

    def test_preserve_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x';save_unchanged(p,b'first');save_unchanged(p,b'first')
            with self.assertRaises(ValueError):save_unchanged(p,b'other')
            self.assertEqual(p.read_bytes(),b'first')


class RunnerTests(unittest.TestCase):
    def test_run_directory_is_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run';new_run(p,{},'unit_test')
            with self.assertRaises(FileExistsError):new_run(p,{},'unit_test')

    def test_end_to_end_success_failure_and_no_label_input(self):
        events=[]
        class Policy:
            def predict(self,obs,seed):
                events.append('model')
                if set(obs.__dict__)!={'image','instruction'}:raise AssertionError('Label leakage')
                if seed==2:raise ValueError('deliberate unit-test failure')
                return dict(actions=[[1,0,0]],termination='stop',peak_gpu_memory_mib=None)
        def reference(*args):
            events.append('reference')
            return dict(position=[[0,0],[1,0]],yaw=[0,0])
        cfg=dict(seed=1,episodes=[dict(split='val_seen',episode_id='one'),dict(split='val_unseen',episode_id='two')])
        with tempfile.TemporaryDirectory() as tmp:
            run=new_run(Path(tmp)/'run',cfg,'unit_test')
            with patch('worldnav.runner.load_observation',return_value=Observation(Image.new('RGB',(2,2)),'forward')),patch('worldnav.runner.load_reference',side_effect=reference):
                metrics=run_batch(Policy(),cfg,Path(tmp),run,mode='unit_test')
            self.assertEqual(events,['model','reference','model'])
            self.assertEqual(metrics['kind'],'unit_test_only')
            self.assertEqual(metrics['attempted'],2);self.assertEqual(metrics['evaluated'],1)
            self.assertAlmostEqual(metrics['aggregate']['Score'],100,places=10)
            self.assertTrue((run/'failure_cases/val_unseen__two.json').exists())
            for name in ['per_episode.csv','metrics.json','summary.json','runtime.json','provenance.json','config.json']:
                self.assertTrue((run/name).is_file())


if __name__=='__main__':unittest.main()
