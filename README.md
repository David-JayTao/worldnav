# WorldNav 第一轮验证

当前结果：已使用官方 `val_seen` 中 **9 个 episode / 3 段轨迹**完成真实数据读取、坐标回环、官方公开评测函数和本地 JSON/ZIP smoke test。**模型成功推理 0 条；没有 baseline 成绩。** 尚未找到可用的 LCVN 专用 checkpoint，官方入口还存在依赖阻塞。

完整发现、指标定义、执行命令与未完成项见 [第一轮报告](reports/first_round.md)。

## 最短复现命令

```sh
cd ${PROJECT_ROOT}
sh scripts/run_smoke_test.sh
```

脚本只使用 CPU，默认离线，不启动训练、不申请 GPU、不上传比赛。首次缺少缓存时，仅通过 HTTP Range 获取验证归档前 16 MiB；不获取完整数据。重复运行复用缓存。日志写入 `outputs/first_round/smoke_test.log`。

项目 `.venv` 通过 `--system-site-packages` 只读复用 `${EXISTING_PYTHON_ENV}` 的 NumPy、Pillow、Matplotlib 等依赖；没有修改已有环境。该环境足以复现 smoke test，**并非完整 LCVN 推理环境**。具体版本见 `outputs/first_round/software_versions.json`。

## 文件入口

- `vendor/track1/`：官方工具，commit `a52e43fd68edcd413436c2466a3177046002964b`。
- `vendor/LCVN/`：官方模型代码，commit `e6a52e65901a10e4581a0431944aad6e56355ef7`；未修改。
- `data/lcvn/val_seen/`：只提取 9 个真实 episode，包含 `0.jpg`、其余帧、`traj_data.pkl`。
- `outputs/first_round/status.json`：真实推理数、baseline 指标空值、耗时与阻塞。
- `outputs/first_round/samples.json`：每条样例的图像路径、指令、字段及参考动作示例；预测为 null。
- `outputs/first_round/coordinate_controls.png`：参考轨迹与坐标错误对照，**不是预测轨迹**。
- `outputs/first_round/controls/`：参考动作回环和零动作格式样例，**均非 baseline 输出**。
- `outputs/first_round/LOCAL_FORMAT_ONLY_NOT_SUBMISSION.zip`：仅本地格式用，缺少完整 episode 与 `val_unseen.json`，正式检查会拒绝。

## 本地格式校验

```sh
.venv/bin/python scripts/validate_predictions.py \
  outputs/first_round/controls/format_only_val_seen.json --split val_seen
```

以上只检查结构和公开动作限制；没有 manifest 时不验证官方 ID 覆盖率。
以后取得官方 example ZIP/manifest 后，可传 `--manifest <official_val_seen.json> --full` 检查 ID 完整性。9 条局部文件不能通过完整 Phase 1 提交检查。

参考： [Track 1 工具仓库](https://github.com/roboworld2026/track1)、[LCVN](https://github.com/UWMILab/LCVN)、[CodaBench](https://www.codabench.org/competitions/18185/)。
