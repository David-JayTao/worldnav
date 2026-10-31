# WorldNav 第二阶段科研冲刺：完整实验报告

证据更新时间（UTC）：2026-10-31T05:51:23.068203+00:00。当前获分配GPU=0。API实测与CPU/Mock测试分开计数。这里零样本指请求无任务示例、无任务权重训练；开发集仍用于策略选择，不宣称开发过程没有标签监督。temperature=0也不保证云服务逐位确定性；服务端权重版本与训练数据不可独立核验，保存原始响应用于精确离线复算。

## 1. 冻结、复算与研究边界

旧实验只读快照见 `stage2_freeze.json`，覆盖原始响应、动作、轨迹、清单、Prompt、源码和测试日志；完整SHA256索引在服务器 local_archive 对应目录。旧文件不修改。重算从逐case原始响应重新解析，与保存动作、轨迹及公开指标核对，并核验真实图片/元数据/轨迹组哈希。未发现原报告差异（浮点求和尾数差异小于1e-10）。

Base和V3使用同100条输入；开发集与正式集轨迹哈希零交集。旧100、dev12、新100、dev24四清单之间的精确初始图片哈希和图片/指令组合交集均为0，见stage2_input_overlap_audit.json；这不是场景级独立性的证明。GT隔离由Observation边界、请求构造代码与持久化顺序测试验证；GT仅用于去重和落盘后的评测/可视化。旧正式集已被查看，本轮复用它比较新策略属于探索性结果。完整归档新清单独立排除旧正式集及开发集，是新的实验版本。

## 2. 实验指标

SR、Score使用计划分母，失败记零；ATE/RPE/F/H使用有效评估子集。另列有效子集SR和Score，禁止口径混用。公开逐例公式：`Score_i = 100 F_i (1+H_i)/2 × [0.70 + 0.10 SR_i + 0.10/(1+ATE_i) + 0.10/(1+RPE_i)]`，按计划样本求均值。SR只占括号中的一项，因此SR较高并不保证Score较高；实现固定在Track1 a52e43f的demonstration.py。

| 数据版本 / 实验 / 分组 | 有效/计划 | SR 分子/分母 | Score* | ATE | RPE | F | H | 有效Score | 有效SR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 旧前缀100/Base/Overall | 100/100 | 5/100 | 11.040 | 7.193 | 0.943 | 0.150 | 0.783 | 11.040 | 0.050 |
| 旧前缀100/Base/val_seen | 50/50 | 3/50 | 4.419 | 6.937 | 0.990 | 0.067 | 0.644 | 4.419 | 0.060 |
| 旧前缀100/Base/val_unseen | 50/50 | 2/50 | 17.661 | 7.449 | 0.896 | 0.233 | 0.921 | 17.661 | 0.040 |
| 旧前缀100/V3/Overall | 98/100 | 17/100 | 27.756 | 2.196 | 0.315 | 0.354 | 0.805 | 28.322 | 0.173 |
| 旧前缀100/V3/val_seen | 48/50 | 9/50 | 16.962 | 1.912 | 0.274 | 0.229 | 0.700 | 17.669 | 0.188 |
| 旧前缀100/V3/val_unseen | 50/50 | 8/50 | 38.549 | 2.469 | 0.354 | 0.474 | 0.906 | 38.549 | 0.160 |
| 旧前缀100/Candidate/Overall | 99/100 | 19/100 | 29.242 | 2.394 | 0.337 | 0.374 | 0.786 | 29.537 | 0.192 |
| 旧前缀100/Candidate/val_seen | 49/50 | 10/50 | 19.323 | 1.908 | 0.291 | 0.259 | 0.681 | 19.717 | 0.204 |
| 旧前缀100/Candidate/val_unseen | 50/50 | 9/50 | 39.160 | 2.870 | 0.383 | 0.486 | 0.889 | 39.160 | 0.180 |
| 新全归档100/Base/Overall | 99/100 | 7/100 | 13.578 | 6.292 | 0.882 | 0.176 | 0.759 | 13.715 | 0.071 |
| 新全归档100/Base/val_seen | 50/50 | 2/50 | 4.272 | 6.600 | 0.917 | 0.058 | 0.592 | 4.272 | 0.040 |
| 新全归档100/Base/val_unseen | 49/50 | 5/50 | 22.884 | 5.977 | 0.846 | 0.297 | 0.929 | 23.351 | 0.102 |
| 新全归档100/V3/Overall | 94/100 | 23/100 | 32.431 | 1.843 | 0.294 | 0.423 | 0.808 | 34.501 | 0.245 |
| 新全归档100/V3/val_seen | 47/50 | 13/50 | 19.746 | 1.766 | 0.258 | 0.263 | 0.695 | 21.006 | 0.277 |
| 新全归档100/V3/val_unseen | 47/50 | 10/50 | 45.116 | 1.921 | 0.329 | 0.583 | 0.922 | 47.995 | 0.213 |
| 新全归档100/Candidate/Overall | 96/100 | 20/100 | 29.895 | 2.115 | 0.312 | 0.383 | 0.794 | 31.141 | 0.208 |
| 新全归档100/Candidate/val_seen | 47/50 | 10/50 | 14.770 | 2.254 | 0.293 | 0.196 | 0.677 | 15.713 | 0.213 |
| 新全归档100/Candidate/val_unseen | 49/50 | 10/50 | 45.020 | 1.982 | 0.331 | 0.563 | 0.905 | 45.939 | 0.204 |

