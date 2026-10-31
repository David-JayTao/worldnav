# 阶段成果索引

- [会议完整汇报](meeting_2026-10-31.md)
- [10 页 PPT](WorldNav_阶段进展汇报_20261031.pptx)
- [口头讲稿](meeting_2026-10-31_speaker_notes.md)
- [Qwen 基础实验](qwen_baseline_report.md)、[优化实验](optimization_report.md)、[配对对照](model_comparison.md)
- [Cosmos 调研与阻塞](cosmos_report.md)
- [实验摘要、逐例配对指标、CPU 测试输出和数据状态](evidence_20261031/)

Qwen 基础版 100/100 有效，优化版 98/100 有效；二者是同一模型的不同 Prompt，不能称为两个模型 baseline。Cosmos 尚未运行，GPU 分配为 0。100-case 来自部分归档前缀，不能代表完整验证集。

Git 保留源代码、固定配置、清单、报告和轻量验证证据。原始数据、模型权重、含完整输入的运行目录及本地缓存保存在服务器，不直接上传；复现方法见 docs/REPRODUCTION.md。PPT 中的数据下载量为生成时快照，最新检查见 evidence_20261031/current_status.json。
