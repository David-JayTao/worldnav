# Prompt 优化实验



V1：原始零样本；V2：按可行路径、地标、转弯和停止位置进行内部结构化规划；V3：强化单位、坐标、动作粒度与保守尺度先验。未请求隐藏思维链，三个版本输出仅 JSON。

| Prompt | 完成/12 | SR（有效子集） | 失败记零 Score |
|---|---:|---:|---:|
| V1 | 12 | 0.167 | 16.958 |
| V2 | 12 | 0.000 | 19.279 |
| V3 | 12 | 0.083 | 21.617 |

选择证据：`{"development_scores": {"1": 16.957754342847426, "2": 19.27851019442929, "3": 21.617121450869167}, "selected_variant": 3, "selected_beats_development_baseline": true, "selection_metric": "failure-zero mean Score on 12 independent development cases", "formal_test_metrics_used": false, "selected_config_sha256": "53f0df2d2ab5918e2bc66425e9fb75a352c958331117739cbc8bb44d78854003"}`。选择只读取开发集，正式集指标不用于选参数；若非基础最优，仍明确报告候选未胜出，不改写负结果。候选正式集有效评估 98 / 100，Prompt 版本 qwen_worldnav_scale_v3。

配对分析（正式集完成后计算）：Score 差值 16.716，95% 配对 bootstrap 区间 [11.361382345134816, 22.06429110701694]；提升/下降/持平 58/15/27。数据键、图片/元数据哈希和指令均须一致才允许比较。小开发集和前缀抽样限制了可外推性。

此区间仅反映当前 100 个本地样本的重采样波动，不证明完整验证集的泛化性能。
