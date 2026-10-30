"""Freeze 12 independent cases: 6 per split, excluding every formal trajectory."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_eval_manifest import catalog,choose,materialize,save_unchanged,sha_prefix


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--formal',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();formal=json.loads(args.formal.read_text())
    excluded={e['trajectory_sha256'] for e in formal['episodes']};episodes=[]
    for index,split in enumerate(('val_seen','val_unseen')):
        source=formal['sources'][split];full=args.data_root/'archives'/(split+'.tar')
        path=full if full.exists() else full.with_suffix('.tar.part')
        if sha_prefix(path,source['snapshot_bytes'])!=source['snapshot_sha256']:
            raise ValueError('Frozen archive prefix changed')
        records=catalog(path,split,source['snapshot_bytes'])
        rows=choose([r for r in records if r['trajectory_sha256'] not in excluded],20261031+index,count=6)
        materialize(path,rows,args.data_root);episodes.extend(rows)
    assert not excluded.intersection(e['trajectory_sha256'] for e in episodes)
    result=dict(formal,name='independent_development_12',manifest_kind='independent_development_sample',
        seed=20261031,episodes=episodes,excludes_formal_trajectory_groups=True)
    save_unchanged(args.output,(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
    print('Independent development cases:',len(episodes))


if __name__=='__main__':main()
