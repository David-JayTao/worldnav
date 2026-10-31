"""Independent final aggregation, report and data-state records; no model requests."""
import json,sys,re,hashlib,datetime,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from recompute_stage2 import recompute
from compare_experiments import compare

def read(p):return json.loads((ROOT/p).read_text())
def stripped(r):return {k:v for k,v in r.items() if k!='cases'}
def main():
 root=Path('/data1/worldnav-data');runs={'Base':ROOT/'runs/qwen_api_100case_baseline','V3':ROOT/'runs/qwen_api_100case_optimized','Candidate':ROOT/'runs/stage2_candidate_100'}
 result={'runs':{name:stripped(recompute(p,root)) for name,p in runs.items()},'old_Base_vs_V3':compare(runs['Base'],runs['V3']),'old_V3_vs_new':compare(runs['V3'],runs['Candidate'])}
 result['development']={name:stripped(recompute(ROOT/f'runs/stage2_dev_{name}',root)) for name in ['scale','stop','turn','structured','json','vision','vision8'] if (ROOT/f'runs/stage2_dev_{name}/summary.json').exists() and read(f'runs/stage2_dev_{name}/summary.json')['completed_records']==12}
 fullpaths={'Base':ROOT/'runs/stage2_full_base_100','V3':ROOT/'runs/stage2_full_v3_100','Candidate':ROOT/'runs/stage2_full_candidate_100'}
 if all((p/'summary.json').exists() and read(p/'summary.json')['completed_records']==100 for p in fullpaths.values()):
  result['full_control']={'runs':{n:stripped(recompute(p,root)) for n,p in fullpaths.items()},'paired':compare(fullpaths['Base'],fullpaths['Candidate']),'paired_V3_vs_candidate':compare(fullpaths['V3'],fullpaths['Candidate']),'independent_from_old_formal_and_dev':True}
 for field in ['old_Base_vs_V3','old_V3_vs_new']:
  result[field]={k:v for k,v in result[field].items() if k!='rows'}
 if result.get('full_control'):
  for field in ['paired','paired_V3_vs_candidate']:result['full_control'][field]={k:v for k,v in result['full_control'][field].items() if k!='rows'}
 log=(ROOT/'logs/stage2_tests.txt').read_text();m=re.search(r'Ran (\d+) tests',log);assert m and '\nOK\n' in log
 result['vision8_probe']=read('reports/stage2_vision8_probe.json') if (ROOT/'reports/stage2_vision8_probe.json').exists() else None
 result['vision_probe']=read('reports/stage2_vision_probe.json') if (ROOT/'reports/stage2_vision_probe.json').exists() else None
 new_runs=[p for p in (ROOT/'runs').glob('stage2_*') if p.is_dir() and (p/'api_config.json').exists()]
 confirmed=[];reserved=0
 for run in new_runs:
  reserved+=len(list((run/'logs/request_budget').glob('*.json')))
  confirmed.extend(a for p in (run/'raw_responses').glob('*.json') for a in json.loads(p.read_text()).get('attempts',[]))
 run_hashes={}
 for run in new_runs:
  files={str(p.relative_to(run)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['raw_responses','predictions','trajectories','cases','logs'] for p in sorted((run/folder).rglob('*')) if p.is_file() and p.name!='runner.lock'}
  for name in ['api_config.json','manifest.json','experiment.json']:
   if (run/name).exists():files[name]=hashlib.sha256((run/name).read_bytes()).hexdigest()
  index_path=ROOT/'outputs'/(run.name+'_SHA256.json');index_path.write_text(json.dumps(files,indent=2)+'\n')
  run_hashes[run.name]={'files':len(files),'index_sha256':hashlib.sha256(index_path.read_bytes()).hexdigest(),'manifest_sha256':files.get('manifest.json'),'config_sha256':files.get('api_config.json'),'prompt_file_sha256':files.get('logs/system_prompt.txt'),'request_prompt_sha256':json.loads((run/'experiment.json').read_text()).get('prompt_hash') if (run/'experiment.json').exists() else None,'source_snapshot_sha256':files.get('logs/source_snapshot.json'),'local_index':str(index_path.relative_to(ROOT))}
 (ROOT/'reports/stage2_run_hashes.json').write_text(json.dumps(run_hashes,indent=2)+'\n')
 result['new_round_usage']={'reserved_slots':reserved,'recorded_requests':len(confirmed),'unresolved_reserved_slots':reserved-len(confirmed),'reported_input_tokens':sum((a.get('raw_response',{}).get('usage') or {}).get('prompt_tokens',0) or 0 for a in confirmed),'reported_output_tokens':sum((a.get('raw_response',{}).get('usage') or {}).get('completion_tokens',0) or 0 for a in confirmed),'requests_without_reported_usage':sum(not (a.get('raw_response',{}).get('usage') or {}) for a in confirmed),'monetary_cost':None,'note':'Unresolved slots may or may not have reached provider; timeout/interrupted requests may still be billed. Tokens are provider-reported usage only, not assumed zero for missing records. No reused old inference counted as new.'}

 result['cpu_test_count']=int(m.group(1));result['checked_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 (ROOT/'reports/stage2_final_metrics.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 audits=sorted((ROOT/'outputs').glob('full_validation_audit_*.json'))
 fullaudit=[json.loads(p.read_text()) for p in audits if json.loads(p.read_text()).get('both_validation_splits_audited')]
 cfg=read('configs/datasets.json');splits={}
 if fullaudit:splits=fullaudit[-1]['splits']
 else:
  old=ROOT/'outputs/val_seen_full_audit_20261031.json'
  if old.exists():splits.update(json.loads(old.read_text()).get('splits',{}))
 current={s:{'downloaded_bytes':sum(p.stat().st_size for p in [root/'archives'/(s+'.tar'),root/'archives'/(s+'.tar.part')] if p.exists()),'expected_bytes':m['size'],'expected_sha256':m['sha256'],'complete_archive_exists':(root/'archives'/(s+'.tar')).exists()} for s,m in cfg['splits'].items()}
 dataset={'revision':cfg['revision'],'source':'https://huggingface.co/datasets/fly1113/LCVN','splits':splits,'download':current,'complete':bool(fullaudit) and all(splits[s]['image_pose_count_mismatches']==0 for s in cfg['splits']),'checked_at_utc':result['checked_at_utc'],'audit_source':str(audits[-1].relative_to(ROOT)) if audits else None}
 dataset['trajectory_group_audit']=read('reports/stage2_trajectory_groups.json') if (ROOT/'reports/stage2_trajectory_groups.json').exists() else None
 dataset['input_overlap_audit']=read('reports/stage2_input_overlap_audit.json')
 dataset['manifests']={}
 for p in ['configs/eval_100.json','configs/dev_12.json','configs/eval_100_full_stage2.json','configs/dev_24_full_stage2.json']:
  if (ROOT/p).exists():
   j=read(p);dataset['manifests'][p]={'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest(),'count':len(j['episodes']),'seed':j['seed'],'sources':j['sources'],'excluded_manifests':j.get('excluded_manifests',[]),'distinct_trajectory_groups':len({e['trajectory_sha256'] for e in j['episodes']}),'per_split':{split:{'count':sum(e['split']==split for e in j['episodes']),'instruction_styles':{str(style):sum(e['split']==split and e['instruction_style']==style for e in j['episodes']) for style in [0,1,2]}} for split in ['val_seen','val_unseen']}}
 if (ROOT/'configs/eval_100_full_stage2.json').exists():
  formal=read('configs/eval_100_full_stage2.json')['episodes'];old=read('configs/eval_100.json')['episodes'];dev=read('configs/dev_12.json')['episodes'];hashes=lambda es:{e['trajectory_sha256'] for e in es}
  assert len(hashes(formal))==100 and not (hashes(formal)&(hashes(old)|hashes(dev)))
  dataset['full_manifest_overlap_old_formal_or_dev']=0
  if (ROOT/'configs/dev_24_full_stage2.json').exists():
   extra=read('configs/dev_24_full_stage2.json')['episodes'];assert not hashes(extra)&(hashes(formal)|hashes(old)|hashes(dev))
   dataset['extra_dev_24_overlap_with_any_other_manifest']=0
 (ROOT/'reports/stage2_data_audit.json').write_text(json.dumps(dataset,indent=2,ensure_ascii=False)+'\n')
 text=['# WorldNav 第二阶段科研冲刺：完整实验报告','',f"证据更新时间（UTC）：{result['checked_at_utc']}。当前获分配GPU=0。API实测与CPU/Mock测试分开计数。这里零样本指请求无任务示例、无任务权重训练；开发集仍用于策略选择，不宣称开发过程没有标签监督。temperature=0也不保证云服务逐位确定性；服务端权重版本与训练数据不可独立核验，保存原始响应用于精确离线复算。",'','## 1. 冻结、复算与研究边界','','旧实验只读快照见 `stage2_freeze.json`，覆盖原始响应、动作、轨迹、清单、Prompt、源码和测试日志；完整SHA256索引在服务器 local_archive 对应目录。旧文件不修改。重算从逐case原始响应重新解析，与保存动作、轨迹及公开指标核对，并核验真实图片/元数据/轨迹组哈希。未发现原报告差异（浮点求和尾数差异小于1e-10）。','','Base和V3使用同100条输入；开发集与正式集轨迹哈希零交集。旧100、dev12、新100、dev24四清单之间的精确初始图片哈希和图片/指令组合交集均为0，见stage2_input_overlap_audit.json；这不是场景级独立性的证明。GT隔离由Observation边界、请求构造代码与持久化顺序测试验证；GT仅用于去重和落盘后的评测/可视化。旧正式集已被查看，本轮复用它比较新策略属于探索性结果。完整归档新清单独立排除旧正式集及开发集，是新的实验版本。','','## 2. 实验指标','','SR、Score使用计划分母，失败记零；ATE/RPE/F/H使用有效评估子集。另列有效子集SR和Score，禁止口径混用。公开逐例公式：`Score_i = 100 F_i (1+H_i)/2 × [0.70 + 0.10 SR_i + 0.10/(1+ATE_i) + 0.10/(1+RPE_i)]`，按计划样本求均值。SR只占括号中的一项，因此SR较高并不保证Score较高；实现固定在Track1 a52e43f的demonstration.py。','', '| 数据版本 / 实验 / 分组 | 有效/计划 | SR 分子/分母 | Score* | ATE | RPE | F | H | 有效Score | 有效SR |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 def append_rows(version,label,r):
  for group,g in [('Overall',r['overall']),*r['per_split'].items()]:
   m=g['valid_subset'];fmt=lambda k:f"{m[k]:.3f}" if k in m else 'NA'
   text.append(f"| {version}/{label}/{group} | {g['valid']}/{g['planned']} | {int(g['sr_numerator'])}/{g['planned']} | {g['Score_failure_zero']:.3f} | {fmt('ATE')} | {fmt('RPE')} | {fmt('full_route_fidelity')} | {fmt('heading_turn_fidelity')} | {fmt('Score')} | {fmt('SR')} |")
 for n,r in result['runs'].items():append_rows('旧前缀100',n,r)
 if 'full_control' in result:
  for n,r in result['full_control']['runs'].items():append_rows('新全归档100',n,r)
 text+=['','## 3. 开发集策略与选择','','预注册见 `stage2_preregistration.md`；原V3不变。所有方法先跑轨迹隔离的12例开发集，唯一候选由开发集失败记零Score决定。新策略的研究假设为分段尺度、终止子句、转弯事件以及显式路线编译；没有将全体动作统一乘常数。','', '| 方法 | 有效/12 | SR | Score | API 成功/请求 | JSON合法/请求 | 已报告输入/输出 Token | 累积API秒 |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for n,r in result['development'].items():
  g=r['overall'];text.append(f"| {n} | {g['valid']}/12 | {int(g['sr_numerator'])}/12 | {g['Score_failure_zero']:.3f} | {r['api_success_count']}/{r['request_count']} | {r['json_valid_response_count']}/{r['request_count']} | {r['input_tokens']}/{r['output_tokens']} | {r['latency_sum_seconds']:.1f} |")
 selection=read('reports/stage2_selection.json');text+=['',f"冻结候选：**{selection['selected']}**；开发集是否超过V3：{selection['selected_beats_V3_on_development']}。冻结时间（UTC）{selection['frozen_at_utc']}；配置SHA256 `{selection['config_sha256']}`。12例反复开发与多重候选选择造成选择偏差，不能外推。",'','Robust JSON使用原V3文本和response_format=json_object；单例真实图片请求返回合法结果。开发集实际出现1次HTTP400，请求接受性并不完全稳定；服务接受参数不等于确认强制schema或证明参数未被忽略。严格解析与有限重试没有放宽。结构化策略先产生地标、转角、距离和步幅，独立编译器严格细分到动作；非法字段、非有限值或超过64步均记失败，不截断、不补全、不伪装Stop。','','额外模型为官方明确支持图像输入的Qwen3-VL-32B-Instruct，经同SinapisAI真实RGB请求测试。它不参与Qwen3.8策略选型；若接口持续超时，将保留终止请求和未决预算记录并停止，不把未完成调用写成有效预测或0分模型对照。现场状态见stage2_vision_probe.json。模型身份依赖服务方路由，无法独立验证服务器权重。官方来源：https://huggingface.co/Qwen/Qwen3-VL-32B-Instruct。','','## 4. 配对统计']
 for label,p in [('旧Base→V3',result['old_Base_vs_V3']),('旧V3→新候选',result['old_V3_vs_new'])]+([('新完整归档Base→候选',result['full_control']['paired']),('新完整归档V3→候选',result['full_control']['paired_V3_vs_candidate'])] if 'full_control' in result else []):
  text+=['',f"- {label}：ΔScore={p['score_mean_delta']:.6f}；95% paired bootstrap CI={p['paired_bootstrap_95ci']}；改善/下降/持平={p['improved']}/{p['worsened']}/{p['tied']}；SR新增/丢失={p['sr_gained']}/{p['sr_lost']}；split差值={p['per_split']}。"]
 text+=['','配对分解（1为有效预测；贡献按计划100例分母；不把格式覆盖率变化当成纯几何改进）：','','| 对照 | 有效性变化 | 样本数 | 子集平均Score差 | 对计划均值的贡献 |','|---|---|---:|---:|---:|']
 for name,p in [('旧V3→Turn',result['old_V3_vs_new'])]+([('新V3→Turn',result['full_control']['paired_V3_vs_candidate'])] if result.get('full_control') else []):
  for pattern,g in p['coverage_decomposition'].items():
   delta='未测' if g['conditional_mean_delta'] is None else f"{g['conditional_mean_delta']:.3f}"
   text.append(f"| {name} | {pattern} | {g['cases']} | {delta} | {g['contribution_to_planned_mean']:.3f} |")
 text+=['','固定种子20261031、5000次配对重采样；区间只反映该样本集重采样波动，不保证完整验证集泛化。两种数据版本不混算、不直接相减。','','## 5. 深入诊断与真实案例','','`stage2_deep_analysis.json`包括Overall、seen/unseen、指令类型、参考步数区间、参考长度区间及文件名场景代理分组。输出分布包含动作数量、预测/参考长度、逐例长度比、终点/朝向误差、转弯次数与进度、动作幅度。场景前缀不是经过验证的物理场景标签；终点投影与转弯匹配仅为几何诊断代理，不能当语义错误真值。','','7组确定性案例规则覆盖最大改善、最大终点偏差、尺度异常、转弯偏差代理、停止越界代理、格式失败及SR与轨迹保真度不一致。`outputs/stage2_analysis/*_details.json`保留真实输入指令、GT、预测动作/轨迹、原始响应；各case指标在CSV/JSON中。PPT展示改善和失败两例，不仅展示成功。','','粒度敏感性CPU诊断：固定原V3的几何路径，只将平移二等分并保留最后半步转角；97例符合64步上限，终点/路径长度不变，但公开Score平均改变0.173、最大绝对改变2.923。该结果不是新模型实验，提示不能把粒度带来的所有Score变化等同于几何改善。原始诊断在outputs/stage2_metric_sensitivity.json。','','## 6. 数据与可信度','',f"固定来源revision `{cfg['revision']}`；下载实际字节、SHA256、归档与逐图审计见 `stage2_data_audit.json`。完整审计是否通过：**{dataset['complete']}**。没有下载完整训练集；旧前缀清单保留不覆盖。episode目录对应指令变体，图像统计为文件数而非去重物理视图数；底层轨迹内容哈希分组数量见stage2_trajectory_groups.json。",'','新完整归档清单按拥有三类指令的轨迹组抽样，50/50、风格17/17/16；排除旧正式集和开发集。此为符合资格轨迹组的分层局部100例，不能称为所有episode等概率样本或完整全量评测。','','## 7. 工程测试与异常','',f"{result['cpu_test_count']}项CPU/Mock测试通过，原72项无退化。测试名称与完整输出在本地 logs/stage2_tests.txt；API请求不计入单测。修复了单split smoke初始化遗漏、空split汇总除零以及旧matplotlib参数兼容问题。JSON smoke的汇总异常通过离线恢复解决，没有重新收费请求；完整异常日志保留。",'','长任务均有独立tmux、日志、有限预算和重试、原子case落盘及完成case跳过。开发单runner最多3并发，JSON smoke与之合计最多4；正式候选与全归档对照最多4并发并顺序执行，避免并发叠加。新进程结束日志保存CPU时间与峰值RSS。旧实验未覆写。','','## 8. 模型与资源阻塞','','Cosmos Reason2-8B: **NOT RUN / AUTHORIZATION UNAVAILABLE**。最新目录仍无Sinapis路由；NVIDIA匿名真实图片请求401，公开Space为PAUSED。无现有NVIDIA凭据，不将SinapisKey发到NVIDIA。GPU分配0，未启动CUDA或CPU完整8B推理。LCVN缺已验证任务checkpoint。详见 `stage2_model_access.json`；官方接口来源：https://docs.nvidia.com/nim/vision-language-models/1.7.0/examples/cosmos-reason2/api.html。','','## 9. 结论与下一步','','本轮正负结果均按开发集冻结后实测报告；重点关注结构化表示是否改善几何误差、是否牺牲有效率或朝向，而非只挑最高SR。下一步扩大独立开发集，在新测试版本验证地标约束的距离与终止规划；获取合法Cosmos endpoint和LCVN匹配权重后才进行对应模型实测。公开demo指标不是CodaBench比赛成绩。输入端GT隔离也不能证明通用模型预训练从未接触这些公开数据，当前无法核验预训练污染。','','## 10. 原始证据与复现','','- 旧实验：runs/qwen_api_100case_baseline、runs/qwen_api_100case_optimized。','- 新开发集：runs/stage2_dev_{scale,stop,turn,structured,json,vision}。','- 冻结选择与旧集候选：runs/stage2_selection.json、runs/stage2_candidate_100。','- 全归档新集：configs/eval_100_full_stage2.json、runs/stage2_full_{base,v3,candidate}_100。','- 数据下载和图像审计：logs/stage2_data_download.txt、outputs/full_validation_audit_*.json。','- 报告和演示：reports/stage2_*、WorldNav_科研冲刺汇报_20261031_v2.pptx。','- Git只提交脱敏汇总、源码、配置、报告和必要演示；原始预测、API响应、数据、私密日志仅服务器保存。']
 text+=['','## 最终失败样本（不补动作、不删除）','','| 实验 | Split | Episode ID | 分类 | 可公开的错误摘要 |','|---|---|---|---|---|']
 for run in [runs['V3'],*new_runs]:
  for path in sorted((run/'cases').glob('*.json')):
   row=json.loads(path.read_text())
   if not row.get('failure_category'):continue
   raw_path=run/'raw_responses'/path.name;attempts=json.loads(raw_path.read_text()).get('attempts',[]) if raw_path.exists() else []
   reasons=[a.get('parse_error') or ('HTTP '+str(a['http_status']) if a.get('http_status') else a.get('error_type','unknown')) for a in attempts if a.get('parse_error') or not a.get('api_success')]
   reason='；'.join(str(r)[:120].replace('|','/') for r in reasons) or '无可用预测；详见本地证据'
   text.append(f"| {run.name} | {row['split']} | {row['episode_id']} | {row['failure_category']} | {reason} |")
 deep=read('reports/stage2_deep_analysis.json')
 text+=['','## 深入解读：改善、代价与负结果','',f"旧100例新候选相对V3的失败记零Score差为{result['old_V3_vs_new']['score_mean_delta']:.3f}，95%配对区间{result['old_V3_vs_new']['paired_bootstrap_95ci']}。该结果只用于冻结策略的事后比较，不回头重选。",'','Structured在开发集SR为3/12，高于Turn的2/12，但Score更低，因此不能因SR较高而认定最好。Scale和Structured未超过固定V3；RobustJSON仅11/12有效并有HTTP400，没有可靠性改善证据。Turn和Stop开发分数提升仍需新样本检验。','', '| 策略 | ATE | RPE | F | H | 有效Score | 平均请求秒 |','|---|---:|---:|---:|---:|---:|---:|']
 for name,r in result['development'].items():
  m=r['overall']['valid_subset'];values=[f'{m[k]:.3f}' if k in m else '未测' for k in ['ATE','RPE','full_route_fidelity','heading_turn_fidelity','Score']];text.append('| '+name+' | '+' | '.join(values)+f" | {r['latency_sum_seconds']/r['request_count']:.2f} |")
 text+=['',f"几何诊断共同有效子集：{deep['paired_common_valid_count']}例（所有展示方法均有有效预测的交集），用于降低失败子集不同造成的描述性偏差。该子集不替代计划分母正式指标。",'','| 方法 | 预测步数 | 参考步数 | 预测长度 | 参考长度 | 逐例长度比均值 | 终点误差 | 朝向误差rad | 转弯进度代理 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for name,g in deep['paired_common_valid'].items():
  m=g['valid_subset_means'];text.append('| '+name+' | '+' | '.join(f"{m[k]:.3f}" for k in ['predicted_steps','reference_steps','predicted_length','reference_length','path_length_ratio','endpoint_error','heading_error','turn_progress_proxy'])+' |')
 if result.get('full_control'):
  increment=result['full_control']['paired_V3_vs_candidate'];text+=['',f"新集Turn相对V3差值为{increment['score_mean_delta']:.3f}，区间{increment['paired_bootstrap_95ci']}跨零，不能宣布稳定提升，也不能据此宣称已证明显著退步；当前继续保留V3参照，不推广Turn为新最佳。"]
  p=result['full_control']['paired'];text+=['',f"新完整归档100例Base→候选：ΔScore={p['score_mean_delta']:.3f}，CI={p['paired_bootstrap_95ci']}。它与旧集不同，不能将该差值当作V3→候选的提升，也不能用旧集Base分数作分母。"]
 text+=['','## 本轮API消耗与未决请求','',json.dumps(result['new_round_usage'],ensure_ascii=False,indent=2)]
 if result['vision8_probe']:text+=['','较小视觉模型的有界路由探测（先1例，再决定是否12例；45秒超时，无网络重试，不参与策略选择）：',json.dumps(result['vision8_probe'],ensure_ascii=False,indent=2),'官方视觉输入说明：https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct。API超时不是几何导航失败，不能用不可用路由的零覆盖证明模型能力差。']
 if result['vision_probe']:text+=['','额外视觉路线受控终止记录：',json.dumps(result['vision_probe'],ensure_ascii=False,indent=2)]
 (ROOT/'reports/stage2_experiment_report.md').write_text('\n'.join(text)+'\n')
 # Public list of test names/results, excluding any private execution logs.
 (ROOT/'reports/stage2_cpu_tests.txt').write_text(log)
 print('Final independent replay and report written. CPU tests:',result['cpu_test_count'],'full control:',bool(result.get('full_control')))
if __name__=='__main__':main()
