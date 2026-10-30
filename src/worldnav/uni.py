"""Experimental protocol adapter over pinned official Uni model classes.

Requires a verified trained checkpoint. This path has NOT yet been GPU validated.
"""
from pathlib import Path
import os
import random
import sys
import numpy as np
from PIL import Image
from .actions import adapt_action,decode_action,normalize_generation_output
from .checkpoint import verify_checkpoint
from .geometry import wrap_angle
from .protocol import validate
from .policy import BasePolicy

ROOT=Path(__file__).resolve().parents[2]


class UniPolicy(BasePolicy):
    def __init__(self,config,checkpoint_manifest):
        self.config=config
        if config.get('initial_pose_policy')!='canonical_zero_experimental':
            raise ValueError('Only explicit canonical-zero experimental pose policy is implemented')
        if config.get('memory_bank',False): raise ValueError('Memory-bank extension requires a separate validation; disabled')
        if not 1<=config['max_steps']<=64: raise ValueError('max_steps must be in 1..64')
        verified=verify_checkpoint(checkpoint_manifest)
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['TRANSFORMERS_OFFLINE']='1'
        import torch
        from transformers import AutoProcessor
        from peft import PeftModel,get_peft_model_state_dict
        from safetensors.torch import load_file
        sys.path.insert(0,str(ROOT/'vendor/LCVN/lcvn-uni'))
        from lcvnuni.wrapped_visualizer import AnoleforConditionalGeneration,split_token_sequence
        from scripts.prompt_builder import build_instruction_prompt
        self.torch=torch; self.split_tokens=split_token_sequence;self.prompt=build_instruction_prompt
        self.processor=AutoProcessor.from_pretrained(str(verified['adapter_dir']),image_seq_length=784,local_files_only=True,trust_remote_code=False)
        base,info=AnoleforConditionalGeneration.from_pretrained(str(verified['base_dir']),local_files_only=True,
            device_map='cuda:0',torch_dtype=torch.bfloat16,attn_implementation='flash_attention_2',
            codebook_sim='mse',output_loading_info=True)
        if any(info.get(k) for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):
            raise ValueError(f'Base weights did not load strictly: {info}')
        vocab=len(self.processor.tokenizer)
        if base.get_input_embeddings().weight.shape[0]!=vocab:
            if not any('embed_tokens' in k for k in verified['tensor_keys']):
                raise ValueError('Expanded vocabulary requires trained input embeddings; refusing random resized rows')
            base.resize_token_embeddings(vocab)
        weights=load_file(str(verified['adapter_dir']/'adapter_model.safetensors'),device='cpu')
        self.model=PeftModel.from_pretrained(base,str(verified['adapter_dir']),is_trainable=False,local_files_only=True)
        loaded=get_peft_model_state_dict(self.model)
        if set(loaded)!=set(weights): raise ValueError('Adapter tensor set mismatch; refusing partial/random adapter load')
        for key in weights:
            if not torch.equal(loaded[key].detach().cpu(),weights[key].to(dtype=loaded[key].dtype)):
                raise ValueError(f'Adapter tensor was not restored exactly: {key}')
        del weights,loaded
        self.base=base;self.model.eval()
        self.processor.tokenizer.padding_side='left'
        # Preserve the pinned official processor compatibility workaround locally.
        tokenizer=self.processor.tokenizer
        original=tokenizer._batch_encode_plus
        def batch_encode(*args,**kwargs):
            kwargs.pop('padding_side',None)
            return original(*args,**kwargs)
        tokenizer._batch_encode_plus=batch_encode
        self.processor.image_processor.size={'shortest_edge':448}
        self.processor.image_processor.crop_size={'height':448,'width':448}
        base.config.pad_token_id=tokenizer.pad_token_id
        base.model.vqmodel.config.resolution=448
        base.model.vqmodel.quantize.quant_state_dims=[448//2**(len(base.model.vqmodel.config.channel_multiplier)-1)]*2
        base.sketch_resolution=(448,448);base.image_token_num=784
        base.get_vis_codebook_sim()
        self.manifest_sha256=verified['manifest_sha256']
        self.device=base.device

    def _pixels_to_image(self,pixels):
        arr=self.processor.postprocess_pixel_values(pixels)[0].detach().cpu().numpy().transpose(1,2,0)
        return Image.fromarray(arr.astype(np.uint8))

    def _sanitize(self,image):
        batch=self.processor(text='<image>',images=image,return_tensors='pt').to(self.device)
        tokens=self.base.model.get_image_tokens(batch['pixel_values'].to(self.base.dtype))
        return self._pixels_to_image(self.base.decode_image_tokens(tokens))

    def predict(self,observation,seed):
        torch=self.torch
        random.seed(seed);np.random.seed(seed)
        torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark=False
        torch.cuda.reset_peak_memory_stats()
        actions=[];yaw=0.;texts=[];reason='max_steps'
        start=observation.image.convert('RGB').resize((256,256))
        with torch.inference_mode():
            current=self._sanitize(start)
            for step in range(self.config['max_steps']):
                prompt=self.prompt('Starting Point Coordinate: x=0.000, y=0.000, yaw=0.000\n',
                                   (-2.46,2.46),(-2.82,2.82),observation.instruction)
                batch=self.processor(text=[prompt],images=[start,current],return_tensors='pt').to(self.device)
                # Only start/current generated images enter the prompt; no unbounded history.
                limit=self.base.config.max_position_embeddings
                if batch['input_ids'].shape[-1]+834>limit:
                    raise ValueError('Prompt plus image generation exceeds model context; no silent truncation')
                # Pinned wrapper sets do_sample=True itself; avoid duplicate keyword.
                ids=normalize_generation_output(self.model.generate(**batch,max_new_tokens=834,num_beams=1,use_cache=True))
                row=ids[0]
                starts=(row==self.base.config.boi_token_id).nonzero().flatten()
                text_ids=row[:int(starts[0])] if len(starts) else row
                text=self.processor.tokenizer.decode(text_ids,skip_special_tokens=False).strip()
                for marker in ('</s>','<reserved08706>','<pad>'):
                    text=text.replace(marker,'').strip()
                texts.append(text)
                numeric=decode_action(text)
                if numeric is None: reason='stop';break
                local=adapt_action(numeric,self.config['model_action_frame'],yaw)
                validate({'split':'val_seen','episodes':[{'episode_id':'generated','actions':[local]}]},'val_seen')
                actions.append(local);yaw+=wrap_angle(numeric[2])
                if step==self.config['max_steps']-1: break
                parsed=self.split_tokens(ids,784,self.base.config.boi_token_id,self.base.config.eoi_token_id,
                                         ids.shape[-1],self.processor.tokenizer.pad_token_id)
                if not parsed['images']: raise ValueError('Future image decoding failed; not a successful Stop')
                generated=self._pixels_to_image(self.base.decode_image_tokens(parsed['images'][0]))
                current=self._sanitize(generated)
        torch.cuda.synchronize()
        return dict(actions=actions,termination=reason,decoded=texts,
                    peak_gpu_memory_mib=torch.cuda.max_memory_allocated()/1024**2)
