"""Publish only reviewed derived artifacts and refresh status from final evidence."""
from pathlib import Path
import json,shutil,re,datetime
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/name).read_text())
def prepend(path,body):
 p=ROOT/path;old=p.read_text();old=re.sub(r'<!-- STAGE2_FINAL_START -->.*?<!-- STAGE2_FINAL_END -->\n*','',old,flags=re.S)
 p.write_text('<!-- STAGE2_FINAL_START -->\n'+body+'\n<!-- STAGE2_FINAL_END -->\n\n'+old)
def main():
 data=read('reports/stage2_final_metrics.json');audit=read('reports/stage2_data_audit.json');selection=read('reports/stage2_selection.json')
 assert audit['complete'] and set(data['full_control']['runs'])=={'Base','V3','Candidate'}
 ppt='WorldNav_科研冲刺汇报_20261031_v2.pptx';pdf=ppt.replace('.pptx','.pdf')
 assert (ROOT/'reports'/ppt).exists() and (ROOT/'reports'/pdf).exists()
 full=data['full_control'];paired=full['paired_V3_vs_candidate'];old=data['runs']['Candidate'];ci=paired['paired_bootstrap_95ci']
 verdict='区间跨零，未获得稳定增益证据' if ci[0]<=0<=ci[1] else ('该100例局部对照支持正增量' if ci[0]>0 else '该100例局部对照显示退步')
 dst=ROOT/'reports/stage2_figures';dst.mkdir(exist_ok=True)
 for p in (ROOT/'outputs/stage2_analysis').glob('*.png'):shutil.copyfile(p,dst/p.name)
 gallery=read('outputs/stage2_analysis/gallery.json')
 notes=['# 第二阶段成果入口','',f"核验时间（UTC）：{data['checked_at_utc']}。GPU分配0；以下为实际结果，不是实验计划。",'','## 关键结果','','新完整归档100例与旧前缀100例是不同版本，分别配对。SR/Score使用计划分母，失败记零；其他指标用有效子集。','', '| 数据版本 | 策略 | 有效/100 | SR | Score |','|---|---|---:|---:|---:|']
 for version,runs in [('旧前缀100',data['runs']),('新完整归档100',full['runs'])]:
  for name,r in runs.items():
   g=r['overall'];notes.append(f"| {version} | {'Turn' if name=='Candidate' else name} | {g['valid']}/100 | {100*g['SR_failure_zero']:.1f}% | {g['Score_failure_zero']:.3f} |")
 notes+=['',f"新集 Turn−V3：ΔScore={paired['score_mean_delta']:.3f}，95%配对区间[{ci[0]:.3f}, {ci[1]:.3f}]；**{verdict}**。区间仅反映相应局部100例重采样，不是全量验证或CodaBench成绩。",'','## 交付文件','',f'- [13页可编辑PPT]({ppt})、[PDF]({pdf})。','- [完整实验报告](stage2_experiment_report.md)、[逐页中文讲稿](stage2_speaker_notes.md)。','- [PPT来源与口径](stage2_ppt_sources.md)、[最终独立重算JSON](stage2_final_metrics.json)。','- [数据完整性](stage2_data_audit.json)、[轨迹组口径](stage2_trajectory_groups.json)。','- [服务器初始审计](server_audit_20261031.md)、[旧快照](stage2_freeze.json)、[旧SHA清单](stage2_frozen_sha256.json)、[新运行证据哈希](stage2_run_hashes.json)。',f"- [{data['cpu_test_count']}项CPU/Mock完整测试名称和结果](stage2_cpu_tests.txt)。",'- [Cosmos授权核查](stage2_model_access.json)、[LCVN任务产物复核](stage2_lcvn_checkpoint.md)。','- [32B视觉路由受控停止](stage2_vision_probe.json)；较小视觉模型探测见最终实验报告。','','## 完成与未完成','','已完成服务器审计、旧实验冻结与原始响应复算、两个验证集整包SHA和逐图片审计、五项开发集策略消融、旧100例Turn对照、新完整100例Base/V3/Turn实测和配对分析、真实案例图、新PPT/PDF及讲稿。',f"CPU/Mock共{data['cpu_test_count']}项通过；真实模型调用分别记录请求与已报告Token，超时/中断的计费和服务端完成状态不猜测。",'','额外24-case开发清单已准备，**未执行24-case推理**。Cosmos Reason2-8B未运行，缺可用授权；LCVN仍缺已验收任务产物与GPU。小模型服务探测不冒充正式100例baseline。旧V3两条格式失败及所有新失败保持原样。','','## 一页汇报要点','','- 输入：初始单图+指令；输出：完整开放环机体坐标动作。','- 已建立可追溯API流程、冻结清单、严格解析、独立评测和有界恢复。','- Base→V3的旧集改善真实存在；Turn的增量必须由独立同清单对照判断，不能只看12例开发集。','- 完整验证归档已通过审计；episode是指令变体，轨迹哈希组才是去重物理路径。','- 公开demo不等于私有CodaBench；单图尺度、停止与转弯仍有误差。','- 下一步使用已准备24例独立开发清单进行确认，优先改进地标约束的分段距离与终止规划。','','## 团队需要讨论的问题','','1. 能否取得真正可用的Cosmos Reason2-8B托管endpoint或现有NVIDIA授权？','2. 谁负责向作者索取LCVN任务adapter、tokenizer/processor、基座版本和哈希？','3. 后续GPU如何明确分配，最小验收由谁负责？','4. 是否优先扩大独立开发集和几何诊断，避免继续对旧100例改Prompt？','5. 数据、模型服务、评测统计和科研汇报分别由谁长期维护？','','## 真实成功与失败案例','','图片为真实RGB与真实预测/GT的事后配对可视化，不作为模型输入。重复角色可能对应同一episode，选例规则和ID见完整分析JSON。','']
 for g in gallery:
  filename=Path(g['file']).name;notes+=[f"### {g['role']}：{g['case_key']}",'',f"![{g['role']}](stage2_figures/{filename})",'',g['instruction'],'']
 (ROOT/'reports/STAGE2_DELIVERY.md').write_text('\n'.join(notes).rstrip()+'\n')
 summary=f"## 第二阶段最终状态（2026-10-31）\n\n完整验证归档已审计：seen10,806 episode/189,873图片文件/3,602轨迹组；unseen4,500/79,689/1,500，图片与位姿数量不匹配0。{data['cpu_test_count']}项CPU/Mock通过。旧Turn99/100有效、SR19%、Score29.242；新完整100例见最终报告，新集Turn−V3={paired['score_mean_delta']:.3f}，{verdict}。Cosmos未运行，GPU分配0。24例独立开发清单准备不等于推理完成。\n\n[最新成果入口](../reports/STAGE2_DELIVERY.md)。后文保留历史快照，过时的下载/测试/推送描述不代表当前状态。"
 prepend('docs/PROJECT_STATUS.md',summary)
 prepend('docs/EXPERIMENT_PLAN.md','## 本轮已完成与下一步\n\n审计、数据下载、五项开发消融和两套正式局部对照已完成，不能再列作计划。下一步在新独立开发样本验证分段距离、停止语义和转弯事件；先取得合法模型服务和匹配LCVN任务权重再做对应推理。24例清单已准备、模型实验未执行。详见[最终交付](../reports/STAGE2_DELIVERY.md)。')
 prepend('README.md','## 最新第二阶段成果\n\n[完整交付入口](reports/STAGE2_DELIVERY.md)包含新旧两套100例对照、数据整包审计、策略负结果、13页PPT/PDF和讲稿。新完整集Turn−V3：'+f"{paired['score_mean_delta']:.3f}；{verdict}。"+'\n\nGPU分配仍为0，Cosmos未运行；CPU测试和真实模型推理分别记录。')
 prepend('reports/README.md','## 最新科研汇报\n\n请先查看[第二阶段完整交付](STAGE2_DELIVERY.md)。下方为之前阶段的历史成果。')
 execution={}
 for run in sorted((ROOT/'runs').glob('stage2_*')):
  p=run/'logs/process.json'
  if not p.exists():continue
  s=json.loads(p.read_text());entry={k:v for k,v in s.items() if k!='pid'}
  for field in ['started_unix','finished_unix']:
   if field in s:entry[field.replace('_unix','_utc')]=datetime.datetime.fromtimestamp(s[field],datetime.timezone.utc).isoformat()
  execution[run.name]=entry
 (ROOT/'reports/stage2_execution_summary.json').write_text(json.dumps(execution,indent=2)+'\n')
 print('Delivery index, public derived figures and current status refreshed.')
if __name__=='__main__':main()
