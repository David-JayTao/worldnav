"""Audit exact initial-image and image/instruction overlap between frozen manifests."""
import argparse,hashlib,itertools,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-root',type=Path,required=True)
 p.add_argument('--output',type=Path,default=ROOT/'reports/stage2_input_overlap_audit.json');args=p.parse_args()
 names=['eval_100.json','dev_12.json','eval_100_full_stage2.json','dev_24_full_stage2.json'];sets={}
 for name in names:
  pairs=[]
  for item in json.loads((ROOT/'configs'/name).read_text())['episodes']:
   folder=args.data_root/'samples'/item['split']/item['episode_id']
   image=hashlib.sha256((folder/'0.jpg').read_bytes()).hexdigest();assert image==item['image_sha256']
   instruction=json.loads((folder/'input.json').read_text())['instruction']
   pairs.append((image,hashlib.sha256(instruction.encode()).hexdigest()))
  sets[name]={'images':{a for a,b in pairs},'pairs':set(pairs)}
 result={a+' vs '+b:{'shared_initial_image_hashes':len(sets[a]['images']&sets[b]['images']),'shared_image_instruction_pairs':len(sets[a]['pairs']&sets[b]['pairs'])} for a,b in itertools.combinations(names,2)}
 content=json.dumps(result,indent=2)+'\n'
 if args.output.exists() and args.output.read_text()!=content:raise ValueError('Input overlap changed; inspect instead of overwriting evidence')
 if not args.output.exists():args.output.write_text(content)
 print('Verified exact image/input overlap:',json.dumps(result))
if __name__=='__main__':main()
