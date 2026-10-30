# 项目真实状态

2026-10-30：Repository Bootstrap / Engineering & Baseline Pipeline。

## 已确认的历史成果

- 首轮读取 9 个 val_seen episode（3 个底层轨迹组）。
- 模型前向成功 0 次，baseline 评估 0 次，全部 baseline 指标未测。
- 参考标签坐标回环最大误差 8.88e-16；公开 demo 指标调用成功。
- 13 类非法/不完整格式被拒绝。最近一次历史 smoke 为 5.138 秒。
- 原始结果完整保留在未跟踪的 `outputs/first_round/`，公开版本仅包含脱敏报告和状态摘要。
- 旧 README、报告、脚本在 `local_archive/bootstrap_20261030/` 保留原件，防止脱敏/重构丢失历史。

## 审计发现

- 根项目原先没有 Git；两个 vendor 自带 Git 且固定到指定版本。
- 已有三个脚本实现 CPU smoke 和格式校验；无独立测试套件。
- 原 smoke 会覆盖 first_round 输出，已改为新运行目录；数据同名文件内容不符即拒绝覆盖。
- 原脚本/报告存在用户绝对路径，公开副本已改为变量或项目相对路径。
- `outputs/first_round/` 内 HTML、JS、API 快照是调研证据，原样保留在本地，不提交公共仓库。
- bytecode、虚拟环境和原始 GPU/环境日志均排除在版本管理之外。

## 当前阻塞

- 未确认可用的 LCVN-Uni 导航训练 adapter 和配套 tokenizer/processor。
- 现有 Transformers 与官方 fork 不匹配；尚未安装完整 GPU 环境。
- 初始数值位姿、世界坐标动作和 26 步限制需要适配；未经真实推理验证。
- 完整官方 CodaBench manifest 尚未取得；本地抽样不能称为官方完整 ID 校验。
- 本轮用户明确禁止 GPU 推理/训练；下一次须用户确认并重新核对空闲 GPU。

本阶段后续完成情况以各提交及文末追加的验证记录为准。下载、测试、推理三个状态分别记录，不能相互替代。

## 2026-10-31 核实追加

- CPU 环境、输入隔离、坐标/协议和独立实验目录均已建立；官方 submodule 受跟踪源文件保持原样。
- float32 相减精度问题已修复；100 条参考轨迹世界坐标回环误差最大 1.42e-14，仅为参考控制。
- 固定前缀 provisional/debug 清单已有 100 条（50/50、各 split 指令类型 17/17/16、100 个不同轨迹内容哈希）；原始清单 SHA256 为 b7151e01e00f9b3588c44cae9d10de0d32bba8e3f7a17789b9187403af4eef44。
- seen 全包 7,409,704,960 bytes，官方 SHA256 已通过；10,806 episode、189,873 图片、10,806 轨迹文件均完成 CPU 解码/结构审计，图片/位姿数量不匹配为 0。unseen 部分文件保留并续传，未进行整包校验。
- 训练 delta 在 100 条元数据上经角度 wrap 后与世界差分一致；5 条参考轨迹超过 26 步，最长 30 步。详见 PROTOCOL_AUDIT。
- Qwen API 路线由用户新增授权，只向指定 SinapisAI endpoint 发送初始 RGB 与指令；本机 GPU 仍为 0。具体完成数量与分数以本地 runs 摘要和本次会议报告为准。
- LCVN 任务 checkpoint 仍未取得；Cosmos 仅有 CPU 输入/输出契约，不具备真实导航模型验收结果。
- 旧会议稿 MEETING_BRIEF.md 仍是待审核历史草稿，不提交。最新任务禁止自动公开 push；保留本地提交。

## 冲刺任务授权与运行（2026-10-31）

用户新任务明确取消旧 10 次请求限制，授权完成基础 100-case、独立 12-case 三版 Prompt 对照和候选版正式测试。先导 10 次记录保留，仅复用同配置的 9 条有效预测。基础实验目录为 `runs/qwen_api_100case_baseline`；开发集和候选目录分别为 `qwen_prompt_ablation`、`qwen_api_100case_optimized`，进度以各自 summary.json 为准。

已实现原子保存、有限网络和格式重试、429 降并发、持久预算、源码快照、离线复算、原始响应恢复和失败归档重跑。开发集与正式集轨迹哈希交集为 0，每 split 风格为 2/2/2。测试日志为 `logs/tests_sprint_20261031.log`。

会议 PPT、报告和逐页讲稿已实际生成初版，仍须在实验结束后重建并核验最终数字。Cosmos 额外检查发现公开 Space 的模型代码固定官方 revision，但 Space 为 PAUSED；未获得运行权限，不擅自启动他人的资源。本轮不自动 push GitHub。
