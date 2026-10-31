# WorldNav API 实验复现

## 1. 环境和凭据

```sh
"$HOME/.venv/bin/python" -m pip install -r requirements-api.txt
. "$HOME/.config/worldnav/api.env"
"$HOME/.venv/bin/python" -c 'import os; print(bool(os.getenv("SINAPISAI_API_KEY")))'
```

密钥目录/文件权限应为 700/600，凭据不存入项目或日志。不使用 `set -x`。SinapisAI Key 只发送至 `https://api.sinapisai.com/v1`，重定向关闭。GPU 始终禁用；无 CUDA 或本地 8B 模型加载。

CPU / Mock 测试不消耗真实 API：

```sh
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 "$HOME/.venv/bin/python" -m unittest discover -s tests -v
```

`requirements-api.txt` 固定当前 SDK 和 CPU 包。PPT 使用 python-pptx；预览可用现有 LibreOffice，并需要可用的中文字体。字体仅位于用户缓存/字体目录，不修改系统字体。

## 2. 数据

设置 `WORLDNAV_DATA_ROOT` 指向已有数据根。固定官方 revision、整包大小和 SHA 在 `configs/datasets.json`。只下载验证 split，不下载 train：

```sh
"$HOME/.venv/bin/python" scripts/download_validation.py --data-root "$WORLDNAV_DATA_ROOT"
"$HOME/.venv/bin/python" scripts/audit_validation.py --data-root "$WORLDNAV_DATA_ROOT" --output outputs/full_data_audit_new.json
```

整包哈希成功前不改名成 `.tar`。逐图片审计不全量解包。`scripts/complete_validation.sh` 提供有界自动续传，完整后完成整包审计；新全归档清单由独立的prepare_full_stage2.sh生成，不改本轮正式对照集。

`configs/eval_100.json` 是本轮固定正式本地对照集，来自冻结前缀，种子 20261030；SHA256 `b7151e01e00f9b3588c44cae9d10de0d32bba8e3f7a17789b9187403af4eef44`。50/50、每 split 风格 17/17/16，100 个不同轨迹内容哈希。原有清单通过 `build_eval_manifest.py --allow-partial` 再生时冻结前缀，不随下载增长变化。

`configs/dev_12.json` 为独立开发集，种子 20261031，6/6、每 split 风格 2/2/2，排除全部正式集轨迹组。生成入口：

```sh
"$HOME/.venv/bin/python" scripts/build_development_manifest.py --formal configs/eval_100.json --data-root "$WORLDNAV_DATA_ROOT" --output configs/dev_12.json
```

模型只读取初始 RGB 与独立 input.json 指令；参考轨迹在预测保存后才用于评分。去重和 CPU 数据审计不属于模型输入。

## 3. 基础实验与恢复

首次新实验（目录必须不存在）：

```sh
sh scripts/run_api_sprint.sh --manifest configs/eval_100.json --api-config configs/qwen_base_100.json --data-root "$WORLDNAV_DATA_ROOT" --run-dir runs/qwen_api_100case_baseline --seed-from runs/qwen_api_100case
```

已有本轮实验必须用 `--resume`，去掉 `--seed-from`。相同配置的 9 条有效先导结果会核对模型、Prompt 哈希、图像哈希和指令后复用，原目录不改。

中断恢复增加 `--recover-incomplete`：存在有效原始响应就离线完成，不再请求；没有可用响应则先归档再请求。失败重试使用 `--retry-failed`，每 case 有界归档，已评估成功 case 始终跳过。所有新请求都占用持久预算槽，超时也计入，禁止删除预算账本重置消费计数。

本轮用户授权 ID 为 `worldnav_sprint_20261031`，明确取消旧 10 次请求限制。正式配置 max_requests=200、并发 3、网络最多 2 次重试、格式最多 1 次重试；429 降并发，认证/额度 HTTP 错误停止后续付费请求。此授权不代表价格或账户余额已经核实，货币费用仍以服务方账单为准。

## 4. 开发集与候选版

V1/V2/V3 在同一 12-case 开发集运行，代码 `src/worldnav/prompts.py`，配置 `qwen_dev_v*.json`。依次运行 `scripts/run_prompt_ablation.sh`；运行中的脚本应保持原样，避免重复启动。

选择器只读取开发集的失败记零 Score，冻结最强的非基础候选为 `qwen_optimized_100.json`；即使未胜过 V1 也如实记录，再做同一正式集配对测试，不根据正式集得分重选或缩放。

开发阶段每个任务并发 1，与基础实验并发 3 组合不超过 4。候选正式实验等待基础任务结束后使用并发 3。

## 5. 长时间运行

tmux 会话：`worldnav_qwen_base`、`worldnav_qwen_ablation`、`worldnav_validation`。输出在 `logs/sprint_*.log` 和 `logs/validation_complete_20261031.log`；每个实验的 `logs/process.json` 保存 PID 和状态。不要对同一实验启动两个 runner，文件锁会拒绝。

## 6. 复算、诊断和 PPT

```sh
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 "$HOME/.venv/bin/python" scripts/analyze_sprint.py --run-dir runs/qwen_api_100case_baseline --data-root "$WORLDNAV_DATA_ROOT"
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 "$HOME/.venv/bin/python" scripts/analyze_sprint.py --run-dir runs/qwen_api_100case_optimized --data-root "$WORLDNAV_DATA_ROOT"
"$HOME/.venv/bin/python" scripts/build_meeting_ppt.py
```