## 3. 开发集策略与选择

预注册见 `stage2_preregistration.md`；原V3不变。所有方法先跑轨迹隔离的12例开发集，唯一候选由开发集失败记零Score决定。新策略的研究假设为分段尺度、终止子句、转弯事件以及显式路线编译；没有将全体动作统一乘常数。

| 方法 | 有效/12 | SR | Score | API 成功/请求 | JSON合法/请求 | 已报告输入/输出 Token | 累积API秒 |
|---|---:|---:|---:|---:|---:|---:|---:|
| scale | 11/12 | 1/12 | 21.479 | 13/13 | 11/13 | 12244/19647 | 365.3 |
| stop | 12/12 | 2/12 | 28.365 | 12/12 | 12/12 | 10732/20914 | 435.6 |
| turn | 12/12 | 2/12 | 33.075 | 12/12 | 12/12 | 10708/21706 | 428.6 |
| structured | 12/12 | 3/12 | 19.756 | 12/12 | 12/12 | 7252/15993 | 323.1 |
| json | 11/12 | 1/12 | 11.543 | 11/12 | 11/12 | 8960/21452 | 517.4 |

冻结候选：**turn**；开发集是否超过V3：True。冻结时间（UTC）2026-10-31T04:39:07.185341+00:00；配置SHA256 `9567c07bed6b5b9a0f89f9261a48d2d17d9ca158d2ee2654dc9cf0cd82d008af`。12例反复开发与多重候选选择造成选择偏差，不能外推。

Robust JSON使用原V3文本和response_format=json_object；单例真实图片请求返回合法结果。开发集实际出现1次HTTP400，请求接受性并不完全稳定；服务接受参数不等于确认强制schema或证明参数未被忽略。严格解析与有限重试没有放宽。结构化策略先产生地标、转角、距离和步幅，独立编译器严格细分到动作；非法字段、非有限值或超过64步均记失败，不截断、不补全、不伪装Stop。

额外模型为官方明确支持图像输入的Qwen3-VL-32B-Instruct，经同SinapisAI真实RGB请求测试。它不参与Qwen3.8策略选型；若接口持续超时，将保留终止请求和未决预算记录并停止，不把未完成调用写成有效预测或0分模型对照。现场状态见stage2_vision_probe.json。模型身份依赖服务方路由，无法独立验证服务器权重。官方来源：https://huggingface.co/Qwen/Qwen3-VL-32B-Instruct。

## 4. 配对统计

- 旧Base→V3：ΔScore=16.715658；95% paired bootstrap CI=[11.361382345134816, 22.06429110701694]；改善/下降/持平=58/15/27；SR新增/丢失=16/4；split差值={'val_seen': 12.543170541813645, 'val_unseen': 20.888146319004218}。

- 旧V3→新候选：ΔScore=1.485817；95% paired bootstrap CI=[-3.729791285097661, 6.875401260904494]；改善/下降/持平=38/41/21；SR新增/丢失=13/11；split差值={'val_seen': 2.360585378811158, 'val_unseen': 0.6110481471327431}。

- 新完整归档Base→候选：ΔScore=16.316817；95% paired bootstrap CI=[10.468841139982295, 22.164907837070228]；改善/下降/持平=59/13/28；SR新增/丢失=18/5；split差值={'val_seen': 10.497949244629362, 'val_unseen': 22.135685356131386}。

- 新完整归档V3→候选：ΔScore=-2.535595；95% paired bootstrap CI=[-7.510745117568489, 2.4973529921115927]；改善/下降/持平=37/42/21；SR新增/丢失=10/13；split差值={'val_seen': -4.975637144820945, 'val_unseen': -0.0955533990537441}。

