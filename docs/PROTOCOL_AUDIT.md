# WorldNav 协议核查（2026-10-31）

## 一手证据与适用范围

- 固定 [Track 1 README](https://github.com/roboworld2026/track1/blob/a52e43fd68edcd413436c2466a3177046002964b/README.md)：Task Definition、Submission Format、Evaluation。
- 固定 `vendor/track1/demonstration.py`：公开指标数学实现，非提交服务器私有 scorer。
- [CodaBench 官方页面](https://www.codabench.org/competitions/18185/)的 Submission & Evaluation，已重新读取公开 API 内容；本地证据 `logs/bootstrap_sources/coda_20261031.txt`。
- 固定 LCVN `e6a52e65901a10e4581a0431944aad6e56355ef7` 的 `scripts/navigation.py`、`action_utils.py`、`prompt_builder.py`、`customize_trainer.py`。

## 输入、输出与坐标

1. 输入只有一张初始第一视角 RGB 和一条语言指令；无真实终点、数值初始位姿、未来帧或环境反馈。Qwen policy 接口只接收隔离的 Observation。
2. 每个 episode 输出可变长 `[dx,dy,dyaw]` 列表：当前机体坐标前向、左向、逆时针 yaw 增量。yaw 单位是 rad；官方限值以 dataset coordinate units 表述。LCVN prompt 使用 meters，但不应把跨数据来源的尺度校准当作已证明。
3. 平移使用当前 yaw，之后更新 yaw。世界增量转机体使用 `R(-yaw)`，角度按官方规范归一化到 `[-pi,pi)`。现有核心坐标逻辑有官方公式、手算及真实数据回环支持，本轮未改变坐标约定。
4. 最多 64 个动作；`hypot(dx,dy)<=2.46`，`abs(dyaw)<=6.29`。序列结束即终止，无独立 Stop token。**全零动作是合法静止步，不能擅自当作 Stop**；本轮移除了本项目 Uni 适配器的零动作提前终止逻辑，保留显式 Stop 解析。
5. JSON 为 `{split, episodes:[{episode_id, actions}]}`；phase 1 ZIP 根目录需两个验证 split JSON，phase 2 需 test.json。固定 100-case 子集 ZIP 只能验证本地协议，不能冒充完整官方提交。

## 已证实的 LCVN 差异

- `action_utils.calculate_action_delta` 直接返回世界坐标差；`navigation._prepare_actions` 优先使用 delta；prompt 却用 facing direction 描述 dx。不能直接把训练 delta 当作当前机体动作。
- `navigation.py:151` 等将真实起点数值写入 prompt；`customize_trainer.py:1173` 从参考 coords 取起点。本地 Qwen 不调用这些训练输入路径。
- `navigation.py:66` 采用 80/10/10 划分；本项目严格按固定 split 清单加载。
- `customize_trainer.py:1189` 硬编码 max_steps=26，`:1278` 把零动作当作停止；均为参考实现行为，不能外推为比赛协议。
- 100 条真实元数据审计：delta 平移与世界差分一致（最大误差 2.89231538772583e-5），yaw 按模 2pi 比较最大误差 2.360902726650238e-7；100/100 在 1e-4 内一致。一条 yaw 跨界若直接相减会出现约 2pi 差异，因此不能误报数据错误。证据：`logs/protocol_data_audit_wrapped_20261031.json`。
- 此清单 5/100 条参考动作超过 26 步，最长 30 步；26 步确实可能截断此子集。参考步数没有进入模型 prompt。Qwen 直接预测最多 64 步，不使用 Uni 的 26 步循环。

## 公开指标与失败统计

调用固定 demonstration 的 SR、ATE、RPE、Full-route fidelity、Heading/turn fidelity，并按官方 README 公式逐 episode 计算 Score。参考轨迹先旋转到初始机体坐标，以和仅图像输入的预测共同评分；模型不接触该变换所用的标签。

SR 阈值取 `max(reference_average_step,1.5)`，其中 average_step 来源是本地明确选择的参考步长；私有 scorer 同源性未证实。ATE/RPE 对短预测按公开实现重复最后位置，不截短参考。

API runner 明确报告请求成功率、合法预测率、评测覆盖率、失败分类和未运行数量。主摘要同时提供成功评估子集的各项均值和失败记零的 Score；失败样本 ATE/RPE 不伪造有限值。完整 100-case 未执行时，不提供伪造的全量均分。
