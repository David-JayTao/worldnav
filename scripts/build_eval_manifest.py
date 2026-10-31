"""Freeze reproducible 50 seen + 50 unseen local cases from official TAR snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from worldnav.data import read_reference_bytes, safe_episode_id


def sha_prefix(path, count):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        while count:
            chunk=stream.read(min(count,8*1024*1024))
            if not chunk: raise ValueError("Archive shorter than frozen snapshot")
            h.update(chunk);count-=len(chunk)
    return h.hexdigest()


def catalog(path, split, snapshot_bytes):
    records=[]; images={}
    with tarfile.open(path,mode="r:") as archive:
        while True:
            try: member=archive.next()
            except (tarfile.ReadError,EOFError): break
            if member is None or member.offset_data+member.size>snapshot_bytes: break
            archive.members.clear()  # Do not retain hundreds of thousands of frame headers.
            parts=Path(member.name).parts
            if member.isdir(): continue
            if not member.isfile() or len(parts)!=3 or parts[0]!=split:
                raise ValueError(f"Unexpected tar entry: {member.name}")
            eid=safe_episode_id(parts[1])
            frame=Path(parts[-1])
            if frame.suffix.lower() in ('.jpg','.jpeg','.png') and frame.stem.isdigit() and int(frame.stem)==0:
                images[eid]=(member.offset_data,member.size,parts[-1])
            if parts[-1]!="traj_data.pkl": continue
            content=archive.extractfile(member).read()
            raw=read_reference_bytes(content)
            group_hash=hashlib.sha256(raw['position'].astype('<f8').tobytes()+raw['yaw'].astype('<f8').tobytes()).hexdigest()
            style=eid.rsplit('_',1)[-1]
            if style not in ('0','1','2'): raise ValueError(f"Unrecognized instruction suffix: {eid}")
            records.append(dict(episode_id=eid,split=split,trajectory_sha256=group_hash,
                instruction_style=int(style),metadata_offset=member.offset_data,metadata_size=member.size,
                metadata_sha256=hashlib.sha256(content).hexdigest()))
    # TAR order differs between splits: metadata can precede the initial frame.
    complete=[]
    for row in records:
        if row['episode_id'] in images:
            row.update(image_offset=images[row['episode_id']][0],image_size=images[row['episode_id']][1],
                       source_image_name=images[row['episode_id']][2])
            complete.append(row)
    return complete


def choose(records, seed, count=50):
    groups={}
    for row in sorted(records,key=lambda x:x['episode_id']):
        groups.setdefault(row['trajectory_sha256'],{}).setdefault(row['instruction_style'],row)
    # Require all three styles, so balanced selection is independent of incomplete last groups.
    keys=sorted(k for k,v in groups.items() if set(v)=={0,1,2})
    if len(keys)<count: raise ValueError(f"Need {count} complete distinct trajectories; available {len(keys)}")
    rng=random.Random(seed);rng.shuffle(keys)
    return [groups[key][i%3] for i,key in enumerate(keys[:count])]


def save_unchanged(path,content):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=content: raise ValueError(f"Refusing to overwrite different content: {path.name}")
    else:
        with path.open('xb') as stream: stream.write(content)


def materialize(archive_path,rows,root):
    with archive_path.open('rb') as stream:
        for row in rows:
            folder=root/'samples'/row['split']/row['episode_id']
            for filename,prefix in [('0.jpg','image'),('traj_data.pkl','metadata')]:
                stream.seek(row[prefix+'_offset']);content=stream.read(row[prefix+'_size'])
                if len(content)!=row[prefix+'_size']: raise ValueError('Archive truncated during extraction')
                digest=hashlib.sha256(content).hexdigest()
                if prefix=='metadata' and digest!=row['metadata_sha256']: raise ValueError('Metadata changed')
                row[prefix+'_sha256']=digest
                save_unchanged(folder/filename,content)
                if prefix=='metadata':
                    raw=read_reference_bytes(content)
                    save_unchanged(folder/'input.json',(json.dumps({'instruction':raw['instruction']},ensure_ascii=False,indent=2)+'\n').encode())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'configs/eval_100.json')
    parser.add_argument('--seed',type=int,default=20261030)
    parser.add_argument('--allow-partial',action='store_true',help='Explicitly mark sampling from downloaded prefixes, not a full-split uniform sample')
    parser.add_argument("--exclude-manifest",action="append",type=Path,default=[],help="Exclude all trajectory groups from these development/previous manifests")
    args=parser.parse_args()
    metadata=json.loads((ROOT/'configs/datasets.json').read_text())
    previous=json.loads(args.output.read_text()) if args.output.exists() else None
    if previous and previous['seed']!=args.seed: raise ValueError('Use a different output file for a new seed')
    excluded={e["trajectory_sha256"] for file in args.exclude_manifest for e in json.loads(file.read_text())["episodes"]}
    sources={}; episodes=[]
    for i,split in enumerate(['val_seen','val_unseen']):
        full=args.data_root/'archives'/(split+'.tar')
        path=full if full.exists() else full.with_suffix('.tar.part')
        size=previous['sources'][split]['snapshot_bytes'] if previous else path.stat().st_size
        total=metadata['splits'][split]['size']
        if size<total and not args.allow_partial: raise ValueError('Archive incomplete; wait or explicitly use --allow-partial')
        digest=sha_prefix(path,size)
        if previous and digest!=previous['sources'][split]['snapshot_sha256']: raise ValueError('Frozen snapshot checksum changed')
        verified=size==total and digest==metadata['splits'][split]['sha256']
        if size==total and not verified: raise ValueError('Full archive checksum mismatch')
        rows=catalog(path,split,size)
        eligible=[row for row in rows if row["trajectory_sha256"] not in excluded]
        selected=choose(eligible,args.seed+i)
        excluded.update(row["trajectory_sha256"] for row in selected)
        materialize(path,selected,args.data_root)
        episodes.extend(selected)
        sources[split]=dict(snapshot_bytes=size,snapshot_sha256=digest,archive_bytes=total,
                            archive_sha256=metadata['splits'][split]['sha256'],archive_verified=verified,
                            catalog_episode_count=len(rows),sampling_scope='full_archive' if verified else 'downloaded_prefix')
        print(split,'catalog',len(rows),'selected',len(selected),'distinct trajectories',len({x['trajectory_sha256'] for x in selected}),flush=True)
    config=dict(schema_version=1,name='local_validation_100',manifest_kind='local_validation_sample',
        official_manifest_verified=False,dataset_revision=metadata['revision'],seed=args.seed,
        data_root='${WORLDNAV_DATA_ROOT}',sources=sources,episodes=episodes,
        model=dict(backend='lcvn_uni',checkpoint_manifest=None,model_action_frame='canonical_world',
                   initial_pose_policy='canonical_zero_experimental',max_steps=26,memory_bank=False),
        protocol=dict(max_actions=64,max_translation=2.46,max_abs_dyaw=6.29),
        evaluation=dict(scorer='public_demonstration',average_step_source='reference',failed_episodes='excluded_and_reported'))
    if args.exclude_manifest:config["excluded_manifests"]=[str(p) for p in args.exclude_manifest]
    content=(json.dumps(config,indent=2,ensure_ascii=False)+'\n').encode()
    save_unchanged(args.output,content)
    print('Manifest SHA256:',hashlib.sha256(content).hexdigest())


if __name__=='__main__': main()
