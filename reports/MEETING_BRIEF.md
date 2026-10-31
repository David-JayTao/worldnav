> 更新说明（2026-10-31）：本文保留为上一阶段待审核草稿。最新真实 API 实验、指标和会议材料请阅读 [meeting_2026-10-31.md](meeting_2026-10-31.md)。本轮 Qwen 基础版已完成 100/100 有效评估，候选版和开发集进展以最新报告为准。

# WorldNav 阶段性科研进展汇报（会议审核草稿）

事实核验时间：2026-10-30 11:52（北京时间）。本文仅保存在本地，未经审核不提交或推送。数据下载仍在进行，会议前必须刷新进度。

## 1. 项目背景与目标

RoboWorld 2026 Track 1 WorldNav 要求根据初始 RGB 图像和语言指令生成导航动作序列。我们负责先建立可复现的数据、推理和评测链路，再取得真实 baseline，之后比较 LCVN-Uni 与 Cosmos-Reason2-8B 路线。目前完成的是 CPU 工程准备，不是模型创新或比赛成绩。

## 2. 已完成工作及证据

| 分类 | 实际成果 | 实现和证据 |
|---|---|---|
| 工程 | 初始图像/指令与参考标签隔离；受限 pickle 读取；动作严格解码；世界位移转当前机体坐标；轨迹积分 | `src/worldnav/{data,actions,geometry}.py` |
| 评测 | 调用固定版官方公开指标；保存逐样本预测、轨迹、失败原因、耗时和运行配置；检查 JSON/ZIP 协议 | `src/worldnav/{evaluation,protocol,runner}.py`、`scripts/run_eval.py`；不代表与私有评分器一致 |
| 数据 | 验证集断点续传；固定归档前缀、种子与文件哈希；抽取 50 seen + 50 unseen | `scripts/{download_validation,build_eval_manifest}.py`、`configs/eval_100.json` |
| 代码管理 | 初始化 main，保留历史成果，固定两个官方 submodule，屏蔽数据、权重、环境和私密日志 | `.gitignore`、`.gitmodules`；本地提交 `66a0413`、`4085d3b` |
| 模型调研 | 区分 Anole 基座与导航训练 adapter；缺少任务 checkpoint 时明确阻止模型加载 | `src/worldnav/checkpoint.py`；LCVN-Uni 适配代码尚未经真实模型验证 |

官方 Track 1 固定为 `a52e43fd68edcd413436c2466a3177046002964b`；LCVN 固定为 `e6a52e65901a10e4581a0431944aad6e56355ef7`。未修改官方受版本管理的源代码。原始结果留在 `outputs/first_round/`，旧脚本/报告留在 `local_archive/bootstrap_20261030/`；公共报告做了路径脱敏。

Git 目标：<https://github.com/David-JayTao/worldnav>。本地提交尚未推送成功：HTTPS 缺少认证，现有 SSH 路径连接超时。不能称为已在 GitHub 交付。

## 3. 首轮实验与工程验证

- 历史首轮：9 个 val_seen episode、3 条底层轨迹；CPU smoke 用时 5.138 秒；模型前向 0 次、baseline 评估 0 次。证据：`reports/first_round_summary.json` 和原始 `outputs/first_round/`。
- 当前独立 `.venv-cpu`：原 40 项测试通过；追加 float32 坐标精度回归测试后共 41 项通过。具体名称附后，原始输出 `logs/tests_cpu_current.log`。
- 100 条参考轨迹回环：最大世界位置误差 `1.4210854715202004e-14`，CPU 约 0.124 秒；无参考动作超过 64 步或平移限制。证据：`outputs/reference_roundtrip_100_fixed_20261030/summary.json`。
- 该回环使用参考标签验证数学与指标接口，**不是模型输出**。真实 3 / 9 / 100 case 推理均未完成；SR、ATE、RPE、fidelity、Score、GPU 显存均未测。

## 4. 当前数据情况

核验快照：val_seen `3,440,438,415 / 7,409,704,960` bytes（约 46.43%）；val_unseen `3,165,321,855 / 20,311,838,720` bytes（约 15.58%）。均为 `.tar.part`，尚未完成整包 SHA256 和归档完整性检查。仅下载验证集，未下载 train。下载目录使用配置的数据根，原始数据保留。

数据源为官方 `fly1113/LCVN`，固定 revision `ecf02ef425398b3cf5bd76a729fae1edd928ed98`，预期大小与整包 SHA256 在 `configs/datasets.json`。

现有 `configs/eval_100.json` 是 **provisional/debug 本地前缀抽样**：seen 前缀 978,381,967 bytes（候选 3140 episode），unseen 前缀 1,133,410,305 bytes（候选 228 episode）；固定种子 20261030。先按位姿内容哈希分组，再从包含三类指令的轨迹组中确定性抽取。每个 split 50 条，指令类型各 17/17/16；总共 100 个不同轨迹内容哈希。已物化 100 条所需初始图像和元数据并通过输入检查。

