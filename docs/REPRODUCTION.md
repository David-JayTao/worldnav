# 复现指南

```sh
git clone --recurse-submodules https://github.com/David-JayTao/worldnav.git
cd worldnav
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements-cpu.txt
sh scripts/run_smoke_test.sh
```

CPU 环境只用于数据、协议、指标和测试。原服务器的项目 venv 已只读继承已有用户环境；不修改该环境。干净机器按上面的独立安装复现。

Smoke 默认创建新的 `outputs/smoke_<时间>/`，保留 `outputs/first_round/`。使用已有 16 MiB 缓存或从官方 pinned 数据集获取少量样例。未运行 GPU 或训练后的模型。

验证数据（只取 seen/unseen，不取 train）：

```sh
python scripts/download_validation.py --data-root "$WORLDNAV_DATA_ROOT"
```

数据根目录由环境或命令指定，仓库不包含原始数据或权重。下载保留 `.part`，再次运行续传；完整大小和 SHA256 必须匹配 `configs/datasets.json` 才更名为 `.tar`。

模型环境、100-case 抽样和运行入口将在工程里程碑中补充，当前不要将 CPU smoke 命令当成 baseline 命令。
