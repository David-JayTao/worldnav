"""Freeze the best nonbaseline prompt using only independent development scores."""
import json
from pathlib import Path
import hashlib


def main():
    summaries={v:json.loads(Path(f'runs/qwen_prompt_ablation/v{v}/summary.json').read_text()) for v in (1,2,3)}
    if any(s['completed_records']!=12 for s in summaries.values()):raise ValueError('All 12 development cases must finish for every prompt')
    scores={v:s['overall']['score_all_planned_failure_zero'] for v,s in summaries.items()}
    # A held-out paired test of the strongest candidate is retained even if V1 wins.
    selected=max((2,3),key=lambda v:(scores[v],-v))
    source=Path('configs/qwen_structured_v2.json' if selected==2 else 'configs/qwen_scale_v3.json')
    target=Path('configs/qwen_optimized_100.json');content=source.read_text()
    if target.exists() and target.read_text()!=content:raise ValueError('Selected config is already frozen; refusing reselection')
    if not target.exists():target.write_text(content)
    evidence=dict(development_scores=scores,selected_variant=selected,
        selected_beats_development_baseline=scores[selected]>scores[1],selection_metric='failure-zero mean Score on 12 independent development cases',
        formal_test_metrics_used=False,selected_config_sha256=hashlib.sha256(content.encode()).hexdigest())
    target=Path('runs/qwen_prompt_ablation/selection.json')
    if target.exists() and json.loads(target.read_text())!=json.loads(json.dumps(evidence)):
        raise ValueError('Selection evidence already exists and differs')
    target.write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence),flush=True)


if __name__=='__main__':main()
