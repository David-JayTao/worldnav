"""Rebuild a 13-slide research presentation from verified local experiment evidence."""
import sys,json,hashlib,datetime,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_meeting_ppt import slide,text,box,arrow,table,chart,BLUE,TEAL,GRAY,DARK,WHITE
from pptx import Presentation
from pptx.util import Inches
from pptx.enum.text import PP_ALIGN


def read(path,default=None):
 p=ROOT/path;return json.loads(p.read_text()) if p.exists() else default

def picture(s,path,x,y,w=None,h=None):
 kwargs={}
 if w:kwargs['width']=Inches(w)
 if h:kwargs['height']=Inches(h)
 return s.shapes.add_picture(str(ROOT/path),Inches(x),Inches(y),**kwargs)

def build():
 data=read('reports/stage2_final_metrics.json');audit=read('reports/stage2_data_audit.json');deep=read('reports/stage2_deep_analysis.json');sel=read('reports/stage2_selection.json');paired=data['old_V3_vs_new'];oldpair=data['old_Base_vs_V3']
 base=data['runs']['Base'];v3=data['runs']['V3'];new=data['runs']['Candidate'];dev=data['development'];prs=Presentation();prs.slide_width=Inches(13.3333);prs.slide_height=Inches(7.5)
 notes=[];sources=[]
 def add(title,note,source,subtitle=''):
  s=slide(prs,title,len(prs.slides)+1,subtitle);s.notes_slide.notes_text_frame.text=note;notes.append(note);sources.append(source);return s
 def line(s,y,heading,body):
  text(s,.65,y,3,.45,heading,20,BLUE,True);text(s,3.8,y,8.8,.75,body,18)
 def metrics(r):
  g=r['overall'];m=g['valid_subset'];return [f"{g['valid']}/{g['planned']}",f"{100*g['SR_failure_zero']:.1f}%",f"{g['Score_failure_zero']:.3f}",f"{m['ATE']:.3f}",f"{m['RPE']:.3f}",f"{m['full_route_fidelity']:.3f}",f"{m['heading_turn_fidelity']:.3f}"]
 s=add('WorldNav：视觉语言导航的零样本策略评估与轨迹优化','今天汇报的是单图开放环导航的本地API实验。我们用通用视觉语言模型建立流程和参照，而不是复现官方专用导航模型。核心观察是，动作尺度与坐标约束的V3相比直接零样本输出，在旧100例上的Score由11.040提高到27.756，但只有98条有效预测，两条格式错误完整保留。这次进一步完成数据审计和分离的策略实验。接下来会逐步说明证据、统计口径和限制，不把公开demo指标当作排行榜成绩。','reports/stage2_final_metrics.json；固定旧100-case')
 text(s,.7,1.35,12,.5,'RoboWorld 2026 · Track 1',24,GRAY)
 text(s,.75,2.2,11.8,1,'Base 11.040  →  V3 27.756',40,BLUE,True)
 text(s,.8,3.45,11.7,.8,'单张初始图像 · 完整开放环轨迹 · 98/100 有效预测',24,TEAL,True)
 text(s,.8,4.55,11.6,1.2,'官方公开 demo 指标，本地实验\n本轮新增：尺度 / 停止 / 转弯 / 结构化路线编译 / JSON 可靠性对照',21)
 text(s,.8,6.25,11.6,.4,'当前获分配 GPU：0；真实模型调用均通过现有授权 API',16,GRAY)
 gallery=read('outputs/stage2_analysis/gallery.json');sample=gallery[0];detail=read('outputs/stage2_analysis/V3_details.json')[sample['case_key']];item=detail['item']
 s=add('任务定义：单图规划整段路线','任务只给起点的一张RGB和一条自然语言指令，要求一次输出整段动作。与闭环导航不同，机器人走出去之后模型收不到新的真实观察，因此看不到的拐角、尺度和终点都必须提前估计。页面上的照片和英文指令来自同一真实样本，而不是示意数据。停止并非额外系统替模型处理的事情，它由动作列表结束的位置决定。由此我们将研究重点放在尺度、停止位置和转弯时机。','outputs/stage2_analysis/gallery.json；真实样本0.jpg和input.json')
 image=Path('/data1/worldnav-data/samples')/item['split']/item['episode_id']/'0.jpg';s.shapes.add_picture(str(image),Inches(.7),Inches(1.5),width=Inches(5.5),height=Inches(3.7))
 text(s,6.6,1.6,6,.65,'初始 RGB + 自然语言指令',25,BLUE,True);arrow(s,6.7,2.6,11.8,2.6)
 text(s,6.7,3.05,5.8,1.45,'完整动作序列\n[[dx, dy, dyaw], …]',25,TEAL,True)
 text(s,6.7,4.5,5.8,1.1,'没有后续观察反馈\n需要同时决定路线与停止位置',21)
 text(s,.75,5.55,11.8,1.1,sample['instruction'],17)
 s=add('动作协议：先按当前机体平移，再更新朝向','每个动作包含向前dx、向左dy和逆时针角度dyaw。关键在于它们属于每一步的当前机体坐标，而不是固定世界坐标。一次动作先根据当前朝向完成平移，之后才更新yaw；如果要原地左转再前进，需要两个动作。图中是协议示意而不是实验预测。列表最多64项，每步平移模长不超过2.46数据单位。全零动作是静止的一步，不是停止标记，停止由列表结束表达。','src/worldnav/geometry.py、protocol.py；固定Track1协议')
 arrow(s,2.3,4.7,5.7,4.7,BLUE);arrow(s,2.3,4.7,2.3,1.9,TEAL);text(s,5.8,4.5,2,.5,'x：向前',21,BLUE);text(s,1.2,1.5,3,.5,'y：向左',21,TEAL)
 text(s,3.0,2.6,3.0,1.2,'+dyaw：左转\n单位：rad',22)
 line(s,5.5,'执行顺序','平移 → 更新 yaw → 下一动作使用新坐标系')
 text(s,8,1.65,4.6,3.5,'dx、dy：数据坐标单位\ndyaw：弧度\n动作数 ≤ 64\n平移模长 ≤ 2.46\n列表结束 = 停止',23,BLUE)
 s=add('实验设计：开发集选择，测试集对照','所有实验都固定模型、输入和动作协议。旧正式集是50个seen加50个unseen，来自已冻结的归档前缀，绝不是完整验证集均匀抽样。12例开发集在轨迹哈希级别与其隔离，原V3和本轮策略都只在开发集选择。我们也明确，旧正式集的误差已经被查看，因此本轮在它上面的新比较具有探索性。新完整归档清单如被评估，将单独列出，绝不把两个清单的分数混起来。GT只在保存预测之后进入评测。','configs/eval_100.json、dev_12.json；stage2_preregistration.md')
 line(s,1.6,'模型与服务','Qwen 3.8-27B；SinapisAI；temperature=0')
 line(s,2.55,'旧正式对照','100 条：50 seen + 50 unseen；冻结归档前缀')
 line(s,3.5,'独立开发集','12 条；seen/unseen 各 6；轨迹哈希零重叠')
 line(s,4.45,'预测输入隔离','模型只接收初始 RGB 和指令；GT 事后评分')
 line(s,5.4,'选择与局限','只按开发集选策略；旧正式集复用属于探索性对照')
 s=add('系统架构：从真实输入到可追溯评测','实验链路首先把RGB和指令封装为独立Observation，API策略不能拿到参考轨迹。直接策略返回动作JSON；结构化策略则返回地标和分段距离，通过独立编译器转换。所有输出都必须经过严格字段、数值与动作上限校验。我们先持久化原始响应和合法预测，然后读取GT，重建坐标轨迹并调用固定版本的官方公开评测。每条结果记录请求、Token、错误和配置哈希，已有case恢复时跳过，非法输出不会补零伪装成功。','run_qwen_api.execute_case；research_policy.py；trajectory_plan.py')
 labels=['RGB + 指令','API Policy','严格 JSON','动作校验','坐标变换','轨迹重建','公开评测','指标与案例']
 for i,label in enumerate(labels):
  col=i%4;row=i//4;x=.75+col*3.15;y=1.8+row*1.8;box(s,x,y,2.7,.85,fill='EDF4F8',radius=False);text(s,x+.12,y+.18,2.45,.5,label,21,BLUE,True)
  if col<3:arrow(s,x+2.72,y+.42,x+3.08,y+.42)
 arrow(s,11.55,2.7,11.55,3.15);arrow(s,11.55,3.15,2.1,3.15);arrow(s,2.1,3.15,2.1,3.58)
 text(s,.85,5.6,11.7,.9,'原始响应 → 预测落盘 → GT 评测\n配置、Prompt、Manifest、源码快照、请求数、Token、失败类别全部保留',20)
 s=add('Base：合法动作不等于可靠导航','Base的100条预测都能通过动作校验，但只有5条终点成功，总Score为11.040。表格分别展示seen和unseen，二者存在较大差异，不能只给总分。尺度诊断显示Base平均预测路径偏长，而路径形状和终点定位也不稳定。这个实验的价值是建立实际运行的参照与问题定位，而不是证明通用VLM已经解决导航。这里所有指标都来自原始响应独立重算，分母为固定100条，不是筛选成功样本之后计算。','stage2_recomputed_metrics.json；独立原始响应重算')
 table(s,[['分组','有效','SR','Score','ATE','RPE','F','H'],['Overall',*metrics(base)],*[[split,*metrics({'overall':g})] for split,g in base['per_split'].items()]],.7,1.6,12,2.15,size=16)
 text(s,.85,4.25,11.5,.75,'100/100 合法预测，导航成功 5/100',29,BLUE,True)
 text(s,.85,5.25,11.4,.9,'初步问题：尺度、路径形状与停止位置\n合法 JSON 是工程条件，SR / 轨迹保真度才描述导航表现。',21)
 s=add('开发集策略消融：从措辞约束走向显式路线表示','上一轮独立12例上，V1、V2和V3的Score依次是16.958、19.279和21.617，所以选择V3；并不是因为V3的SR最高。本轮保持V3不动，分别研究尺度、停止和转弯，并增加结构化路线编译和原生JSON参数对照。右表是实际完成的开发集结果，格式失败记零。结构化编译器只细分模型自己规划的距离，不访问GT，也不修补非法段。选择只读取开发集，但12例太少且被反复使用，因此结果是探索性证据。','stage2_selection.json；各stage2_dev运行；原V1/V2/V3开发集')
 c=chart(s,['V1','V2','V3'],[('旧开发集 Score',[read('reports/stage2_recomputed_metrics.json')['runs'][f'qwen_prompt_ablation/v{v}']['overall']['Score_failure_zero'] for v in (1,2,3)])],.65,1.6,4.8,3.4,'独立开发集（n=12）；Score')
 c.category_axis.has_title=True;c.category_axis.axis_title.text_frame.text='Prompt版本'
 c.value_axis.has_title=True;c.value_axis.axis_title.text_frame.text='失败记零 mean Score'
 rows=[['策略','有效/12','SR','Score']]
 for name,r in dev.items():
  g=r['overall'];rows.append([name,f"{g['valid']}/12",f"{g['sr_numerator']}/12",f"{g['Score_failure_zero']:.3f}"])
 table(s,rows,5.75,1.6,6.85,3.8,size=15)
 text(s,.85,5.65,11.5,.9,f"开发集选定：{sel['selected']}；是否超过 V3：{sel['selected_beats_V3_on_development']}\n主指标：失败记零 mean Score；小样本结果不作泛化保证。",19)
 s=add('配对结果：相同输入、显式失败分母','本页先看旧100例的配对比较。Base到V3提高16.716分，配对bootstrap区间约11.361到22.064，58条改善、15条下降、27条持平。V3的两条格式失败仍在100分母中记零，ATE等指标则来自98条有效子集，所以不能把两个口径混用。本轮新候选与V3的差异同样使用逐例配对，负结果也完整保留。若下方列出完整归档的新100例，它是不同样本的独立表，只能在那张新表内比较，不能拿它与旧集直接相减。','stage2_final_metrics.json；old_Base_vs_V3、old_V3_vs_new、full_control')
 table(s,[['旧100-case','有效','SR','Score','ATE','RPE','F','H'],['Base',*metrics(base)],['V3',*metrics(v3)],['新候选',*metrics(new)]],.7,1.45,12,1.9,size=15)
 text(s,.85,3.55,11.5,.5,f"Base→V3：ΔScore {oldpair['score_mean_delta']:.3f}；95% CI [{oldpair['paired_bootstrap_95ci'][0]:.3f}, {oldpair['paired_bootstrap_95ci'][1]:.3f}]",21,BLUE,True)
 text(s,.85,4.6,11.5,.6,f"V3→新候选：ΔScore {paired['score_mean_delta']:.3f}；提升/下降/持平 {paired['improved']}/{paired['worsened']}/{paired['tied']}",20,TEAL,True)
 text(s,.85,4.1,11.5,.4,'Base→V3 改善/下降/持平：58/15/27；Seen Score 4.419→16.962；Unseen 17.661→38.549',14,GRAY)
 full=data.get('full_control')
 if full:
  table(s,[['新完整归档抽样100例','有效','SR','Score'],*[ [name,f"{r['overall']['valid']}/100",f"{100*r['overall']['SR_failure_zero']:.1f}%",f"{r['overall']['Score_failure_zero']:.3f}"] for name,r in full['runs'].items()]],.9,5.35,11.5,1.05,size=14)
 else:text(s,.85,5.5,11.5,.8,'CI 只描述当前样本重采样；不代表完整验证集或排行榜。\nSR / Score：计划分母失败记零；ATE / RPE / F / H：有效子集。',17,GRAY)
 text(s,.85,6.6,11.5,.3,'SR / Score：计划分母，失败记零；ATE / RPE / F / H：有效子集。CI仅描述当前样本重采样。',12,GRAY)
 s=add('真实案例：改善与失败都展示','这两张图按预先定义的诊断规则自动选择：左侧是Base到V3分数提升最大的样本，右侧是V3终点误差最大的样本。两边都来自真实初始RGB和原始指令，叠加同一轨迹的GT、Base和V3预测；GT只用于事后解释。对照可以看到分数改善并不等于所有样本都解决，最差终点仍可能很远。它们不是人工挑选的全部成功故事。更多尺度、转弯代理、停止越界代理和格式失败案例保存在完整分析目录，可在讨论中逐个追溯原始响应。','outputs/stage2_analysis/gallery.json；自动排序选择；真实输入与轨迹')
 for i,role in enumerate(['largest_score_gain','worst_endpoint']):
  g=next(x for x in gallery if x['role']==role);x=.65+i*6.25
  text(s,x,1.5,6,.5,'最大分数改善' if i==0 else '最大终点偏差',22,BLUE,True)
  picture(s,g['file'],x,2.05,w=6.05)
  text(s,x,4.7,5.95,1.25,g['instruction'],15)
  text(s,x,6.15,5.95,.5,f"Base Score {g['Base_Score']:.2f}；V3 {g['V3_Score']:.2f}",17,TEAL,True)
 s=add('误差分析：尺度改善，朝向未同步改善','我们不只观察Score，还统计路径长度、终点、朝向以及动作幅度。逐例路径长度比的平均值从3.947降到1.823，注意这不是两组总长度相除；终点误差从7.932降到4.168，而最终朝向误差从0.358变成0.378，略有恶化。Base和V3有效子集数量不同，这些是描述性统计，不应直接解释为因果。转弯与停止的自动排序只是几何代理，不能凭终点投影就断言模型理解了停止地标；需要结合真实指令和图像判断。','stage2_deep_analysis.json；原始预测重算；有效子集统计')
 picture(s,'outputs/stage2_analysis/error_distributions.png',.65,1.55,w=8.0)
 text(s,9.05,1.75,3.6,.9,'长度比均值\n3.947 → 1.823',23,BLUE,True)
 text(s,9.05,3.2,3.6,.9,'终点误差\n7.932 → 4.168',23,TEAL,True)
 text(s,9.05,4.65,3.6,.9,'朝向误差 / rad\n0.358 → 0.378',23,DARK,True)
 text(s,.85,6.3,11.5,.45,'尺度/停止/转弯仍是研究假设；转弯进度、终点投影仅为诊断代理。',17,GRAY)
 s=add('数据与工程可信度：证据可以独立复算','这次从断点恢复了unseen下载，并按固定官方revision和SHA检查整包。页面只使用最新审计文件，未通过的项目会明确写未完成。旧100例保留不动，新的完整归档清单按轨迹组抽样，并排除开发集与旧测试轨迹。旧实验已冻结成不可覆盖只读快照，原始响应、配置和源码都有哈希。CPU和Mock测试验证的是坐标、解析、恢复和编译器等工程行为，不能算作模型准确率。真实API实验与这些测试分开记账。','stage2_data_audit.json；stage2_freeze.json；测试输出；完整Manifest')
 seen=audit.get('splits',{}).get('val_seen',{});unseen=audit.get('splits',{}).get('val_unseen',{})
 line(s,1.65,'Seen 全包',f"{seen.get('episodes','未审计')} episodes；{seen.get('images_decoded','—')} 张图像")
 line(s,2.65,'Unseen 全包',f"{unseen.get('episodes','未完成')} episodes；{unseen.get('images_decoded','—')} 张图像")
 line(s,3.65,'数据完整性',f"完整审计通过：{audit.get('complete',False)}；大小、SHA256、逐图解码")
 line(s,4.65,'工程测试',f"{data['cpu_test_count']} 项 CPU / Mock 通过；不代表模型性能")
 line(s,5.65,'可复现链路','只读旧快照；原始响应、配置、清单与源码 SHA256；失败保留')
 text(s,.85,6.6,11.5,.3,'Manifest SHA256：旧100 b7151e01e00f9b35…；新100 '+audit['manifests'].get('configs/eval_100_full_stage2.json',{}).get('sha256','未生成')[:16]+'…；完整值见数据审计报告',12,GRAY)
 s=add('局限性与资源：哪些结论现在还不能给','首先，旧100例来自归档前缀，不能代表完整验证集；新全归档分层样本也只有100例，仍不是全量评测。第二，评测调用公开demo，没有证据证明它与私有CodaBench评分器相同。第三，开发集很小，多策略选择有偏差，旧测试集已经反复使用。第四，API模型别名无法锁定服务端权重，temperature为零也不保证逐位确定性。Cosmos核查仍然没有授权，Reason2-8B没有运行；LCVN缺少任务训练产物，目前分配GPU也为零，这些阻塞没有被工程测试替代。','stage2_model_access.json；数据采样记录；固定公开评测代码')
 line(s,1.55,'统计限制','小开发集、多候选选择、旧测试复用；不作泛化保证')
 line(s,2.55,'评测边界','公开 demo ≠ 已验证的私有 scorer；无排行榜成绩')
 line(s,3.55,'模型身份','通用视觉语言 API ≠ 专用导航模型；服务端版本不透明')
 line(s,4.55,'Cosmos Reason2-8B','NOT RUN / AUTHORIZATION UNAVAILABLE')
 line(s,5.55,'LCVN 与算力','缺可验证任务 checkpoint；当前获分配 GPU 为 0')
 if data.get('vision_probe'):text(s,.85,6.6,11.5,.3,'额外 Qwen3-VL 路由：终止于有限超时探测；未决请求单列，不计为有效模型预测。',12,GRAY)
 s=add('研究结论与下一步：以独立验证推动路线规划','本轮把已有结果冻结并重算，完成分开的尺度、停止、转弯、结构化和JSON实验，所有正负结果都保留。下一步最值得投入的是扩大真正独立的开发和测试样本，检验在可见地标约束下分段估计距离和终止条件，而不是继续对旧100例调Prompt。结构化表示如果没胜出，也不能只因其工程上整齐就宣称更好。团队资源方面，优先获取真实Cosmos endpoint或NVIDIA授权，以及LCVN匹配权重；GPU到位后先做1例验证输入输出，再做同清单对照，避免一开始铺开大实验。','stage2_selection.json；stage2_final_metrics.json；完整实验报告')
 line(s,1.65,'本轮已完成','冻结与重算；分离消融；真实案例；数据审计与科研汇报')
 line(s,2.65,'优先研究问题','地标约束的分段距离、停止条件和转弯事件联合建模')
 line(s,3.65,'验证路线','已准备24例独立清单 → 后续确认实验 → 冻结下一版策略')
 line(s,4.65,'团队需要决策','Cosmos 合法 endpoint；LCVN 任务权重；可分配 GPU')
 line(s,5.65,'避免错误投入','不对同一旧测试集反复调参；保留没有提升的真实结果')
 out=ROOT/'reports/WorldNav_科研冲刺汇报_20261031_v2.pptx'
 if out.exists():
  backup=ROOT/'local_archive/ppt_stage2_versions';backup.mkdir(exist_ok=True);shutil.copy2(out,backup/(datetime.datetime.now().strftime('%H%M%S%f')+'.pptx'))
 prs.save(out)
 (ROOT/'reports/stage2_speaker_notes.md').write_text('# 逐页中文演讲稿（13页，约7–9分钟）\n\n'+'\n\n'.join(f'## 第{i+1}页\n\n{n}' for i,n in enumerate(notes))+'\n')
 (ROOT/'reports/stage2_ppt_sources.md').write_text('# PPT 数据来源与口径\n\n'+ '\n'.join(f'- 第{i+1}页：{src}' for i,src in enumerate(sources))+'\n\nSR/Score以计划分母，失败记零；ATE/RPE/F/H为有效子集。CI固定5000次配对bootstrap、种子20261031，仅描述相应样本的重采样。新完整归档集与旧集分别汇总，禁止跨集直接作配对。图像和指令仅来自项目真实样本；坐标示意是动作协议说明，非实验结果。原始数据与完整API响应仅本地保存。\n')
 print(out.name,hashlib.sha256(out.read_bytes()).hexdigest(),'slides',len(prs.slides))
if __name__=='__main__':build()
