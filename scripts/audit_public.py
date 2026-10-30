"""Audit staged blobs before a public commit/push. Does not print secret values."""
from pathlib import PurePosixPath
import re
import subprocess
import sys

BLOCKED_SUFFIX={'.pkl','.jpg','.jpeg','.tar','.zip','.pt','.pth','.bin','.ckpt','.safetensors','.pem','.key','.log'}
BLOCKED_ROOT={'data','outputs','logs','local_archive','.venv','.cache','wandb'}
PATTERNS=[rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{20,}',
          rb'github_pat_[A-Za-z0-9_]{30,}',rb'hf_[A-Za-z0-9]{20,}',rb'sk-[A-Za-z0-9_-]{24,}',
          rb'/home/[A-Za-z0-9_-]+/',rb'/data/[A-Za-z0-9_-]+/(?:miniconda|\.ssh)',
          rb'https?://[^\s/]+:[^\s/@]+@',rb'(?:10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3})']


def audit_blob(name,content):
    path=PurePosixPath(name);problems=[]
    if path.parts[0] in BLOCKED_ROOT or path.suffix in BLOCKED_SUFFIX or '.env'==path.name:
        problems.append('excluded artifact type')
    if len(content)>1024*1024:problems.append('blob exceeds 1 MiB; needs explicit review')
    for index,pattern in enumerate(PATTERNS):
        if re.search(pattern,content):problems.append(f'sensitive/path pattern {index}')
    return problems


def main():
    entries=subprocess.check_output(['git','ls-files','--stage','-z']).split(b'\0')
    issues=[];count=0
    for entry in entries:
        if not entry:continue
        info,name=entry.split(b'\t',1);mode,sha,stage=info.split()
        if mode==b'160000':continue
        name=name.decode();content=subprocess.check_output(['git','cat-file','blob',sha.decode()])
        count+=1
        issues.extend(f'{name}: {reason}' for reason in audit_blob(name,content))
    if issues:
        print('\n'.join(issues));return 1
    print(f'PASS: {count} staged files audited; no forbidden artifact/path/token patterns found.');return 0


if __name__=='__main__':sys.exit(main())