配对分解（1为有效预测；贡献按计划100例分母；不把格式覆盖率变化当成纯几何改进）：

| 对照 | 有效性变化 | 样本数 | 子集平均Score差 | 对计划均值的贡献 |
|---|---|---:|---:|---:|
| 旧V3→Turn | 1_to_1 | 97 | 1.532 | 1.486 |
| 旧V3→Turn | 0_to_1 | 2 | 0.000 | 0.000 |
| 旧V3→Turn | 1_to_0 | 1 | 0.000 | 0.000 |
| 旧V3→Turn | 0_to_0 | 0 | 未测 | 0.000 |
| 新V3→Turn | 1_to_1 | 91 | -3.547 | -3.228 |
| 新V3→Turn | 0_to_1 | 5 | 18.878 | 0.944 |
| 新V3→Turn | 1_to_0 | 3 | -8.387 | -0.252 |
| 新V3→Turn | 0_to_0 | 1 | 0.000 | 0.000 |

固定种子20261031、5000次配对重采样；区间只反映该样本集重采样波动，不保证完整验证集泛化。两种数据版本不混算、不直接相减。

## 5. 深入诊断与真实案例

`stage2_deep_analysis.json`包括Overall、seen/unseen、指令类型、参考步数区间、参考长度区间及文件名场景代理分组。输出分布包含动作数量、预测/参考长度、逐例长度比、终点/朝向误差、转弯次数与进度、动作幅度。场景前缀不是经过验证的物理场景标签；终点投影与转弯匹配仅为几何诊断代理，不能当语义错误真值。

7组确定性案例规则覆盖最大改善、最大终点偏差、尺度异常、转弯偏差代理、停止越界代理、格式失败及SR与轨迹保真度不一致。`outputs/stage2_analysis/*_details.json`保留真实输入指令、GT、预测动作/轨迹、原始响应；各case指标在CSV/JSON中。PPT展示改善和失败两例，不仅展示成功。

粒度敏感性CPU诊断：固定原V3的几何路径，只将平移二等分并保留最后半步转角；97例符合64步上限，终点/路径长度不变，但公开Score平均改变0.173、最大绝对改变2.923。该结果不是新模型实验，提示不能把粒度带来的所有Score变化等同于几何改善。原始诊断在outputs/stage2_metric_sensitivity.json。

## 6. 数据与可信度

固定来源revision `ecf02ef425398b3cf5bd76a729fae1edd928ed98`；下载实际字节、SHA256、归档与逐图审计见 `stage2_data_audit.json`。完整审计是否通过：**True**。没有下载完整训练集；旧前缀清单保留不覆盖。episode目录对应指令变体，图像统计为文件数而非去重物理视图数；底层轨迹内容哈希分组数量见stage2_trajectory_groups.json。

新完整归档清单按拥有三类指令的轨迹组抽样，50/50、风格17/17/16；排除旧正式集和开发集。此为符合资格轨迹组的分层局部100例，不能称为所有episode等概率样本或完整全量评测。

## 7. 工程测试与异常

84项CPU/Mock测试通过，原72项无退化。测试名称与完整输出在本地 logs/stage2_tests.txt；API请求不计入单测。修复了单split smoke初始化遗漏、空split汇总除零以及旧matplotlib参数兼容问题。JSON smoke的汇总异常通过离线恢复解决，没有重新收费请求；完整异常日志保留。

长任务均有独立tmux、日志、有限预算和重试、原子case落盘及完成case跳过。开发单runner最多3并发，JSON smoke与之合计最多4；正式候选与全归档对照最多4并发并顺序执行，避免并发叠加。新进程结束日志保存CPU时间与峰值RSS。旧实验未覆写。

## 8. 模型与资源阻塞

Cosmos Reason2-8B: **NOT RUN / AUTHORIZATION UNAVAILABLE**。最新目录仍无Sinapis路由；NVIDIA匿名真实图片请求401，公开Space为PAUSED。无现有NVIDIA凭据，不将SinapisKey发到NVIDIA。GPU分配0，未启动CUDA或CPU完整8B推理。LCVN缺已验证任务checkpoint。详见 `stage2_model_access.json`；官方接口来源：https://docs.nvidia.com/nim/vision-language-models/1.7.0/examples/cosmos-reason2/api.html。

## 9. 结论与下一步

本轮正负结果均按开发集冻结后实测报告；重点关注结构化表示是否改善几何误差、是否牺牲有效率或朝向，而非只挑最高SR。下一步扩大独立开发集，在新测试版本验证地标约束的距离与终止规划；获取合法Cosmos endpoint和LCVN匹配权重后才进行对应模型实测。公开demo指标不是CodaBench比赛成绩。输入端GT隔离也不能证明通用模型预训练从未接触这些公开数据，当前无法核验预训练污染。