Manifest SHA256：`b7151e01e00f9b3588c44cae9d10de0d32bba8e3f7a17789b9187403af4eef44`。重新生成结果一致。它不是完整验证集均匀抽样，也未通过官方完整 ID 清单校验。完整验证集下载并校验后，使用新文件生成最终清单，保留此版本。**100-case 数据准备不等于 100-case 推理完成。**

## 5. 模型与算力

LCVN-Uni：已检查官方仓库、Releases、Issues、HF 和论文资源；尚未确认能使用的导航训练 adapter、配套扩展 tokenizer/processor 和对应基座版本。公开 Anole 基座不能替代这些文件。需要向作者或团队索取完整训练产物、文件哈希和官方推理命令。现有适配器的零初始位姿策略、动作坐标和 26 步 rollout 仍需真实模型核验。

Cosmos-Reason2-8B：目前尚无经过验证的本项目推理环境、导航 prompt、动作解析器或模型结果。后续先核对官方模型资料和部署约束；其导航输出协议必须单独设计，不复用 LCVN 专用动作 token 解码器。不能把通用视觉推理模型直接视为已训练导航策略。

**当前获准可用 GPU 数量为 0**，以用户资源分配通知为准，不是对物理服务器 GPU 数量的判断。不得假设明天有两张 3090；不启动 GPU，也不通过 CPU 强跑完整 8B 模型。

## 6. 主要困难和风险

- 工程：真实权重尚未验证适配接口；初始位姿适配可能改变模型分布；26→64 步不能仅修改常量。公开 demo 与私有评分器不保证相同。
- 数据：完整下载仍进行中；当前前缀清单有抽样偏差；完整图片/轨迹统计与归档校验待完成。
- 权重：LCVN 任务训练产物缺失是独立于 GPU 的阻塞。
- 算力：没有获分配的 GPU，模型加载和真实推理无法验收。
- 协作：GitHub 认证未通，代码目前仅在本地提交。

## 7. 下一阶段最短路径

1. CPU 阶段完成数据续传、整包哈希及归档/图片统计，生成最终 100-case 清单；持续补齐测试与复现文档。
2. 并行向团队确认 GitHub 安全认证、LCVN 训练产物、可复用 Cosmos 环境及 prompt。
3. 获得真实 checkpoint 后先核验文件与依赖；GPU 明确分配后做最小 3-case 推理，检查权重加载、真实动作、坐标和结果落盘。
4. 运行历史 9-case 指令对照，再固定 100-case，记录逐样本指标、失败率、耗时、峰值显存。
5. 在可复现 baseline 基础上，再研究 prompt、动作规划和长程 rollout 改进。

## 8. 团队讨论与分工

建议由一人负责权重/作者沟通，一人负责算力和部署，一人负责数据与评测，统一通过配置和版本记录共享结果；这只是会议建议，尚未分配或联系任何人。

重点问题：

1. 能否明确分配双 3090 或其他 GPU？显存、时段和使用权限分别是什么？
2. 是否已有可直接复用的 Cosmos 环境、权重缓存、导航 prompt 和有效输出样例？
3. 是否能向 LCVN 作者获取 adapter、扩展 tokenizer/processor、匹配基座及命令？
4. LCVN 复现和 Cosmos 探索如何安排优先级与负责人？
5. 谁能恢复仓库推送权限，并审核本汇报与实验口径？

## 9. 2～3 分钟口头汇报稿

我们当前的目标是把 WorldNav 从初始数据测试推进到可复现的真实模型 baseline。任务输入只有初始图像和语言指令，输出是符合比赛协议的导航动作。

这阶段主要完成了工程准备。我们保留了原来的实验和日志，建立了 Git 仓库，并固定官方工具和 LCVN 的代码版本。数据读取、动作解码、坐标转换、轨迹积分、JSON 校验和公开指标已经接入，模型输入也和参考轨迹分离，避免用标签得到看似有效的成绩。独立 CPU 环境目前通过 41 项测试。真实数据的坐标回环还发现并修复了 float32 相减精度问题。

数据方面，完整 seen 和 unseen 验证集还在断点续传。我们从已下载的固定前缀里准备了 100 条调试样本，seen 和 unseen 各 50 条，并平衡了三种指令类型。这个清单可以重复生成，但有前缀抽样偏差，不能称为完整验证集评测。下载完成并校验后，我们会另建最终清单。

现在还没有真实 baseline 分数。首轮九条样本和这次一百条回环都是 CPU 流程或数学验证，模型前向仍然是零。原因有两个：LCVN 导航训练权重及配套 tokenizer 还没有确认可用；当前分配给我们的 GPU 数量也是零。Cosmos 路线目前仍是接入准备，尚无本项目的有效推理结果。

