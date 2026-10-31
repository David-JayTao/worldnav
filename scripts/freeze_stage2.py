"""Copy prior evidence into an exclusive, read-only, SHA256-indexed snapshot."""
from pathlib import Path
import hashlib,json,shutil,datetime,os
root=Path(__file__).resolve().parents[1]
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
target=root/'local_archive'/('stage2_frozen_'+stamp);target.mkdir(parents=True,exist_ok=False)
for name in ('runs','configs','src','scripts','tests','reports','docs','logs'):
 shutil.copytree(root/name,target/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
checks={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
index=target/'SHA256.json';index.write_text(json.dumps(checks,indent=2,ensure_ascii=False)+'\n')
report={'snapshot_name':target.name,'files':len(checks),'index_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),'mode':'exclusive copy; file mode 0444, directories 0555; original artifacts untouched','utc':stamp}
for p in target.rglob('*'):p.chmod(0o555 if p.is_dir() else 0o444)
target.chmod(0o555)
(root/'reports/stage2_freeze.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