## 10. 原始证据与复现

- 旧实验：runs/qwen_api_100case_baseline、runs/qwen_api_100case_optimized。
- 新开发集：runs/stage2_dev_{scale,stop,turn,structured,json,vision}。
- 冻结选择与旧集候选：runs/stage2_selection.json、runs/stage2_candidate_100。
- 全归档新集：configs/eval_100_full_stage2.json、runs/stage2_full_{base,v3,candidate}_100。
- 数据下载和图像审计：logs/stage2_data_download.txt、outputs/full_validation_audit_*.json。
- 报告和演示：reports/stage2_*、WorldNav_科研冲刺汇报_20261031_v2.pptx。
- Git只提交脱敏汇总、源码、配置、报告和必要演示；原始预测、API响应、数据、私密日志仅服务器保存。

## 最终失败样本（不补动作、不删除）

| 实验 | Split | Episode ID | 分类 | 可公开的错误摘要 |
|---|---|---|---|---|
| qwen_api_100case_optimized | val_seen | Feb-16-2023-cory1-intloss_00000007_2_13_0_2 | invalid_prediction | parse_check: action must be [dx, dy, dyaw]；Empty model content |
| qwen_api_100case_optimized | val_seen | Jan-12-2023-bww8_00000000_2_6_0_0 | invalid_prediction | Expecting value: line 1 column 339 (char 338)；Expecting value: line 1 column 465 (char 464) |
| stage2_dev_json | val_seen | Dec-06-2022-bww8_00000032_0_13_0_1 | api_error | HTTP 400 |
| stage2_candidate_100 | val_seen | jackal_2019-08-06-15-35-05_0_r00_4_0_0 | invalid_prediction | Expecting ',' delimiter: line 1 column 379 (char 378)；parse_check: action must be [dx, dy, dyaw] |
| stage2_dev_scale | val_unseen | 20210826_42_0001_14_2 | invalid_prediction | Expecting value: line 23 column 3 (char 448)；Empty model content |
| stage2_vision8_smoke | val_seen | Feb-21-2023-soda3-intloss_00000020_0_5_0_0 | api_error | APITimeoutError |
| stage2_dev_vision | val_seen | Feb-21-2023-soda3-intloss_00000020_0_5_0_0 | api_error | APITimeoutError；APITimeoutError；APITimeoutError |
| stage2_dev_vision | val_seen | Feb-23-2023-soda3-intloss_00000017_0_12_0_1 | api_error | APITimeoutError；APITimeoutError；APITimeoutError |
| stage2_dev_vision | val_unseen | 20210826_42_0001_09_0 | api_error | APITimeoutError；APITimeoutError；APITimeoutError |
| stage2_full_v3_100 | val_seen | jackal_2019-09-19-12-00-08_1_r02_0_0_1 | invalid_prediction | Expecting value: line 1 column 383 (char 382)；Expecting ',' delimiter: line 1 column 265 (char 264) |
| stage2_full_v3_100 | val_seen | jackal_2019-10-24-16-20-42_10_r02_1_0_0 | invalid_prediction | Expecting ',' delimiter: line 1 column 650 (char 649)；parse_check: action must be [dx, dy, dyaw] |
| stage2_full_v3_100 | val_seen | jackal_2019-12-23-14-44-10_11_r01_3_0_2 | invalid_prediction | Expecting ',' delimiter: line 1 column 492 (char 491)；Expecting value: line 1 column 121 (char 120) |
| stage2_full_v3_100 | val_unseen | 20210826_91_0001_10_1 | api_error | APITimeoutError；APITimeoutError；APITimeoutError |
| stage2_full_v3_100 | val_unseen | 20210903_299_0001_08_0 | invalid_prediction | Expecting ',' delimiter: line 18 column 17 (char 348)；Empty model content |
| stage2_full_v3_100 | val_unseen | 20210903_33_0001_00_1 | invalid_prediction | Expecting ',' delimiter: line 1 column 293 (char 292)；Empty model content |
| stage2_full_base_100 | val_unseen | 20210826_91_0001_10_1 | api_error | APITimeoutError；APITimeoutError；APITimeoutError |
| stage2_full_candidate_100 | val_seen | jackal_2019-09-12-18-31-38_22_r00_3_0_2 | invalid_prediction | Expecting value: line 1 column 349 (char 348)；Empty model content |
| stage2_full_candidate_100 | val_seen | no10vcF_61_1_3_0_0 | invalid_prediction | Expecting value: line 22 column 3 (char 412)；Expecting ',' delimiter: line 14 column 17 (char 264) |
| stage2_full_candidate_100 | val_seen | random_mdps_A_Spot_Library_Fountain_Fri_Nov_12_82_0_20_0_2 | invalid_prediction | Expecting ',' delimiter: line 1 column 322 (char 321)；Expecting value: line 1 column 406 (char 405) |
| stage2_full_candidate_100 | val_unseen | 20210903_33_0001_00_1 | invalid_prediction | Expecting ',' delimiter: line 1 column 293 (char 292)；Empty model content |