最短推进路线是继续完成数据和 CPU 验证，同时请团队确认 LCVN 训练产物、可复用的 Cosmos 环境，以及明确的 GPU 分配。条件具备后先做三条真实推理，确认加载和输出正确，再做九条指令对照，最后运行固定的一百条 baseline。希望今天讨论的重点是资源、路线优先级和负责人，而不是把工程测试当作比赛成绩。

## 10. 一页 PPT 核心要点

- **目标**：RGB + 指令 → 合规动作 → 可复现真实 baseline。
- **已完成**：版本固定、输入隔离、坐标/协议/评测工程；41 项 CPU 测试；历史 9 条流程测试。
- **数据**：50 seen + 50 unseen 调试清单，100 个轨迹组；完整归档仍在下载。
- **尚未完成**：真实模型推理 0；baseline 指标未测；GitHub 推送未成功。
- **阻塞**：GPU 可用 0；LCVN 任务 checkpoint 缺失；Cosmos 尚待部署验证。
- **下一步**：数据校验 + 权重/算力落实 → 3 条真实推理 → 9 条对照 → 100 条 baseline。

## 11. 会前需复核

下载字节数与完成状态、最终测试数量、最新 Git commit/推送状态、是否新获得训练权重或 GPU、Cosmos 环境是否已有团队成果、最终 manifest 是否已经生成。口头稿和 PPT 的数字应同步更新。以下测试结果是生成时的实际记录。

## 附录：CPU 测试原始结果

```text
test_duplicate_tokens_rejected (test_core.ActionTests) ... ok
test_missing_tokens_rejected (test_core.ActionTests) ... ok
test_outside_vocabulary (test_core.ActionTests) ... ok
test_stop (test_core.ActionTests) ... ok
test_tuple_generation (test_core.ActionTests) ... ok
test_uses_predicted_yaw (test_core.ActionTests) ... ok
test_valid_tokens (test_core.ActionTests) ... ok
test_missing_checkpoint (test_core.DownloadAndCheckpointTests) ... ok
test_resume_ignored (test_core.DownloadAndCheckpointTests) ... ok
test_resume_valid (test_core.DownloadAndCheckpointTests) ... ok
test_resume_wrong_offset (test_core.DownloadAndCheckpointTests) ... ok
test_template_is_not_checkpoint (test_core.DownloadAndCheckpointTests) ... ok
test_canonical_reference_rotation (test_core.GeometryTests) ... ok
test_forward_at_ninety_degrees (test_core.GeometryTests) ... ok
test_heading_continuity (test_core.GeometryTests) ... ok
test_invalid_numbers (test_core.GeometryTests) ... ok
test_left_is_positive (test_core.GeometryTests) ... ok
test_reference_identity_metric (test_core.GeometryTests) ... ok
test_short_prediction_is_scored (test_core.GeometryTests) ... ok
test_translation_precedes_rotation (test_core.GeometryTests) ... ok
test_world_delta_conversion (test_core.GeometryTests) ... ok
test_action_bounds (test_core.ProtocolTests) ... ok
test_duplicate_unknown_missing_ids (test_core.ProtocolTests) ... ok
test_full_requires_manifest (test_core.ProtocolTests) ... ok
test_json_constants_and_duplicate_keys (test_core.ProtocolTests) ... ok
test_max_actions (test_core.ProtocolTests) ... ok
test_valid (test_core.ProtocolTests) ... ok
test_valid_phase1_zip (test_core.ProtocolTests) ... ok
test_zip_layout_and_phase (test_core.ProtocolTests) ... ok
test_float32_reference_roundtrip (test_data_pipeline.DataTests) ... ok
test_insufficient_groups (test_data_pipeline.DataTests) ... ok
test_numpy_protocols (test_data_pipeline.DataTests) ... ok
test_observation_boundary (test_data_pipeline.DataTests) ... ok
test_partial_member_excluded (test_data_pipeline.DataTests) ... ok
test_path_traversal_rejected (test_data_pipeline.DataTests) ... ok
test_pickle_global_rejected (test_data_pipeline.DataTests) ... ok
test_preserve_existing_files (test_data_pipeline.DataTests) ... ok
test_selection_reproducible_balanced_unique (test_data_pipeline.DataTests) ... ok
test_zero_padded_frame_and_tar_order (test_data_pipeline.DataTests) ... ok
test_end_to_end_success_failure_and_no_label_input (test_data_pipeline.RunnerTests) ... ok
test_run_directory_is_exclusive (test_data_pipeline.RunnerTests) ... ok

----------------------------------------------------------------------
Ran 41 tests in 0.131s

OK

```
