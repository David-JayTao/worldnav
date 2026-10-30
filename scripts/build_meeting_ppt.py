"""Build editable Chinese slides and reports only from on-disk experiment evidence."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import sys
import os
from zoneinfo import ZoneInfo
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE,MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN,MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE,XL_LEGEND_POSITION

ROOT=Path(__file__).resolve().parents[1]
BLUE='244B70';TEAL='337D94';DARK='243447';GRAY='657488';PALE='EDF2F7';WHITE='FFFFFF';ORANGE='D48A43'
FONT='Noto Sans CJK SC'


def read(path,default=None):
    path=Path(path);return json.loads(path.read_text()) if path.exists() else default


def fmt(value,digits=3):return '—' if value is None else f'{value:.{digits}f}'


def write_derived(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_text()!=text:
        archive=ROOT/'local_archive/meeting_versions'/datetime.now().strftime('%Y%m%dT%H%M%S%f')
        archive.mkdir(parents=True,exist_ok=True);shutil.copy2(path,archive/path.name)
    path.write_text(text)


def box(slide,x,y,w,h,fill=PALE,line=None,radius=True):
    shape=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
    shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string(fill)
    shape.line.fill.background() if line is None else None
    if line:shape.line.color.rgb=RGBColor.from_string(line)
    return shape


def text(slide,x,y,w,h,value,size=20,color=DARK,bold=False,align=None):
    shape=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));frame=shape.text_frame
    frame.word_wrap=True;frame.margin_left=Inches(.03);frame.margin_right=Inches(.03)
    for i,line in enumerate(str(value).split('\n')):
        p=frame.paragraphs[0] if i==0 else frame.add_paragraph();p.text=line
        p.font.name=FONT;p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color)
        p.space_after=Pt(8)
        if align is not None:p.alignment=align
    return shape


def arrow(slide,x1,y1,x2,y2,color=TEAL):
    line=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x1),Inches(y1),Inches(x2),Inches(y2))
    line.line.color.rgb=RGBColor.from_string(color);line.line.width=Pt(2.5)
    # Explicit arrowhead is an editable native triangle.
    shape=slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE,Inches(x2-.08),Inches(y2-.08),Inches(.16),Inches(.16))
    shape.rotation=90 if x2>x1 else (270 if x2<x1 else (180 if y2>y1 else 0))
    shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string(color);shape.line.fill.background()


def table(slide,rows,x,y,w,h,widths=None,size=13):
    obj=slide.shapes.add_table(len(rows),len(rows[0]),Inches(x),Inches(y),Inches(w),Inches(h)).table
    if widths:
        for col,width in zip(obj.columns,widths):col.width=Inches(width)
    for r,values in enumerate(rows):
        for c,value in enumerate(values):
            cell=obj.cell(r,c);cell.text=str(value);cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string(BLUE if r==0 else (PALE if r%2 else WHITE))
            cell.margin_left=Inches(.08);cell.margin_right=Inches(.05);cell.vertical_anchor=MSO_ANCHOR.MIDDLE
            for p in cell.text_frame.paragraphs:
                p.font.name=FONT;p.font.size=Pt(size);p.font.color.rgb=RGBColor.from_string(WHITE if r==0 else DARK);p.font.bold=r==0
    return obj


def chart(slide,categories,series,x,y,w,h,title):
    data=CategoryChartData();data.categories=categories
    for label,values in series:data.add_series(label,values)
    c=slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,Inches(x),Inches(y),Inches(w),Inches(h),data).chart
    c.has_title=True;c.chart_title.text_frame.text=title
    c.chart_title.text_frame.paragraphs[0].font.size=Pt(14)
    c.has_legend=True;c.legend.position=XL_LEGEND_POSITION.BOTTOM;c.legend.font.size=Pt(10)
    for axis in (c.category_axis,c.value_axis):axis.tick_labels.font.size=Pt(10);axis.tick_labels.font.name=FONT
    for i,s in enumerate(c.series):s.format.fill.solid();s.format.fill.fore_color.rgb=RGBColor.from_string(BLUE if i==0 else TEAL)
    return c


def slide(prs,title,index,subtitle=''):
    s=prs.slides.add_slide(prs.slide_layouts[6]);s.background.fill.solid();s.background.fill.fore_color.rgb=RGBColor.from_string(WHITE)
    box(s,0,0,.18,7.5,BLUE,radius=False)
    text(s,.55,.28,12,.6,title,28,BLUE,True)
    if subtitle:text(s,.58,.98,12,.45,subtitle,13,GRAY)
    text(s,.6,7.12,11,.25,'WorldNav · API Zero-shot Policy · 官方公开 demo 指标；非 CodaBench 私有得分',9,GRAY)
    text(s,12,7.1,.6,.3,f'{index:02d}',11,GRAY,align=PP_ALIGN.RIGHT)
    return s


def sources():
    base=read(ROOT/'runs/qwen_api_100case_baseline/summary.json',{})
    opt=read(ROOT/'runs/qwen_api_100case_optimized/summary.json',{})
    dev={v:read(ROOT/f'runs/qwen_prompt_ablation/v{v}/summary.json',{}) for v in (1,2,3)}
    return base,opt,dev


def result_rows(base,opt):
    rows=[['实验 / Split','有效/计划','SR','ATE','RPE','F','H','Score*']]
    for label,summary in [('Base',base),('候选优化',opt)]:
        if not summary:continue
        groups=[('Overall',summary['overall'],summary['planned_cases'])]
        if label=='Base':groups.extend((s,summary['per_split'][s],50) for s in ('val_seen','val_unseen'))
        for split,g,n in groups:
            m=g['metrics_on_evaluated'];rows.append([label+' / '+split,f"{g['evaluated']}/{n}",fmt(m['SR']),fmt(m['ATE']),fmt(m['RPE']),fmt(m['full_route_fidelity']),fmt(m['heading_turn_fidelity']),fmt(g.get('score_all_planned_failure_zero',g['score_failure_zero']))])
    return rows


def build_reports(base,opt,dev,notes,test_log,data_root):
    now=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
    table_rows=result_rows(base,opt)
    md_table='\n'.join(['| '+' | '.join(row)+' |' for row in [table_rows[0],['---']*len(table_rows[0]),*table_rows[1:]]])
    dev_rows=['| Prompt | 完成/12 | SR（有效子集） | 失败记零 Score |','|---|---:|---:|---:|']
    for v,s in dev.items():
        if s:dev_rows.append(f"| V{v} | {s['completed_records']} | {fmt(s['overall']['metrics_on_evaluated']['SR'])} | {fmt(s['overall'].get('score_all_planned_failure_zero'))} |")
    selection=read(ROOT/'runs/qwen_prompt_ablation/selection.json',{})
    paired=read(ROOT/'runs/model_comparison/paired.json',{})
    diagnostics={name:read(ROOT/f'runs/{folder}/metrics/diagnostics.json',{}).get('overall',{})
                 for name,folder in [('Base','qwen_api_100case_baseline'),('候选版','qwen_api_100case_optimized')]}
    diag_rows=['| 实验 | 预测步数 | 参考步数 | 预测长度 | 参考长度 | 逐例长度比均值 | 终点误差 | 航向误差 rad |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,d in diagnostics.items():
        diag_rows.append('| '+name+' | '+' | '.join(fmt(d.get(k)) for k in ('predicted_action_count','reference_action_count','predicted_path_length','reference_path_length','path_length_ratio','endpoint_error','final_heading_error'))+' |')
    manifest=read(ROOT/'runs/qwen_api_100case_baseline/manifest.json')
    unseen_path=data_root/'archives/val_unseen.tar'
    if not unseen_path.exists():unseen_path=unseen_path.with_suffix('.tar.part')
    bytes_unseen=unseen_path.stat().st_size if unseen_path.exists() else 0
    case_rows=[]
    for p in sorted((ROOT/'runs/qwen_api_100case_baseline/cases').glob('*.json')):
        r=read(p);m=r.get('evaluation_metrics') or {}
        case_rows.append(f"| {r['episode_id']} | {r['split']} | {r['status']} | {fmt(m.get('SR'))} | {fmt(m.get('Score'))} | {fmt(r.get('api_latency_seconds'),2)} | {r.get('input_tokens')} / {r.get('output_tokens')} |")
    txt=f'''# WorldNav 任务与实验进展（2026-10-31）

生成时间：{now}。所有数字读取磁盘结果；实验若仍运行，以下只代表该时点快照。GPU 使用数量 0。

## 1. 比赛与任务

RoboWorld Track 1 WorldNav：输入一张初始第一视角 RGB 和自然语言导航指令；输出完整开放环轨迹，没有真实未来观察反馈。动作是当前机体坐标的前进 dx、左移 dy 与逆时针旋转 dyaw（rad）。先平移后转向，列表结束即终止；最多 64 步。平移模长上限 2.46 dataset coordinate units。全零动作不等于 Stop。

用通用视觉语言 API 建立 Zero-shot Policy，当前方法不是官方 LCVN-Uni，也不是机器人闭环实机测试。没有训练或本地 CUDA 加载。

## 2. 官方评测

直接使用固定 Track 1 demonstration.py 的 SR、ATE、RPE、F、H；按官方逐 episode 公式计算 Score。SR 是终点是否接近参考终点；ATE/RPE 衡量位置和步间增量误差；F 衡量整条路径，H 衡量朝向和转弯。公开 demo 与 CodaBench 私有 scorer 的同一性未证实。

## 3. 固定数据与隔离

正式本地对照集 50 seen + 50 unseen，100 个不同轨迹内容哈希；每 split 三类指令 17/17/16。清单源自冻结的官方归档前缀，不是完整验证集均匀抽样。原配置 SHA256：b7151e01e00f9b3588c44cae9d10de0d32bba8e3f7a17789b9187403af4eef44；本实验清单含原始指令、初始图片相对路径、固定交错顺序，SHA256：{base.get('dataset_manifest_sha256','未生成')}。

seen 整包已通过 SHA256 和逐图片审计：10,806 episode、189,873 图片、10,806 轨迹文件、0 个图片/位姿数量不匹配。unseen 当前 {bytes_unseen:,} / 20,311,838,720 bytes；后台继续续传，除非整包存在且校验完成，不宣称完整。

独立开发集 12 条（seen/unseen 各 6、各风格 2），排除正式集的全部轨迹组，种子 20261031。GT 用于清单去重/审计和保存预测后的评测；不进入 Prompt，不用于正式集动作尺度拟合。

## 4. 工程和测试

Policy 边界只含初始图像和指令；严格 JSON/动作校验；当前 yaw 坐标变换；原子且不覆盖的 case 落盘；tmux 持续任务；有限网络和格式重试；429 降并发；跳过已完成 case；每个实验保存配置、Prompt 哈希、manifest 哈希、源码文本快照和逐样本原始响应。

测试日志：`{test_log}`。具体名称及结果附后。模型请求是独立真实实验，不计入 Mock 测试。

## 5. Qwen 基础实验

模型 qwen/qwen3.8-27b，SinapisAI；温度 0；JSON-only。9 条匹配 Prompt、图像、指令和模型的有效先导预测复用，原先导目录保持原样。

实际状态：尝试 {base.get('attempted_cases',0)}，有效评估 {base.get('evaluated_cases',0)} / 100；请求成功率 {fmt(base.get('api_request_success_rate'))}，合法预测率 {fmt(base.get('legal_prediction_rate'))}，评估覆盖率 {fmt(base.get('evaluation_coverage_of_100'))}。当前实验新请求保留 {base.get('current_run_reserved_requests',0)} 个预算槽，继承请求 {base.get('inherited_requests',0)} 次；失败分类 {base.get('failure_counts',{})}。

{md_table}

*Score 为计划分母下失败/未完成记零的本地汇总；SR/ATE/RPE/F/H 表列为有效评估子集均值。未完成时，这不是已完成 100-case 的结果。有效子集 Score 均分：Base {fmt((base.get('overall') or {}).get('metrics_on_evaluated',{}).get('Score'))}；优化候选 {fmt((opt.get('overall') or {}).get('metrics_on_evaluated',{}).get('Score'))}。

API 累积延迟（可含客户端等待）{fmt(base.get('total_api_latency_seconds'),2)} 秒；已报告输入/输出 Token {base.get('total_input_tokens',0):,} / {base.get('total_output_tokens',0):,}。请求级错误 {base.get('request_failure_counts',{})}，中间格式失败 {base.get('intermediate_parse_failure_count','待刷新')} 次，合法率是有限重试后的最终 case 合法率。价格和账户实际账单未确认，不编造货币费用。用户本轮已明确授权超过先前 10 次请求上限；所有实验仍采用有限请求预算。

温度 0 不保证远程服务逐次生成完全一致，模型 alias 不能锁定服务端权重更新。这里可复现的是固定输入、配置与原始响应的完整离线解析和指标；响应 ID、服务方 usage 等原始元数据均保存，不声称服务端位级确定性。

## 6. Prompt 优化与配对比较

V1：原始零样本；V2：按可行路径、地标、转弯和停止位置进行内部结构化规划；V3：强化单位、坐标、动作粒度与保守尺度先验。未请求隐藏思维链，三个版本输出仅 JSON。

{chr(10).join(dev_rows)}

选择证据：`{json.dumps(selection,ensure_ascii=False)}`。选择只读取开发集，正式集指标不用于选参数；若非基础最优，仍明确报告候选未胜出，不改写负结果。候选正式集有效评估 {opt.get('evaluated_cases',0)} / 100，Prompt 版本 {opt.get('prompt_version','尚未冻结')}。

配对分析（正式集完成后计算）：Score 差值 {fmt(paired.get('score_mean_delta'))}，95% 配对 bootstrap 区间 {paired.get('paired_bootstrap_95ci','尚未计算')}；提升/下降/持平 {paired.get('improved','—')}/{paired.get('worsened','—')}/{paired.get('tied','—')}。数据键、图片/元数据哈希和指令均须一致才允许比较。小开发集和前缀抽样限制了可外推性。

## 7. Cosmos 核查与对照

现有 SinapisAI 模型目录 387 项，无 Cosmos 路由。NVIDIA_API_KEY、NVIDIA_NIM_API_KEY、NGC_API_KEY、NGC_CLI_API_KEY、HF_TOKEN 及用户标准配置路径均未发现可用授权。NVIDIA 模型目录列出 nvidia/cosmos-reason2-8b，但向该 endpoint 发送不带认证的真实图片请求返回 HTTP 401。未把 SinapisAI Key 发往 NVIDIA。

官方旧 build 页面当前跳转到 Cosmos3 Nano Reasoner，不能替换后声称跑过 Reason2-8B。没有新建账户、购买服务或使用不明 Key；Cosmos 有效推理 0 / 100，指标未测。对照表必须写“未运行/授权缺失”，不能填 0 分或冒充已完成。官方来源见 cosmos_report.md。

额外找到公开 `gulle1155/Cosmos-Reason2-8B` Space，源码固定官方权重 revision `a9fae2cf89dc64db96b12860417f0eb403013bb9`，但 Space runtime=PAUSED，主页和 /v1/models 均返回 HTTP 503；没有权限启动他人的 Space。该路线目前同样无法推理，已保留代码版本和状态证据。

## 8. 典型案例与误差分析

实际图像/指令/预测/GT 叠图位于 `runs/qwen_api_100case_baseline/figures/`。若没有 SR=1 样本，图注使用“有效预测中最佳”，不把生成成功当作导航成功。逐样本尺度、步数、总长度、终点误差、朝向误差和转弯统计位于 `metrics/diagnostics.json`；这些是事后诊断，不用于同一正式集校准。

开放环单图无法观察远端路径，通用 VLM 的尺度与停止位置估计可能失准。该解释是待检验假设；数值支持应以路径长度比和终点误差统计为准。API 失败与导航失败分别记录。

{chr(10).join(diag_rows)}

所有数值为已持久化预测的事后统计。逐例长度比的均值不等于总长度比。正式集的这些诊断仅用于解释，不用于调整本轮候选策略；V2/V3 在全量基础结果出现前已定义，选型只读取独立开发集。

## 9. 下一阶段

先完成并复算所有授权实验，冻结开发集选择，报告负结果和置信局限；获取 Cosmos 的现有 NVIDIA 授权凭据或团队托管 endpoint，使用同一清单完成对照。LCVN-Uni 另需导航训练 adapter、扩展 tokenizer/processor、准确基座版本与 GPU 分配。更大规模验证使用未来完整归档抽样，避免把当前前缀集外推为全数据结论。

## 10. 可复现命令

见 docs/REPRODUCTION.md。主要入口为 `scripts/run_api_sprint.sh`、`scripts/analyze_sprint.py`、`scripts/build_meeting_ppt.py`。原始响应、解析动作、轨迹、CSV 和运行源码快照均保存在 runs 下，仅本地保存；未自动推送 GitHub。

## 附录 A：逐 case 实际结果

| Episode ID | Split | 状态 | SR | Score | API 秒 | 输入 / 输出 Token |
|---|---|---|---:|---:|---:|---:|
{chr(10).join(case_rows)}

## 附录 B：CPU / Mock 测试

```text
{(ROOT/test_log).read_text() if (ROOT/test_log).exists() else '测试日志不存在，需补充核实'}
```
'''
    write_derived(ROOT/'reports/meeting_2026-10-31.md',txt)
    write_derived(ROOT/'reports/qwen_baseline_report.md','# Qwen 基础实验\n\n'+txt.split('## 5. Qwen 基础实验')[1].split('## 6. Prompt')[0])
    write_derived(ROOT/'reports/optimization_report.md','# Prompt 优化实验\n\n'+txt.split('## 6. Prompt 优化与配对比较')[1].split('## 7. Cosmos')[0])
    write_derived(ROOT/'reports/cosmos_report.md','# Cosmos Reason2-8B 接入核查\n\n'+txt.split('## 7. Cosmos 核查与对照')[1].split('## 8. 典型')[0]+'''\n\n一手来源：[NVIDIA 模型目录](https://integrate.api.nvidia.com/v1/models)、[官方 build 页面](https://build.nvidia.com/nvidia/cosmos-reason2-8b)、[NIM API 文档](https://docs.nvidia.com/nim/vision-language-models/1.7.0/examples/cosmos-reason2/api.html)。本地证据：logs/cosmos_route_check_20261031.json、logs/cosmos_nvidia_noauth_check_20261031.json。\n''')
    write_derived(ROOT/'reports/model_comparison.md','# 模型与 Prompt 对照\n\n'+md_table+'\n\nCosmos Reason2-8B：未运行，缺少可用路由/授权；不能作为零分模型加入排名。\n')
    write_derived(ROOT/'reports/meeting_2026-10-31_speaker_notes.md','# WorldNav 逐页讲稿（约 6～7 分钟）\n\n'+'\n\n'.join(f'## 第{i+1}页\n\n{n}' for i,n in enumerate(notes)))
    for folder in ('qwen_api_100case_baseline','qwen_api_100case_optimized'):
        run=ROOT/'runs'/folder
        if run.exists():write_derived(run/'report.md',txt)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'reports/WorldNav_阶段进展汇报_20261031.pptx')
    p.add_argument('--data-root',type=Path,default=Path(os.getenv('WORLDNAV_DATA_ROOT','/data1/worldnav-data')))
    p.add_argument('--test-log',default='logs/tests_sprint_20261031.log');args=p.parse_args()
    base,opt,dev=sources();prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    manifest=read(ROOT/'runs/qwen_api_100case_baseline/manifest.json');first=manifest['episodes'][1]
    data_root=args.data_root;initial=data_root/'samples'/first['split']/first['episode_id']/'0.jpg'
    notes=[]
    s=slide(prs,'WorldNav：视觉语言导航任务与实验进展',1)
    text(s,.7,1.8,7.3,1.3,'看一张图，听一句指令\n预测机器人接下来怎么走',32,BLUE,True)
    text(s,.75,3.6,7,1.2,'RoboWorld 2026 · Track 1\nAPI-based Zero-shot Policy Evaluation',20,GRAY)
    text(s,.75,5.7,7,.7,'2026年10月31日 · 团队内部科研汇报',17,GRAY)
    s.shapes.add_picture(str(initial),Inches(8.7),Inches(2),width=Inches(3.9))
    notes.append('今天先用三页介绍 WorldNav 是什么，再汇报我们实际完成的工程和模型实验。任务的关键是，机器人只能看一张起始图片，然后根据一句自然语言指令，预测接下来整段路线。我们使用远程视觉语言 API 建立零样本策略，所以本地没有 GPU 也可以开展实验。但这条路线不是官方 LCVN 模型复现，下面会把二者明确区分。')
    s=slide(prs,'比赛任务是什么？',2,'开放环导航：开始时看一次，后续没有真实环境反馈')
    s.shapes.add_picture(str(initial),Inches(.7),Inches(1.8),width=Inches(5.3))
    box(s,6.5,1.8,6,3.8);text(s,6.8,2.05,5.4,.8,'“沿砾石小路直行，在步道尽头停下”',20,BLUE,True)
    text(s,6.8,2.95,5.2,.8,first['instruction'],13,GRAY)
    text(s,6.8,4.05,5.2,1.35,'视觉：哪一条路可通行？\n语言：往哪里走、在哪里停？\n规划：把描述变成一整段动作。',18)
    text(s,.8,6.2,11.8,.5,'难点：只看得到起点，却要推断远处的路线、距离和停止位置。',20,TEAL,True)
    notes.append('可以把任务想象成：我们把机器人放在一条小路或走廊里，只给它眼前这一帧，再告诉它往前走、经过一个地标、向右转、到某处停止。模型既要看懂环境，也要理解指令中的先后关系。开放环的意思是，走起来以后，它不会获得真实的新图片来纠正错误。因此，开始时对距离或者转弯位置的一点误判，可能沿着整条路线累积。')
    s=slide(prs,'输入与输出：预测的是轨迹，不是图片描述',3)
    box(s,.7,1.7,3.3,4.4);text(s,.95,1.95,2.8,.5,'输入',24,BLUE,True)
    text(s,.95,2.8,2.8,2.7,'一张初始 RGB\n一条导航指令\n\n无终点坐标\n无真实未来帧',22)
    arrow(s,4.15,3.7,5.1,3.7)
    box(s,5.3,1.7,7.2,4.4);text(s,5.6,1.95,6.5,.5,'输出完整动作序列 [dx, dy, dyaw]',23,BLUE,True)
    arrow(s,7.1,4.7,7.1,3.1);text(s,6.9,2.55,1.8,.4,'前进 dx',16)
    arrow(s,7.1,4.7,5.95,4.7);text(s,5.7,5.05,1.8,.4,'左移 dy',16)
    text(s,8.1,3.1,3.7,2.5,'↶ 正 yaw：左转\n每一步用当前机体坐标\n先平移，再转向\n列表结束即停止',19)
    text(s,.8,6.45,11.8,.4,'最多 64 步；每步平移模长 ≤ 2.46 数据单位，yaw 使用弧度。示意图不代表实验轨迹。',14,GRAY)
    notes.append('模型的输入始终只有图像和指令。输出是一个数值列表，每一项有三个量：向前移动多少、向左移动多少，以及朝向改变多少。这里的坐标随机器人当前朝向变化，不能把世界坐标的位移直接填进来。一条动作先执行平移，再更新角度。模型自己决定输出多少步，列表结束就表示路线结束，而不是把全零动作当作一个特殊停止标记。')
    s=slide(prs,'比赛如何评价？不仅看有没有到终点',4)
    rows=[['指标','通俗解释','方向'],['SR','最后有没有到参考目标附近','越高越好'],['ATE / RPE','路线位置误差 / 每步移动误差','越低越好'],['F','整条路径的形状和完整性','越高越好'],['H','朝向和转弯位置、方向是否吻合','越高越好'],['Score','逐样本组合上述指标后平均','越高越好']]
    table(s,rows,.7,1.6,11.9,3.9,[2.1,7.7,2.1],18)
    box(s,.8,5.9,11.7,.7);text(s,1,6.03,11.2,.4,'调用官方公开 demonstration.py；不宣称等同于 CodaBench 私有评分环境。',17,TEAL,True)
    notes.append('只走到终点附近还不够，比赛还关心整条路线是否正确。SR 是终点成功率；ATE 和 RPE 分别看位置和步间移动误差；F 看完整路径，H 看朝向和转弯。最后逐样本组合成分数。我们直接调用固定版本的官方公开实现，没有自行改写这些指标。但服务器私有评分环境没有开放，所以现在应称为公开指标评测，不能直接当作排行榜成绩。')
    s=slide(prs,'我们的路线：通过远程 API 建立零样本策略',5)
    labels=['真实初始图像\n+ 导航指令','统一 Policy\nQwen API','严格动作解析\nJSON / 边界','机体动作积分\n重建轨迹','官方公开指标\n逐样本分析']
    for i,label in enumerate(labels):
        x=.65+i*2.55;box(s,x,2.2,2.2,1.5,BLUE if i==1 else PALE);text(s,x+.1,2.55,2,1,label,18,WHITE if i==1 else DARK,True,PP_ALIGN.CENTER)
        if i<4:arrow(s,x+2.22,2.95,x+2.48,2.95)
    text(s,.9,4.6,11.5,1.2,'Ground Truth 只在预测保存后用于评测\nCosmos 保留独立适配入口；当前未取得可用授权。',22,TEAL)
    text(s,.9,6.2,11.4,.4,'本机 GPU = 0；没有训练、CUDA 模型加载或 CPU 强跑 8B 模型。',16,GRAY)
    notes.append('我们的链路是先读取真实起始图像和指令，通过独立 Policy 调用模型，再严格检查它返回的动作，重建轨迹并调用官方指标。参考轨迹只在模型预测保存以后进入评分。每次请求、原始输出、预测动作和错误都单独保存，这样可以离线复算，不需要为了检查一个指标重复付费。当前真正运行的是 Qwen；Cosmos 是否能运行取决于对应路由和授权。')
    s=slide(prs,'工程和数据：让每一个结果都能追溯',6)
    cards=[('版本固定','官方 Track 1 / LCVN 使用固定提交'),('数据核验','seen 10,806 例、189,873 图通过审计'),('评测集固定','正式 50 + 50；开发集 6 + 6，轨迹无重叠'),('协议审计','局部坐标、yaw 时机、零动作、64 步'),('实验可恢复','tmux / 有限重试 / 原子落盘 / 跳过完成例'),('测试与安全','CPU / Mock 回归；密钥和原始结果不入 Git')]
    for i,(a,b) in enumerate(cards):
        x=.75+(i%2)*6.2;y=1.7+(i//2)*1.55;box(s,x,y,5.8,1.28);text(s,x+.2,y+.12,5.3,.4,a,21,BLUE,True);text(s,x+.2,y+.65,5.3,.5,b,15)
    notes.append('工程方面，我们保留了原来的九条流程实验，并固定官方代码版本。完整 seen 验证集已经通过哈希、图片解码和轨迹数量检查。当前对照集固定为一百条，开发集另外取十二条，并排除相同轨迹。需要说明，一百条来自冻结归档前缀，便于复用先导结果，它不是完整验证集均匀随机抽样。测试和运行记录保证结果可以追溯，但工程测试通过本身不等于模型性能提高。')
    s=slide(prs,'真实实验结果：完成多少，就报告多少',7,
        f"Base 有效 {base.get('evaluated_cases',0)}/100 · 优化候选有效 {opt.get('evaluated_cases',0)}/100 · Cosmos 未运行")
    table(s,result_rows(base,opt),.65,1.6,12.05,2.7,size=12)
    series=[]
    for label,summary in [('Base',base),('候选优化',opt)]:
        if summary:series.append((label,[summary['per_split'][sp].get('score_all_planned_failure_zero',0) for sp in ('val_seen','val_unseen')]))
    chart(s,['Seen','Unseen'],series,.8,4.5,6.5,2.3,'Score：计划分母下失败 / 未完成记零')
    text(s,7.6,4.8,4.8,1.6,'* SR / ATE / RPE / F / H：有效评估子集\n* Score：计划分母，失败记零\n* Cosmos 未运行 ≠ 0 分\n* 未完成快照不能写成 100 例完成',14,GRAY)
    notes.append(f"现在磁盘中的真实状态是：基础版有效评估 {base.get('evaluated_cases',0)} 条，优化候选有效评估 {opt.get('evaluated_cases',0)} 条。表中同时展示有效预测的条件指标，以及按计划分母把失败记零的分数。我们没有把 API 成功当作导航成功，也没有从分母中偷偷删掉失败。Prompt 选择只基于独立开发集，最终再在相同的一百条上做配对比较。即使优化没有提升，也会保留这个负结果。")
    s=slide(prs,'典型案例：看懂场景，仍可能走错距离与转弯',8)
    fig_dir=ROOT/'runs/qwen_api_100case_baseline/figures';idx=read(fig_dir/'index.json',{})
    chosen=fig_dir/('navigation_success.png' if idx.get('navigation_success_count',0)>0 else 'best_valid_prediction.png')
    if chosen.exists():s.shapes.add_picture(str(chosen),Inches(.65),Inches(1.55),width=Inches(12.0))
    else:text(s,.9,2,11,2,'轨迹图尚未生成；不使用人工构造轨迹冒充模型输出。',22)
    notes.append('这里展示的初始图片、导航指令和两条曲线全部来自真实样本。蓝线是仅在评测阶段读取的参考轨迹，橙线是 API 输出动作积分得到的预测。即使路径的大方向看起来合理，转弯发生得过晚、总距离偏大或者停止位置不准确，都可能导致 SR 为零。若这页标题使用“最佳有效预测”，它只表示有合法输出，不代表已经导航成功。')
    s=slide(prs,'问题与分析：区分工程错误、模型误差和资源阻塞',9)
    bd=read(ROOT/'runs/qwen_api_100case_baseline/metrics/diagnostics.json',{}).get('overall',{})
    od=read(ROOT/'runs/qwen_api_100case_optimized/metrics/diagnostics.json',{}).get('overall',{})
    diag_table=[['事后诊断（均值）','Base','候选版']]
    for label,field in [('预测动作数','predicted_action_count'),('参考动作数','reference_action_count'),('逐例路径长度比','path_length_ratio'),('终点误差（数据单位）','endpoint_error'),('最终朝向误差（rad）','final_heading_error')]:
        diag_table.append([label,fmt(bd.get(field)),fmt(od.get(field))])
    table(s,diag_table,.7,1.7,7,3.9,[3.5,1.75,1.75],17)
    box(s,8.1,1.7,4.5,4.6);text(s,8.35,2,4,3.9,'如何理解这些数字？\n\n步数少，不一定走得短。\n尺度、转弯和停止位置都重要。\n\n正式集仅做事后解释，\n参数选择只使用开发集。',18,BLUE)
    text(s,.8,6.25,11.8,.5,'资源阻塞独立记录：Cosmos 无授权且公开 Space 暂停；LCVN 缺任务权重和 GPU。',15,GRAY)
    notes.append(f"我们把工程问题、模型误差和资源阻塞分开。基础版平均输出 {fmt(bd.get('predicted_action_count'),1)} 步，参考平均 {fmt(bd.get('reference_action_count'),1)} 步，但逐例路径长度比平均达到 {fmt(bd.get('path_length_ratio'),2)} 倍，说明步数少不等于走得短。尺度和停止位置偏差值得关注，转弯量也需要对照。这里是正式集事后解释，不用于同一正式集校准。候选策略已经先在独立开发集选定。Cosmos 授权和 LCVN 权重则是另一类资源问题，不能靠调 Prompt 解决。")
    s=slide(prs,'下一阶段：从可运行对照走向可信研究结论',10)
    steps=[('01','完成与复算','冻结基础版、候选版同一 100-case 对照'),('02','补齐 Cosmos','取得现有授权 endpoint；同清单、同指标'),('03','复现专用模型','获取 LCVN 训练产物与 GPU，先 3 例验证'),('04','扩大验证','完整归档抽样、更多场景、报告失败与局限')]
    for i,(n,a,b) in enumerate(steps):
        y=1.65+i*1.17;box(s,.8,y,.65,.65,BLUE);text(s,.85,y+.05,.55,.4,n,19,WHITE,True)
        text(s,1.7,y,3.1,.5,a,22,BLUE,True);text(s,4.9,y+.05,7.4,.6,b,19)
    notes.append('最后，最短推进路线是先把当前授权实验完整做完，冻结配置并离线复算，再补齐 Cosmos 的合法授权，避免更换模型后却声称完成了同一对照。专用 LCVN 路线需要作者训练产物和明确 GPU 分配，先用三条样本验证加载与动作，再扩大规模。团队讨论最需要明确的是 Cosmos 授权由谁提供、LCVN 权重由谁联系，以及算力何时可分配。研究结论将建立在相同数据、完整失败统计和可复现记录之上。')
    for s,note in zip(prs.slides,notes):s.notes_slide.notes_text_frame.text=note
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():
        archive=ROOT/'local_archive/meeting_versions'/datetime.now().strftime('%Y%m%dT%H%M%S%f');archive.mkdir(parents=True,exist_ok=True);shutil.copy2(args.output,archive/args.output.name)
    prs.save(args.output)
    build_reports(base,opt,dev,notes,args.test_log,args.data_root)
    evidence=dict(slides=len(prs.slides),base_evaluated=base.get('evaluated_cases',0),optimized_evaluated=opt.get('evaluated_cases',0),
        ppt_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),sources=['runs/qwen_api_100case_baseline/summary.json','runs/qwen_api_100case_optimized/summary.json'])
    (ROOT/'logs/meeting_build_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))


if __name__=='__main__':main()
