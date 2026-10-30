"""Verify full official archives and count/decode images without extracting them."""
import argparse
import json
from pathlib import Path
import sys
import tarfile
from PIL import Image
from download_validation import sha256
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldnav.data import read_reference_bytes,safe_episode_id


def inspect_archive(path,split):
    episodes={};images=0;metadata=0;members=0
    with tarfile.open(path,'r|') as archive:
        for member in archive:
            archive.members.clear()
            if member.isdir():continue
            parts=Path(member.name).parts
            if not member.isfile() or len(parts)!=3 or parts[0]!=split:
                raise ValueError('Unexpected archive member')
            eid=safe_episode_id(parts[1]);name=parts[2];members+=1
            row=episodes.setdefault(eid,{'frames':set(),'poses':None})
            stream=archive.extractfile(member)
            if name=='traj_data.pkl':
                if row['poses'] is not None:raise ValueError('Duplicate metadata')
                ref=read_reference_bytes(stream.read());row['poses']=len(ref['position']);metadata+=1
            elif Path(name).suffix.lower() in ('.jpg','.jpeg','.png') and Path(name).stem.isdigit():
                index=int(Path(name).stem)
                if index in row['frames']:raise ValueError('Duplicate image index')
                with Image.open(stream) as image:
                    image.load()
                row['frames'].add(index);images+=1
            else:raise ValueError('Unknown archive payload')
    incomplete=[eid for eid,row in episodes.items() if row['poses'] is None or 0 not in row['frames']]
    mismatch=sum(row['poses']!=len(row['frames']) for row in episodes.values())
    if incomplete:raise ValueError(f'{len(incomplete)} episodes lack metadata or initial image')
    return dict(split=split,episodes=len(episodes),images_decoded=images,trajectory_files=metadata,
                regular_members=members,image_pose_count_mismatches=mismatch,complete_initial_inputs=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--splits',nargs='+',choices=('val_seen','val_unseen'),default=['val_seen','val_unseen'])
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise FileExistsError('Audit output already exists')
    cfg=json.loads((Path(__file__).resolve().parents[1]/'configs/datasets.json').read_text());result={}
    for split in args.splits:
        expected=cfg['splits'][split]
        path=args.data_root/'archives'/(split+'.tar')
        if path.stat().st_size!=expected['size'] or sha256(path)!=expected['sha256']:
            raise ValueError('Full archive size/SHA256 mismatch')
        result[split]=dict(inspect_archive(path,split),sha256=expected['sha256'],bytes=expected['size'])
        print(json.dumps(result[split]),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:json.dump(dict(revision=cfg['revision'],splits=result,
        both_validation_splits_audited=set(result)==set(cfg['splits'])),f,indent=2)


if __name__=='__main__':main()
