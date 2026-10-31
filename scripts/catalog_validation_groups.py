"""Count unique physical trajectory content groups, separately from style episodes."""
from pathlib import Path
import json,sys,collections
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_eval_manifest import catalog

def main():
 cfg=json.loads((ROOT/'configs/datasets.json').read_text());result={}
 for split,m in cfg['splits'].items():
  path=Path('/data1/worldnav-data/archives')/(split+'.tar')
  assert path.stat().st_size==m['size']
  rows=catalog(path,split,m['size']);groups=collections.defaultdict(set)
  for r in rows:groups[r['trajectory_sha256']].add(r['instruction_style'])
  result[split]={'instruction_specific_episode_dirs':len(rows),'distinct_trajectory_content_groups':len(groups),'groups_with_all_three_instruction_styles':sum(styles=={0,1,2} for styles in groups.values()),'style_episode_counts':dict(collections.Counter(r['instruction_style'] for r in rows)),'archive_sha256':m['sha256']}
  print(split,json.dumps(result[split]),flush=True)
 output={'dataset_revision':cfg['revision'],'splits':result,'note':'Image audit counts files (including repetition across instruction variants), not unique physical views. Group IDs use position/yaw content hashes.'}
 (ROOT/'reports/stage2_trajectory_groups.json').write_text(json.dumps(output,indent=2)+'\n')
if __name__=='__main__':main()
