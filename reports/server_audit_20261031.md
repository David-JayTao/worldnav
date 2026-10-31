# 服务器审计：第二阶段科研冲刺

依据本地 Git、文件、进程和结果记录检查；检查时间见 `logs/stage2_initial_audit.json`（UTC）。

- 仓库：worldnav-baseline；分支 main；起点提交 ee1d633395b583e82fe64164555961aa2ddf66d6；远端同 SHA，无分叉。
- 开始时 staged/unstaged/untracked 均为空；两官方子模块版本与既有报告一致。未发现适用于本仓库的 AGENTS.md。
- 无 tmux 会话；旧 API 实验已结束。Base100有效、V3候选98有效/2格式失败；开发集 V1/V2/V3 各12例。已有摘要、原始响应与轨迹，下一步独立重算，不覆盖旧目录。
- 现有 SinapisAI 配置文件存在，Key 配置布尔值：True；不输出凭据。NVIDIA 标准环境变量未配置。GPU按分配0处理。
- seen完整归档存在，旧审计10806 episodes/189873图片；unseen现有17656210943/20311838720 bytes（86.93%），旧下载已停止，无完整归档或整包校验。磁盘剩余约2.2T。
- README/REPRODUCTION 仍残留“后台续传”和“禁止自动推送”历史描述；最新用户允许正常安全推送，需按现场更新。
- 正式清单与开发清单、Prompt、运行脚本、分析脚本和PPT生成脚本已检查。旧指标不是私有CodaBench成绩。
- 阻塞：完整unseen依赖外部下载；Cosmos无已验证授权；LCVN缺任务权重和GPU。其余CPU与现有授权API工作可独立推进。

## 后续证据

冻结目录与SHA256见本轮快照清单；重算、数据下载和新策略实验分别写独立日志。原始结果不入Git，不覆盖旧实验，不强制推送。
