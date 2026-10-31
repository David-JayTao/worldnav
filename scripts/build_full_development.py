"""Create 24 full-archive development cases excluding both tests and prior dev."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts')]
from build_eval_manifest import catalog,choose,materialize,save_unchanged,sha_prefix

def main():
 root=Path('/data1/worldnav-data');formal=json.loads((ROOT/'configs/eval_100_full_stage2.json').read_text())
 excluded=set()
 for name in ['eval_100.json','eval_100_full_stage2.json','dev_12.json']:
  excluded.update(e['trajectory_sha256'] for e in json.loads((ROOT/'configs'/name).read_text())['episodes'])
 rows=[]
 for i,split in enumerate(['val_seen','val_unseen']):
  path=root/'archives'/(split+'.tar');src=formal['sources'][split]
  assert sha_prefix(path,src['archive_bytes'])==src['archive_sha256']
  records=catalog(path,split,src['archive_bytes']);chosen=choose([r for r in records if r['trajectory_sha256'] not in excluded],20261102+i,count=12)
  excluded.update(r['trajectory_sha256'] for r in chosen);materialize(path,chosen,root);rows+=chosen
 result=dict(formal,name='full_archive_development_24',seed=20261102,episodes=rows,manifest_kind='independent_full_archive_development',excluded_manifests=['configs/eval_100.json','configs/eval_100_full_stage2.json','configs/dev_12.json'],purpose='additional independent validation, not used to reselect the already frozen candidate')
 out=ROOT/'configs/dev_24_full_stage2.json';save_unchanged(out,(json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode());print('Cases:',len(rows),'SHA256:',hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
