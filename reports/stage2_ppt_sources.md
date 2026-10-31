# PPT 数据来源与口径

- 第1页：reports/stage2_final_metrics.json；固定旧100-case
- 第2页：outputs/stage2_analysis/gallery.json；真实样本0.jpg和input.json
- 第3页：src/worldnav/geometry.py、protocol.py；固定Track1协议
- 第4页：configs/eval_100.json、dev_12.json；stage2_preregistration.md
- 第5页：run_qwen_api.execute_case；research_policy.py；trajectory_plan.py
- 第6页：stage2_recomputed_metrics.json；独立原始响应重算
- 第7页：stage2_selection.json；各stage2_dev运行；原V1/V2/V3开发集
- 第8页：stage2_final_metrics.json；old_Base_vs_V3、old_V3_vs_new、full_control
- 第9页：outputs/stage2_analysis/gallery.json；自动排序选择；真实输入与轨迹
- 第10页：stage2_deep_analysis.json；原始预测重算；有效子集统计
- 第11页：stage2_data_audit.json；stage2_freeze.json；测试输出；完整Manifest
- 第12页：stage2_model_access.json；数据采样记录；固定公开评测代码
- 第13页：stage2_selection.json；stage2_final_metrics.json；完整实验报告

SR/Score以计划分母，失败记零；ATE/RPE/F/H为有效子集。CI固定5000次配对bootstrap、种子20261031，仅描述相应样本的重采样。新完整归档集与旧集分别汇总，禁止跨集直接作配对。图像和指令仅来自项目真实样本；坐标示意是动作协议说明，非实验结果。原始数据与完整API响应仅本地保存。请求Prompt哈希不含日志文本额外的末尾换行，文件哈希另列。配置清单与运行清单哈希可能不同（运行时补入指令并交错调度）；配对检查逐例图片、指令与轨迹哈希一致。

## 生成时证据哈希

- `reports/stage2_final_metrics.json`：`18bd1e4f67046f0dd6719184ad84a531f0446e036fbc23a1e84889d624c9bb75`
- `reports/stage2_data_audit.json`：`2fab982ac24c3a6d14421367c96285b48c26c04b9130c9a5967e8db09a5ae598`
- `reports/stage2_deep_analysis.json`：`2cd916b284b4071935c3c994491c93e9e2e393ecd92a3ab796539a92ae669ae5`
- `configs/eval_100.json`：`b7151e01e00f9b3588c44cae9d10de0d32bba8e3f7a17789b9187403af4eef44`
- `configs/eval_100_full_stage2.json`：`b4037013b04d578afc167828c00cffa5bfcacd8067cbe3bbc2c7d83ee7e6f8cf`
- `configs/dev_12.json`：`8a620ce64c01ee3f93b042288acd051c5afd15ea1cdba66bc6706a61e144a304`
- `vendor/track1/demonstration.py`：`04c6d0428df44321697147f99e274920d6e5ab8ac19436e7d3070b61037c5db4`

PPTX SHA256：`cbdaf6705e538e86a8e19598d826f377d8c119dff2e3bee7ea5778ad00b3ecf3`
