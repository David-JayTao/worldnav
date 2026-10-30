# 任务接口与实验假设

模型只接收 `Observation(image, instruction)`，图像是初始 RGB；参考位姿、未来帧、终点、ID 和文件路径不传给 policy。CPU 输入完整性审计允许读取标签；批量推理先保存模型预测，再独立读取标签评分。数据按照指定 seen/unseen 清单加载，不调用官方 loader 的随机 80/10/10 划分。

## 坐标和输出

动作 `[dx,dy,dyaw]` 使用当前机体坐标：先按当前 yaw 旋转平移，再更新 yaw。世界位移转局部使用 `R(-yaw)`；角度连续积分，增量归一化到 `[-pi,pi)`。原始 float32 数值先转双精度再相减，避免差分精度损失。手算 90 度转向、跨 ±pi 和真实参考轨迹回环均有检查。

最多 64 个动作；平移向量模长最多 2.46，绝对 dyaw 最多 6.29。JSON 拒绝 bool、NaN、重复键、重复 ID、漏维度和超限动作；ZIP 必须在根目录放置指定 phase 文件。全量 ID 校验必须提供完整官方清单；本地清单格式通过不能称为官方可提交结果。

## LCVN-Uni（实验性，尚未真实模型验证）

`uni.py` 调用固定版官方 Anole 类、prompt builder 和 image splitter。官方 wrapper 的 generate 返回 `(ids, None)`，并内部指定采样；适配层据此处理，避免重复传 do_sample。严格解析专用 dx/dy/dyaw bin token，缺项不补零。

真实初始数值位姿不可用，因此当前策略固定 canonical zero；将模型世界增量按累计预测 yaw 转为局部动作。此策略会改变训练输入分布，尚不能声称复现论文。不同 checkpoint 的动作含义必须向作者确认。

默认保留 26 步。每步仅使用初始图像和当前生成图像；memory bank 关闭。448 分辨率、784 图像 token，生成预算 834 token，检查 prompt+生成预算不超过配置上下文（候选基座 4096）；超长输入明确失败，不静默截断。改到 64 步仍需真实结束机制、显存与轨迹质量测试。

checkpoint 必须有来源、精确基座 revision 和每个加载文件 SHA256；需要训练 adapter、输出头及必要的扩展输入 embedding。只加载一次 PEFT 并核对恢复后的每个 tensor。无 checkpoint 则阻止加载，不使用基座或随机参数代替任务权重。

## Cosmos（只有 CPU 契约）

`cosmos.py` 独立构建单图像/指令消息，解析严格 JSON body-frame 动作，拒绝 LCVN token、markdown、额外字段和非法数值。prompt 和协议是本项目拟定，尚未验证模型遵循率、动作尺度或导航能力。没有 Cosmos 模型 loader；禁止将其误路由到 Uni。共享的是 Observation、最终动作验证和评分，不共享专用输出解码逻辑。

## 指标与失败

直接调用固定 `vendor/track1/demonstration.py` 的公开指标。使用参考轨迹平均步长作为 SR 阈值来源，是明确的本地选择；公开 demo 与 CodaBench 私有 scorer 一致性未验证。记录 SR、ATE、RPE、两类 fidelity 和组合 Score。聚合仅统计成功评估样本，同时必须报告尝试数、失败数及原因，不能只展示成功子集均分。

参考标签回环与人工 unit-test policy 只用于数学/工程验证，所有产物显式标记，不能记作 baseline。