离线复算从原始 response 再解析动作，核对预测、轨迹和每个指标；不调用 API。诊断输出路径长度比、终点/航向误差、步数与转弯统计，不用于正式集调参。图像只用于事后展示。PPT 和报告由磁盘真实摘要生成，旧版本保存在 local_archive。

## 7. 模型切换与限制

Qwen 入口固定 SinapisAI 和目标模型，不能把 Key 改发其他 Provider。Cosmos 的输入/输出契约独立保留；已检查 NVIDIA 公共目录、匿名图片请求、现有凭据和公开 Space，但当前缺授权/运行服务，不能把接口准备当成推理完成。LCVN-Uni 需匹配任务 checkpoint、独立环境和用户明确分配 GPU。

## 8. Git

仅显式 add 可公开源代码、测试、脱敏配置和文档；运行 `git diff --cached --check` 和 `scripts/audit_public.py`。runs、数据、权重、日志、环境排除在外；会议成果已获用户上传授权。最新阶段允许安全正常推送：先中文提交、核对远端、审计公开内容，禁止强制推送。

## 9. 已完成候选实验的直接恢复命令

```sh
sh scripts/run_api_sprint.sh --manifest configs/eval_100.json --api-config configs/qwen_optimized_100.json --data-root "$WORLDNAV_DATA_ROOT" --run-dir runs/qwen_api_100case_optimized --resume
"$HOME/.venv/bin/python" scripts/compare_experiments.py --base runs/qwen_api_100case_baseline --optimized runs/qwen_api_100case_optimized --output runs/model_comparison/paired.json
```

已完成 case 不再发出 API 请求；复算无需 Key。两条格式失败保留为失败，不在冻结正式集上反复请求直至成功。


## 10. 第二阶段研究流程

先查 `reports/server_audit_20261031.md` 和 `reports/stage2_freeze.json`。不可重复启动已完成实验；快照脚本每次创建独立只读目录，SHA256全索引见 `reports/stage2_frozen_sha256.json`。

- 旧数据独立重算：`scripts/recompute_stage2.py`，输出新目录，不改旧运行目录。已存在输出时拒绝覆盖，复核可直接调用模块内 `recompute(run, data_root)`。
- 开发集：`scripts/run_stage2_research.sh`，顺序比较Scale/Stop/Turn/Structured/RobustJSON及独立视觉模型，最多3并发、每候选36请求；JSON先做单例能力检查。不要在已有tmux任务时重复启动。
- 冻结：`scripts/select_stage2.py`只读取开发集指标；配置已存在时核验哈希和开发选择一致，复用原冻结证据，禁止重新选择。候选正式实验仅执行一次，两条旧V3格式失败保持原样。
- 完整数据：`scripts/complete_validation.sh`从现有part续传，内层4次指数退避、外层3次有界循环，完成后全包SHA256和逐图片审计。固定来源在configs/datasets.json，不重复下载已有字节。
- 新完整归档清单：`scripts/prepare_full_stage2.sh`，种子20261101，排除旧正式集与dev12全部轨迹组；新清单仅在完整文件哈希正确时生成。按具有三种指令的轨迹组分层抽样，不声称全部episode等概率。
- 全归档新对照：`scripts/run_stage2_full_control.sh`等待候选冻结且旧正式实验结束，再顺序执行新清单Base与候选；不据新测试结果修改策略。
- 深入分析：`scripts/analyze_stage2.py`，原始响应解码、严格对照保存动作与指标，输出分组、误差分布和7组配对真实案例。不调用API，不改变模型输入。
- 最终复算：`scripts/finalize_stage2.py`，写最终指标、数据审计摘要与Markdown；`scripts/build_stage2_ppt.py`生成13页可编辑PPT和讲稿、数据来源。

所有Python入口使用已存在的独立API环境；CUDA_VISIBLE_DEVICES留空。原始证据位于runs/outputs/logs，Git只提交脱敏汇总，不上传原始预测或原始API响应。NVIDIA认证不可用时Cosmos记NOT RUN，不使用Sinapis密钥跨服务商请求。计费货币价格未知，仅统计实际请求与Token，不估造账单。


补充固定V3参照：`scripts/run_stage2_full_v3.sh`在完整归档Base与Turn结束后运行相同新清单的固定V3，不修改旧V3文本。它在旧集Turn增量CI跨零之后补充，不能称为起初预注册的设计；增加参照不参与新候选选择。

额外视觉路由：32B的三条样本各耗尽有限网络重试仍失败后受控停止，9次有记录的失败请求、3个未决预算槽保留；不把未决请求标为预测结果。`scripts/probe_stage2_vision8.sh`在三组完整归档实验结束后，用现有同服务商授权对官方声明视觉输入的8B做单例smoke，成功才做12例；45秒超时、网络重试0、格式重试最多1，不进行未经选择的正式100例，不与主实验并发叠加。

数据清单兼容说明：`eval_*`清单沿用历史的LCVN `model`字典（例如26步、canonical_world等），它不参与API runner的执行。API运行的模型和策略以独立`api_config.json`为准，动作语义由冻结Prompt、当前机体坐标积分和64步协议校验决定。本轮为保留清单哈希不更改这些历史字段；不要把清单中的旧LCVN元数据当作API实际执行参数。
