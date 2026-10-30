# 权重来源与环境状态

核查日期：2026-10-30。GPU 分配数量为 0；没有模型加载、训练或推理，没有下载大型权重，没有编译 CUDA 依赖。

## LCVN-Uni

| 核查来源 | 结论 |
|---|---|
| [官方仓库](https://github.com/UWMILab/LCVN)及固定代码 | 推理依赖任务 adapter/tokenizer；未确认可用公开导航训练产物 |
| [Releases](https://github.com/UWMILab/LCVN/releases) | 核查时无可用发布产物 |
| [Issue 7](https://github.com/UWMILab/LCVN/issues/7)及历史 Issue 1/6 | 未找到可核验的完整下载与匹配说明 |
| [HF 模型搜索](https://huggingface.co/models?search=LCVN)与数据发布者模型列表 | 未确认训练后 Uni checkpoint |
| [论文](https://arxiv.org/html/2603.26741v1) | 指向官方仓库，未核实额外 checkpoint 链接 |

这些是已检查来源的结论，不证明互联网不存在其他权重。原始证据保留在本地 `logs/bootstrap_sources/` 和 `outputs/first_round/`，不公开原始日志。

公开基座候选 [leloy/Anole-7b-v0.1-hf](https://huggingface.co/leloy/Anole-7b-v0.1-hf)，revision `96df52301e844d8a624a13953051ead4c008343b`；权重约 14.30GB，配置 vocab 65536、上下文 4096。它不是 LCVN 训练 checkpoint，与未知 adapter 的匹配尚未确认。

需要索取：训练后 `adapter_model.safetensors`、`adapter_config.json`、完整 tokenizer（含扩展动作 token）、processor、训练后的输出头/必要输入 embedding、准确基座 ID/revision、文件 SHA256、推理命令、初始位姿与动作坐标约定。未向作者发送消息。

独立 CPU 环境 `.venv-cpu` 已创建，依赖 `requirements-cpu.txt`。历史共享环境没有修改。Uni GPU 依赖方案位于 `configs/requirements-uni.txt`，**尚未安装或验证**：torch 2.4/torchvision 0.19，官方使用的 Transformers fork commit `dae439cb93e7c2ef61943554b7a2f4590c2118cd`（版本 4.45.0.dev0）、PEFT 0.12、accelerate 0.33；FlashAttention 2.5.9.post1 必须核对 Python/CUDA/torch/ABI，不能自动大规模编译。CPU 包版本是本工程已测版本，不宣称等同原训练环境。

## Cosmos-Reason2-8B

[官方模型](https://huggingface.co/nvidia/Cosmos-Reason2-8B)元数据核查：revision `a9fae2cf89dc64db96b12860417f0eb403013bb9`，gated=auto，8,767,123,696 个 BF16 参数。仅获取小型元数据，没有下载权重；是否接受许可、是否已有本地团队缓存仍待确认。

[官方前置要求](https://docs.nvidia.com/cosmos/latest/prerequisites.html)列出 8B 最低 32GB GPU 显存，主要验证 Hopper/Blackwell；不能假设单张 24GB 3090 足够，双卡显存也不会自动合并。[官方推理参考](https://docs.nvidia.com/cosmos/latest/reason2/reference.html)要求 Transformers >=4.57.0；必须与 Uni 的旧 fork 分开环境。实际多卡分片、量化、上下文和注意力后端均未测试。

已完成 `src/worldnav/cosmos.py` 的纯 CPU prompt 和严格 JSON 解析契约与测试。未完成 processor 实际预处理、模型加载、生成、导航动作语义验证与质量评估；此模块不代表 Cosmos 适配完成。后续优先复用团队经过验证的环境和 prompt，再固定版本、许可证、权重哈希与实验配置。不得通过 CPU 强跑完整 8B 模型替代 GPU 实验。

## 2026-10-31 API 路线更新

新增的真实推理发生在远程 SinapisAI Qwen 服务，本机未加载 CUDA 或 8B 模型；这不改变本文关于 LCVN 训练产物缺失和 Cosmos 本地部署未验证的结论。Cosmos 额外检查了 SinapisAI 全目录（无该模型）、NVIDIA 匿名真实图片请求（401）、公开 HF Space `gulle1155/Cosmos-Reason2-8B`（固定官方 revision，但 PAUSED/503）。未使用不明密钥、未新建账户或购买服务，详见最新 cosmos_report。
