# Cosmos Reason2-8B 接入核查



现有 SinapisAI 模型目录 387 项，无 Cosmos 路由。NVIDIA_API_KEY、NVIDIA_NIM_API_KEY、NGC_API_KEY、NGC_CLI_API_KEY、HF_TOKEN 及用户标准配置路径均未发现可用授权。NVIDIA 模型目录列出 nvidia/cosmos-reason2-8b，但向该 endpoint 发送不带认证的真实图片请求返回 HTTP 401。未把 SinapisAI Key 发往 NVIDIA。

官方旧 build 页面当前跳转到 Cosmos3 Nano Reasoner，不能替换后声称跑过 Reason2-8B。没有新建账户、购买服务或使用不明 Key；Cosmos 有效推理 0 / 100，指标未测。对照表必须写“未运行/授权缺失”，不能填 0 分或冒充已完成。官方来源见 cosmos_report.md。

额外找到公开 `gulle1155/Cosmos-Reason2-8B` Space，源码固定官方权重 revision `a9fae2cf89dc64db96b12860417f0eb403013bb9`，但 Space runtime=PAUSED，主页和 /v1/models 均返回 HTTP 503；没有权限启动他人的 Space。该路线目前同样无法推理，已保留代码版本和状态证据。



一手来源：[NVIDIA 模型目录](https://integrate.api.nvidia.com/v1/models)、[官方 build 页面](https://build.nvidia.com/nvidia/cosmos-reason2-8b)、[NIM API 文档](https://docs.nvidia.com/nim/vision-language-models/1.7.0/examples/cosmos-reason2/api.html)。本地证据：logs/cosmos_route_check_20261031.json、logs/cosmos_nvidia_noauth_check_20261031.json。
