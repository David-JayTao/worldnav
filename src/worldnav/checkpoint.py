"""Fail-closed local checkpoint audit; never downloads or creates an adapter."""
import hashlib
import json
from pathlib import Path
import re
import struct


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def tensor_header(path):
    with path.open('rb') as stream:
        raw=stream.read(8)
        if len(raw)!=8: raise ValueError('Invalid safetensors file')
        length=struct.unpack('<Q',raw)[0]
        if length>100*1024**2: raise ValueError('Excessive safetensors header')
        return json.loads(stream.read(length))


def verify_checkpoint(path):
    if not path: raise ValueError('Missing trained checkpoint manifest; base Anole is not LCVN-Uni')
    path=Path(path).resolve()
    if not path.is_file(): raise ValueError('Checkpoint manifest file does not exist')
    cfg=json.loads(path.read_text())
    for key in ('source_url','base_revision','training_checkpoint_id'):
        if not cfg.get(key): raise ValueError(f'Missing checkpoint provenance: {key}')
    if not re.fullmatch(r'[0-9a-f]{40}',cfg['base_revision']): raise ValueError('Base revision must be a pinned commit SHA')
    roots={k:(path.parent/cfg[k+'_dir']).resolve() for k in ('base','adapter')}
    listed={}
    for item in cfg.get('files',[]):
        role=item['role'];rel=Path(item['path'])
        if role not in roots or rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe checkpoint file path')
        target=(roots[role]/rel).resolve()
        if not target.is_relative_to(roots[role]): raise ValueError('Checkpoint symlink escapes root')
        expected=item['sha256']
        if not re.fullmatch(r'[0-9a-f]{64}',expected): raise ValueError('Every checkpoint file requires SHA256')
        if not target.is_file() or sha256(target)!=expected: raise ValueError(f'Checkpoint file missing/hash mismatch: {role}/{rel}')
        listed[role,str(rel)]=target
    required={'base':['config.json','model.safetensors.index.json'],
              'adapter':['adapter_config.json','adapter_model.safetensors','tokenizer.json','tokenizer_config.json','preprocessor_config.json']}
    for role,names in required.items():
        for name in names:
            if (role,name) not in listed: raise ValueError(f'Missing verified file: {role}/{name}')
    index=json.loads(listed['base','model.safetensors.index.json'].read_text())
    for shard in set(index['weight_map'].values()):
        if ('base',shard) not in listed: raise ValueError(f'Base shard not verified: {shard}')
    # Every config/tokenizer file consumed by from_pretrained must be hashed as well.
    for role,root in roots.items():
        for file in root.iterdir():
            if file.is_file() and file.suffix in ('.json','.model','.safetensors') and (role,file.name) not in listed:
                raise ValueError(f'Unverified loadable file: {role}/{file.name}')
        if any(root.glob('*.bin')): raise ValueError('Use verified safetensors, not pickle model .bin files')
    ac=json.loads(listed['adapter','adapter_config.json'].read_text())
    if ac.get('peft_type')!='LORA': raise ValueError('Expected a trained LoRA adapter')
    declared_base=ac.get('base_model_name_or_path','')
    if declared_base not in {cfg.get('base_repo'),str(roots['base'])}:
        raise ValueError('Adapter base identity does not match checkpoint manifest')
    keys=tensor_header(listed['adapter','adapter_model.safetensors'])
    if not any('lora_A' in k for k in keys) or not any('lora_B' in k for k in keys):
        raise ValueError('Adapter has no trained LoRA tensors')
    if not any('lm_head' in k for k in keys): raise ValueError('Trained navigation output head missing')
    return dict(config=cfg,base_dir=roots['base'],adapter_dir=roots['adapter'],
                tensor_keys=keys,manifest_sha256=sha256(path))
