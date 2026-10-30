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