## 深入解读：改善、代价与负结果

旧100例新候选相对V3的失败记零Score差为1.486，95%配对区间[-3.729791285097661, 6.875401260904494]。该结果只用于冻结策略的事后比较，不回头重选。

Structured在开发集SR为3/12，高于Turn的2/12，但Score更低，因此不能因SR较高而认定最好。Scale和Structured未超过固定V3；RobustJSON仅11/12有效并有HTTP400，没有可靠性改善证据。Turn和Stop开发分数提升仍需新样本检验。

| 策略 | ATE | RPE | F | H | 有效Score | 平均请求秒 |
|---|---:|---:|---:|---:|---:|---:|
| scale | 1.773 | 0.276 | 0.307 | 0.802 | 23.431 | 28.10 |
| stop | 1.811 | 0.289 | 0.359 | 0.832 | 28.365 | 36.30 |
| turn | 1.614 | 0.265 | 0.420 | 0.833 | 33.075 | 35.72 |
| structured | 1.660 | 0.237 | 0.244 | 0.824 | 19.756 | 26.92 |
| json | 2.747 | 0.385 | 0.165 | 0.682 | 12.592 | 43.12 |

几何诊断共同有效子集：97例（所有展示方法均有有效预测的交集），用于降低失败子集不同造成的描述性偏差。该子集不替代计划分母正式指标。

| 方法 | 预测步数 | 参考步数 | 预测长度 | 参考长度 | 逐例长度比均值 | 终点误差 | 朝向误差rad | 转弯进度代理 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base | 9.000 | 16.990 | 13.017 | 5.949 | 3.796 | 7.720 | 0.365 | 0.454 |
| V3 | 14.474 | 16.990 | 7.243 | 5.949 | 1.800 | 4.085 | 0.380 | 0.389 |
| New | 13.856 | 16.990 | 7.057 | 5.949 | 2.202 | 4.105 | 0.430 | 0.437 |

新集Turn相对V3差值为-2.536，区间[-7.510745117568489, 2.4973529921115927]跨零，不能宣布稳定提升，也不能据此宣称已证明显著退步；当前继续保留V3参照，不推广Turn为新最佳。

新完整归档100例Base→候选：ΔScore=16.317，CI=[10.468841139982295, 22.164907837070228]。它与旧集不同，不能将该差值当作V3→候选的提升，也不能用旧集Base分数作分母。

## 本轮API消耗与未决请求

{
  "reserved_slots": 500,
  "recorded_requests": 497,
  "unresolved_reserved_slots": 3,
  "reported_input_tokens": 396711,
  "reported_output_tokens": 739169,
  "requests_without_reported_usage": 24,
  "monetary_cost": null,
  "note": "Unresolved slots may or may not have reached provider; timeout/interrupted requests may still be billed. Tokens are provider-reported usage only, not assumed zero for missing records. No reused old inference counted as new."
}

较小视觉模型的有界路由探测（先1例，再决定是否12例；45秒超时，无网络重试，不参与策略选择）：
{
  "model": "qwen/qwen3-vl-8b-instruct",
  "smoke_valid": 0,
  "development_completed": 0,
  "development_valid": 0,
  "timeouts_seconds": 45,
  "network_retries": 0,
  "formal_100case_run": false
}
官方视觉输入说明：https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct。API超时不是几何导航失败，不能用不可用路由的零覆盖证明模型能力差。

额外视觉路线受控终止记录：
{
  "reason": "Optional vision route: at least three terminal API failures after bounded retries; stop further paid requests",
  "completed_cases": 3,
  "valid_cases": 0,
  "reserved_requests": 12,
  "recorded_requests": 9,
  "unresolved_reserved_requests": 3,
  "warning": "In-flight requests interrupted; charges/provider completion unknown. Do not label unresolved requests as model predictions.",
  "stopped_at_unix": 1793421736.4909246
}
