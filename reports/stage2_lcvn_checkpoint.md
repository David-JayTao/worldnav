# LCVN-Uni 任务权重现场复核

本轮重新读取了[官方仓库 README 的 LCVN-Uni 部分](https://github.com/UWMILab/LCVN#-lcvn-uni)。该部分提供独立环境、训练和评测入口，要求自行配置 checkpoint 路径；未在该节找到能直接验收的导航任务权重下载链接。

本地固定子模块版本仍为 `e6a52e65901a10e4581a0431944aad6e56355ef7`，未更新 vendor 代码。当前本地没有经过验证的任务 adapter、扩展 tokenizer/processor、基座版本和权重哈希组合。这个结论不等于证明互联网所有位置都没有权重，也不把通用基座权重当作任务训练产物。

当前 GPU 分配为0；没有执行训练、CUDA模型加载或本地推理。下一步需要团队/作者提供完整任务产物与对应命令，取得授权GPU后先做1例严格加载和动作协议验证。LCVN-Uni 与 Cosmos 的输入处理及动作解析保持独立。
