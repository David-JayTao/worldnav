# WorldNav 第一轮实验报告

记录日期：2026-10-29（Asia/Tokyo）。用途：周五组会的第一轮可复现验证。

## 1. 最终状态与结论

**仅完成真实数据、公开评测函数及提交格式的 smoke test；官方 baseline 因权重和依赖问题受阻。**

- 真实输入：9 个 `val_seen` episode，来自 3 段轨迹，每段 3 种指令。同一归档开头的同域场景，不是随机代表性抽样。
- 成功模型前向推理：**0**。baseline 真实评估数：**0**。
- baseline SR、ATE、RPE、Full-route fidelity、Heading and turn fidelity、Score：**全部未测**。
- 已执行 Uni 推理入口和 AC 入口依赖探测，两者在模型加载前退出。没有训练、没有随机初始化模型推理、没有比赛上传。
- 下文参考轨迹回环实验只验证工程链路，不能当作模型分数，也不能与完整验证集或榜单比较。

## 2. 官方来源和版本

| 来源 | 固定版本 / 本地证据 |
|---|---|
| [官方赛道说明](https://roboworld2026.github.io/track1) | 已在线阅读；实际规则优先核对代码与 CodaBench |
| [Track 1 工具](https://github.com/roboworld2026/track1) | `a52e43fd68edcd413436c2466a3177046002964b`；`vendor/track1` |
| [LCVN 官方实现](https://github.com/UWMILab/LCVN) | `e6a52e65901a10e4581a0431944aad6e56355ef7`；`vendor/LCVN` |
| [官方数据](https://huggingface.co/datasets/fly1113/LCVN) | 文件清单 `outputs/first_round/hf_dataset.json`；下载范围和 SHA256 见 `data_provenance.json` |
| [CodaBench](https://www.codabench.org/competitions/18185/) | 公共 `/api/competitions/18185/` 可读取，快照 `codabench_api.json` |

两个 vendor 仓库均未修改。README 有部分旧仓库名和重定向链接，实际 clone 使用用户指定的新地址。

## 3. 硬件、环境与资源决策

初始只读检查：当前目录 `${HOME}`，不是 Git 仓库；未覆盖现有项目，创建独立 `worldnav-baseline/`。

| 项目 | 实测 |
|---|---|
| GPU | 4 × NVIDIA GeForce RTX 3090，24,576 MiB/张 |
| 已有占用 | 各 17,481–17,583 MiB；约 50%–71% 利用率，运行他人的任务 |
| 可用显存 | NVML 后续快照各 6,568–6,670 MiB，约 6.4–6.5 GiB；会动态变化 |
| NVIDIA Driver | 565.77；nvidia-smi 显示最高 CUDA 12.7 |
| CUDA toolkit | nvcc 12.4.131 |
| 内存 | 总 251 GiB，可用约 234 GiB |
| 磁盘 | `/` 约 3.9–4.0 GB；`/data` 78 GB；`/data1` 2.2 TB 可用 |
| 系统 Python | 3.10.12 |
| 已有用户环境 | Conda base 与 `${EXISTING_PYTHON_ENV}` |
| 复用环境 | Python 3.10.20、PyTorch 2.5.1 / CUDA 12.4、torchvision 0.20.1 |
| 其他 | Transformers 4.35.2、NumPy 1.24.4、SciPy 1.15.3、Pillow 11.0.0、Matplotlib 3.7.5 |

资源快照和原始命令见 `environment.log`。当前 GPU 上进程均未终止或调整。

使用项目级 `.venv`，以 `--system-site-packages` 只读继承已有环境；没有修改系统或已有 Conda 环境，也没有用 sudo。仅满足 CPU smoke test；不是完整模型环境。

未找到本地 LCVN/Anole 权重和 `traj_data.pkl`：检查范围为当前用户项目、`${USER_DATA_ROOT}`、用户缓存与公开共享模型目录；不声称扫描了所有用户的私有目录。共享目录中其他模型不能替代官方 LCVN checkpoint。

## 4. baseline 对比与选择

| 项目 | LCVN-Uni | LCVN-WM + LCVN-AC |
|---|---|---|
| 架构 | Anole-7B + 导航动作扩展词表 + LoRA | 定制 VAE + 扩散 WM + actor-critic |
| 官方依赖 | Torch 2.4.0；指定 Git commit 的 Transformers fork；FlashAttention 2.5.9.post1；PEFT 等 | Torch 2.4.1+cu118、FlashAttention 2.6.3、diffusers、Hydra、Lightning、句向量等 |
| 权重 | Anole 基座 + 训练后 adapter + tokenizer/processor | `social_dit_xl.ckpt`、`vae.ckpt`、AC `last.ckpt` 及相应配置/编码资源 |
| 推理入口 | `lcvn-uni/eval.sh` → `train.py --do_task_level_eval` | `python -m lcvn_ac.scripts.test_single_trajectory_real_dfot` |
| 数据准备 | 原始 jpg/pkl；官方 loader 还有内部重新切分问题 | 元数据、潜变量编码、cache；官方全流水线还包含 VAE 训练 |
| 当前实际阻塞 | 缺专用 checkpoint；Transformers 版本不匹配；缺 FlashAttention、PEFT | 缺 3 类专用权重及编码缓存；入口首先缺 FlashAttention |

**选定 Uni 作为后续优先 baseline**：相对而言可以绕开 WM 的定制 VAE 训练和潜变量 cache 流程。但当前不具备复现条件，不能声称已运行成功。

权重核查：

- 当前 README 只有训练/评测和占位 checkpoint 路径，没有训练后权重下载链接。
- GitHub Releases 页面显示没有 release；REST API 遇到 403 限流，已改读公开网页。
- Hugging Face `author=fly1113` 和 `search=LCVN` 的模型搜索均返回空数组，已保存响应。此结论仅限检索范围，不等同于证明所有渠道都不存在权重。
- [issue #7](https://github.com/UWMILab/LCVN/issues/7)、[#6](https://github.com/UWMILab/LCVN/issues/6)、[#1](https://github.com/UWMILab/LCVN/issues/1) 也在请求发布 checkpoint；读取到的页面没有提供下载链接。
- 官方 loader 指向 `leloy/Anole-7b-v0.1-hf`，公开文件元数据的 3 个 safetensors 合计 **14,302,290,188 字节**。这只是基座，不是 LCVN。基座本身就超过系统盘余量，官方 `device_map="cuda"` / BF16 路径也超过当前单卡可用显存。因此没有下载这些权重或安装完整依赖。
- 没有擅自训练，也没有用其他共享模型或随机权重替代 baseline。

## 5. 数据输入与真实样例

`download_data.sh` 默认遍历 `train val_seen val_unseen`，逐个 `wget -c` → `tar -xf` → 删除归档；Track 工具支持 `SPLITS` 选择。直接执行默认脚本会下载全部数据，因此本轮没有执行它。

HF 实际字节大小：train 57,581,035,520；val_seen 7,409,704,960；val_unseen 20,311,838,720。

已实测服务器支持 HTTP Range，返回 `206` 和 `Content-Range: bytes 0-16777215/7409704960`。仅下载前 **16,777,216 字节**，约 6.03 秒，提取前 3 组轨迹及其全部 3 种指令；没有下载完整归档。缓存保留以便离线复现。

```text
data/lcvn/val_seen/{episode_directory}/
  0.jpg, 1.jpg, ..., n.jpg
  traj_data.pkl
```

每个目录对应一条指令；末尾 `_0/_1/_2` 三个目录具有相同图像/轨迹、不同文字。本轮有 9 个 episode，但只有 3 段不同的参考轨迹。完整官方 ID 仍需下载 CodaBench manifest，不能把本地目录名覆盖率当作官方 manifest 验证。

| 轨迹目录前缀（各含末尾 `_0/_1/_2`） | 图像数 | 参考动作数 | 成功预测动作数 |
|---|---:|---:|---|
| `Dec-06-2022-bww8_00000000_0_16_0` | 10 | 9 | 未生成 |
| `Dec-06-2022-bww8_00000000_0_8_0` | 30 | 29 | 未生成 |
| `Dec-06-2022-bww8_00000001_0_8_0` | 20 | 19 | 未生成 |

实测 pkl 字段：`position: float64[T,2]`、`yaw: float64[T]`、`delta: float64[T-1,3]`、`instruction: str`。所有数值有限，图片均可解码，初始 RGB 图像是 160×120。

一条真实输入：

- episode：`Dec-06-2022-bww8_00000000_0_16_0_0`。
- 图像：[0.jpg](../data/lcvn/val_seen/Dec-06-2022-bww8_00000000_0_16_0_0/0.jpg)。
- 指令：`Walk straight down the hallway and stop near the end.`
- 真实模型输出：**无，前向未执行成功；samples.json 的 prediction 与 predicted_action_count 为 null**。
- 仅作标签格式说明：首个参考全局 delta 为 `[0.1949844360, -0.0389537811, 0.2440375239]`；转换后的局部动作是 `[0.1972669487, 0.0249414974, 0.2440375239]`。这不是模型预测。

## 6. 代码中的实际流程及与比赛的差异

目标流程：初始 RGB + 指令 → 图像/文本处理 → Uni 自回归动作和未来图像生成 → 局部动作 JSON → 轨迹重建 → 官方公开指标。

实际已运行部分：真实 jpg/pkl → PIL 解码/256×256 resize → 参考动作局部化 → JSON 写入/读取 → 坐标重建 → `demonstration.py` 五个函数 → 格式检查。模型生成与正式 manifest 校验尚未完成。

Uni 代码确认：

1. `scripts/navigation.py` 读取 pkl、jpg，先转 RGB 并 resize 为 256×256；`scripts/load_model.py` 将 Anole processor 短边/crop 设置为 448×448，使用 784 图像 token，BF16/FlashAttention。后一个 processor 阶段未实际执行。
2. 图像和 prompt 进入 `model.generate`，每步生成动作文本与未来图像，解析 0.01 步长的正负 bin token。生成图像被解码后用作下一步观测，不读取真实中间帧纠偏。
3. `scripts/action_utils.py:calculate_action_delta` 直接做世界坐标位置差；`navigation.py` 优先读取已存在的 `delta`，没有局部坐标变换。实测全部 9 条样例 `delta[:,:2] == diff(position)`，最大差为 0。
4. `customize_trainer.py:_process_single_trajectory` 也是直接 `x += dx, y += dy, yaw += dyaw`，而 prompt 却用前向/侧向描述；训练标签、累积代码与比赛坐标语义需要明确衔接。
5. 原 rollout prompt 依赖 `raw_item['coords'][0]` 的**数值初始位姿**，比赛测试只给 RGB 和指令、不提供此位姿。这是额外的协议差异；不能悄悄把验证标签作为模型输入再声称符合比赛。设为 `[0,0,0]` 只能作为明确声明的后续适配假设，未验证等价性。
6. loader 对传入目录内部按 80/10/10 重新切分，而不是直接保留官方验证集；还限制非训练 split 最多 800 条。因此不能把 README 默认运行当作完整比赛验证。
7. `_prepare_task_level_sample` 会加载末帧用于数据/评估；实际 rollout prompt 只用初始图、当前生成图与指令，没有把该末帧传入模型。真实中间帧同样不能进入模型。
8. 预测 `Stop`、全零动作、图像解码失败或达到 **26 步**都会结束。该上限低于本轮一条参考轨迹的 29 步，需要留意长度截断。比赛 JSON 通过列表结束轨迹，不额外写字符串 Stop。
9. Uni 输出 `eval_result.json` 中的 `trajectory_actions` 是字符串，**不是**官方 `split/episodes/episode_id/actions` 结构；要单独导出，不能直接提交。Uni 的 evo 指标也不等同于本次赛事全套评测。
10. AC 的测试脚本在 checkpoint 不存在或加载失败时会实例化新模型；该路径不能视为训练后 baseline 推理。

局部动作重建（本轮 wrapper 实现，官方 demo 没有提供 JSON 读取器/重建函数）：

```text
X' = X + cos(yaw) * dx - sin(yaw) * dy
Y' = Y + sin(yaw) * dx + cos(yaw) * dy
yaw' = yaw + atan2(sin(dyaw), cos(dyaw))
```

先按当前朝向平移，再加角度；角度是弧度。累计 yaw 保持连续，避免人为制造 2π 跳变。若将 Uni 全局预测适配为局部动作，必须使用预测累积的朝向和明确的初始坐标约定，不能在 rollout 中借用真实未来 yaw。

## 7. 官方指标实现核对

调用 `vendor/track1/demonstration.py`，未重写五个指标。它是函数演示，不读取预测 JSON，也不是 CodaBench 私有 scorer；本轮 wrapper 完成 JSON 读取、坐标积分与公式组合。

- **SR**：demo 使用末点到目标距离 `< max(average_step_length, 1.5)`。官方网页仅写平均步长，实际代码有 **1.5 的下限**。本轮回环控制的 average_step_length 使用参考轨迹平均步长；私有 scorer 的该参数来源尚未验证。
- **ATE**：以参考的 T−1 个运动边界计算 XY RMSE，不做刚体对齐；预测太短时重复最后位置，超出参考窗口的部分不进入该项。
- **RPE**：同一参考窗口内，相邻 XY 位移差的 RMSE；本 demo 只计算平移项，不是完整 SE(3) 或旋转 RPE。
- **Full-route fidelity F**：整条有序折线的连续 Fréchet 距离 d，按参考相对起点的最大跨度 s 归一化，主体为 `max(0,1−d/s)`；再乘 `min(1,L_ref/L_pred)` 惩罚超额长度。退化路径有专门分支，实际仍调用官方实现。
- **Heading and turn fidelity H**：沿移动路程累计 `(1−cos(yaw差))/2` 的误差；再对转向方向、位置、角度差做积分，组合为 `max(0,1−movement_error)/(1+turn_cost)`。纯旋转/零长度有专门处理。
- **Score**：对每个 episode 算 `100*F*(1+H)/2*(0.70+0.10*SR+0.10/(1+ATE)+0.10/(1+RPE))`，最后平均；不能把整体均值塞回非线性公式代替逐条平均。

训练与验证标签公开；最终测试只开放初始图像和指令，参考动作/轨迹/初始数值位姿不公开。当前 CodaBench API 只显示 Phase 1 配置；没有假装取得未来 Phase 2 测试数据。

## 8. 实际运行与结果

从项目目录执行：

```sh
${EXISTING_PYTHON_ENV}/bin/python -m venv --system-site-packages .venv
sh scripts/run_smoke_test.sh
```

脚本保存两个入口命令和 stderr 到 `uni_entry_attempt.log`、`ac_entry_attempt.log`。入口命令分别为：

```sh
# cwd: vendor/LCVN/lcvn-uni；环境：CUDA_VISIBLE_DEVICES=""、HF_HUB_OFFLINE=1
${PROJECT_ROOT}/.venv/bin/python train.py \
  --model anole --data val_seen --data_dir ${PROJECT_ROOT}/data/lcvn \
  --decoder_type anole --image_seq_length 784 --input_format anole \
  --output ${PROJECT_ROOT}/outputs/first_round/baseline_attempt \
  --note first_round --report_to none --do_task_level_eval

# cwd: vendor/LCVN/lcvn-ac；仅探测官方入口是否可导入
${PROJECT_ROOT}/.venv/bin/python \
  -m lcvn_ac.scripts.test_single_trajectory_real_dfot --help
```

两者 exit code 均为 1。Uni 首错是 `ImportError: cannot import name 'StopStringCriteria' from 'transformers'`；AC 首错是 `ModuleNotFoundError: No module named 'flash_attn'`。已定位官方依赖要求；由于专用权重仍不可用，继续安装大体积依赖也无法获得真实推理结果，因此没有盲目升级已有环境或编译 GPU 依赖。

| 测试 | 数量 | 结果 |
|---|---:|---|
| 真实输入读取与有限数值检查 | 9 episode / 3 轨迹 | 通过 |
| 参考标签 → 局部动作 → 世界轨迹回环 | 9 | 最大 XY 坐标差 `8.88e-16` |
| 公开五指标函数与综合公式 | 9 个参考回环控制 | 通过，不是模型评测 |
| JSON 读写、动作形状与公开边界 | 9 条零动作格式样例；参考回环 JSON 也检查 | 通过 |
| 非法/不完整用例拒绝 | 13 类 | 通过 |
| 模型真实推理 / baseline 评测 | 0 / 0 | 未完成 |
| 官方完整 manifest 核对 | 0 | 下载入口 404 / API 403，未完成 |

诊断对照（全部使用参考标签，因此**绝不是 baseline 分数**）：

| 控制条件，9 episode | SR | ATE | RPE | F | H | Score |
|---|---:|---:|---:|---:|---:|---:|
| 参考标签经正确坐标回环 | 1 | 约 2.30e-16 | 约 9.50e-17 | 约 1 | 1 | 约 100 |
| 故意把全局 delta 当局部动作 | 0.3333 | 2.5021 | 0.2308 | 0.3175 | 0.8889 | 31.4482 |

第二个控制中，轨迹 2 和 3 的 F 为 0，提供了具体的坐标错误证据。[对照图](../outputs/first_round/coordinate_controls.png) 的黑线是标签、绿线是标签回环、红线是故意错误的坐标解释；没有模型预测曲线。

首次完整可复现 smoke 脚本约 **4.73 秒**（缓存已存在，含两个失败入口探测；后续复跑可能变化，详见 `status.json`）；原始 16 MiB 获取约 6.03 秒，环境建立和调查时间不包含在这两个耗时内。模型推理耗时、峰值模型显存均**未测**；本轮禁用 GPU，没有 OOM，不能据此推断模型显存需求。

## 9. 提交格式核查与边界

公共 CodaBench API 已确认：

- `actions` 最多 64 条；每项 3 个有限数值，平移 **hypot(dx,dy) ≤ 2.46**，不是逐分量各 ≤ 2.46；`abs(dyaw) ≤ 6.29` rad，评测按 2π 取模。
- Phase 1 ZIP 根目录仅 `val_seen.json`、`val_unseen.json`，分别完整 10,806 / 4,500 episode。Phase 2 根目录仅 `test.json`。
- split 要与文件名一致；ID 必须与官方 manifest 对应且各出现一次；列表结束轨迹。

本地 validator 检查 split、有限数字、拒绝 bool/string、三元动作、64 步限制、向量范数、角度限制、重复 ID；提供 manifest 时检查未知/缺失 ID。完整 ZIP 模式同时检查根路径与文件集合，缺 manifest 不允许声称完整验证通过。

13 个拒绝用例：NaN、Inf、bool、string、错误维度、平移范数超限、角度超限、重复 ID、局部样例缺失 ID、65 动作、错误 split、不完整 Phase 1 ZIP、无 manifest 却要求完整验证。

CodaBench UI 声明的 example 文件是 `worldnav_phase1_example_submission.zip`（50,356 字节）。实际读取其公开 UI 生成的 key 和 ID 下载路由均返回 404，dataset API 与 get_files API 返回 403。**仅读取元数据和规则成功，示例 ZIP 与官方完整 manifest 并未获取或打开。** 不把此错误直接归因为用户没有账号或资源已经删除，原因尚不确定；没有访问 private scorer 或参考私有附件。

`LOCAL_FORMAT_ONLY_NOT_SUBMISSION.zip` 只有 9 条、只有 val_seen，一定缺少正式要求的内容。脚本明确断言它被正式 ZIP 检查拒绝。预测字段为零的文件仅用于格式测试；参考回环文件使用公开验证标签，均不能提交或当作模型成绩。没有生成/上传正式提交文件。

## 10. 完成项与后续实验

- [x] 阅读官方任务说明、下载逻辑、baseline 和评测实际代码。
- [x] 检查工作区、服务器、已有环境与任务占用，保存日志。
- [x] 比较两条路径，选定 Uni 为后续优先；没有把可行性描述为已跑通。
- [x] 建立最小 CPU smoke 环境；记录完整 baseline 环境无法完成的原因。
- [x] 尝试官方入口，并保存真实错误。
- [x] 读取 9 个真实输入；执行标签坐标回环和公开评测函数。
- [x] 完成本地格式/负例检查、日志与报告。
- [ ] 成功完成 3–10 条训练后官方模型的真实推理。
- [ ] 检查真实模型输出的 NaN/Inf、终止与长度；当前没有真实输出。
- [ ] 获得 baseline 的真实 SR/ATE/RPE/F/H/Score。
- [ ] 获取官方 example ZIP 与完整 manifest，验证正式提交覆盖率。

下一步优先三个低成本实验：

1. **先验证 checkpoint 可用性**：由有权限的队员向官方索取 Uni adapter、匹配 tokenizer/processor、基座版本与已验证单卡推理命令；提供 SHA256 后先严格加载一条，再扩大到本轮 9 条。验收标准是所有导航参数成功加载、无随机回退、有真实动作输出。不要先投入训练。
2. **验证比赛协议适配**：取得权重后，在同 3 条轨迹上对照原全局输出与明确局部化导出；只用预测累积朝向，单独验证初始数值位姿设为规范原点的影响，并检查 26 步截断。不能给比赛推理喂入标签位姿；若原模型必须依赖它，应向官方确认适配方式。
3. **固定轨迹比较三种指令**：用已缓存的 3×3 episode，固定采样设置，记录停止步数、格式有效率与六项官方指标，验证详细指令是否改善长轨迹/转向；预约空闲 GPU 后再运行，不占当前共享任务。9 条仅为 sanity check，再决定是否扩到 30 条。

周五可展示的是：真实输入及三种指令、任务/坐标定义、官方代码行为、坐标错误对照图、13 类格式检查和具体阻塞证据；不能展示为已复现的 baseline 分数。
