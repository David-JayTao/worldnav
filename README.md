# WorldNav：视觉语言导航实验

RoboWorld 2026 Track 1：根据一张初始 RGB 和一句导航指令，预测完整开放环动作轨迹。本机获分配 GPU 为 **0**；使用远程 SinapisAI `qwen/qwen3.8-27b` 开展真实 API Zero-shot 实验。当前完成数量和指标以 `runs/*/summary.json` 为准，会议材料由真实文件自动生成。

## 当前成果与边界

- 已跑通真实图片 API → 严格动作解析 → 当前机体坐标积分 → 官方公开指标 → 逐样本结果和轨迹图。
- 固定本地 100-case：50 seen、50 unseen、100 个不同轨迹内容哈希，各 split 风格 17/17/16。数据来自冻结归档前缀，不代表完整验证集均匀抽样。
- 独立开发集 12 条：两 split 各 6、各风格 2，与正式集轨迹组完全不重叠；V1/V2/V3 Prompt 只在开发集选型。
- seen 全包通过大小、SHA256 和逐图审计：10,806 episode、189,873 图片；unseen 本轮恢复续传并进行完整审计，最新状态见第二阶段报告。原有数据和实验均保留。
- Cosmos：当前 SinapisAI 无路由，NVIDIA 无现有授权且匿名图片请求 401；公开 Space 暂停。尚无 Cosmos 导航分数。
- LCVN-Uni：缺少已确认的导航训练 checkpoint；本地适配未经过真实 GPU 验证。
- API Zero-shot 结果不是官方 LCVN-Uni baseline，公开指标也不宣称等同于私有评分器。

## 代码来源与结构

- [Track 1](https://github.com/roboworld2026/track1)，固定 `a52e43fd68edcd413436c2466a3177046002964b`。
- [LCVN](https://github.com/UWMILab/LCVN)，固定 `e6a52e65901a10e4581a0431944aad6e56355ef7`。
- `src/worldnav/`：隔离输入、几何、协议、公开指标、Policy、API 和独立 Uni/Cosmos 准备。
- `configs/`：数据来源、固定清单、Prompt/请求配置、GPU 禁用策略；无 API Key。
- `scripts/`：下载、审计、推理、断点恢复、分析、报告/PPT；`tests/`：纯 CPU 和 Mock 测试。
- `runs/outputs/logs/data/local_archive`：原始结果和证据，仅本地保存；`reports/`：报告、PPT 和逐页讲稿。

## 环境和测试

仅在用户指定的独立环境安装依赖：

```sh
"$HOME/.venv/bin/python" -m pip install -r requirements-api.txt
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 "$HOME/.venv/bin/python" -m unittest discover -s tests -v
```

另有先前 `.venv-cpu`，不需要为了 API 删除或重建；共享环境不修改。

## 数据和正式实验

先将 `WORLDNAV_DATA_ROOT` 设为已有数据目录。密钥从项目外配置文件读取，不写进仓库：

```sh
. "$HOME/.config/worldnav/api.env"
"$HOME/.venv/bin/python" -c 'import os; print(bool(os.getenv("SINAPISAI_API_KEY")))'
"$HOME/.venv/bin/python" scripts/download_validation.py --data-root "$WORLDNAV_DATA_ROOT"
sh scripts/run_api_sprint.sh --manifest configs/eval_100.json --api-config configs/qwen_base_100.json --data-root "$WORLDNAV_DATA_ROOT" --run-dir runs/qwen_api_100case_baseline --resume
```

`--resume` 用于已存在实验，首次运行去掉该参数；每个实验冻结配置，不覆盖历史。当前 sprint 已获用户明确授权超过旧 10 次限制，并以有限请求预算、最多 4 并发、有限重试执行。先导目录 `runs/qwen_api_100case` 保留历史 10 次请求，不与不同 Prompt 混用。

## 离线复算与会议材料

```sh
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 "$HOME/.venv/bin/python" scripts/analyze_sprint.py --run-dir runs/qwen_api_100case_baseline --data-root "$WORLDNAV_DATA_ROOT"
"$HOME/.venv/bin/python" scripts/build_meeting_ppt.py
```

PPT 为原生可编辑元素、真实图片和轨迹图，路径：`reports/WorldNav_阶段进展汇报_20261031.pptx`；完整报告和逐页讲稿同目录。重建会归档旧版本。

详见 [复现指南](docs/REPRODUCTION.md)、[协议核查](docs/PROTOCOL_AUDIT.md)、[项目状态](docs/PROJECT_STATUS.md)、[权重和环境](docs/CHECKPOINT_AND_ENVIRONMENT.md)。按最新授权，在核对远端无冲突并通过公开内容审计后正常推送；禁止强制推送。


## 第二阶段科研冲刺

- 现场审计：[服务器报告](reports/server_audit_20261031.md)。
- 旧实验冻结与独立重算：[快照索引](reports/stage2_freeze.json)、[重算汇总](reports/stage2_recomputed_metrics.json)。
- 新策略在独立开发集先比较，参见 [预注册](reports/stage2_preregistration.md)。研究尺度、停止、转弯、结构化路线编译及JSON可靠性；不修改旧V3配置。
- 原始响应与预测仅本地保存；Git保留脱敏报告与演示。新全归档100-case是独立版本，不与旧前缀样本混算。
