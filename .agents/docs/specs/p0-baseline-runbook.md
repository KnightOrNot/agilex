# P0 基线冻结与测量：实验机 Codex 执行手册

编写日期：2026-11-12。状态：**待执行手册，不是测试通过报告**。

目标：在实验机器上为重构前的 CLI 与浏览器路径建立可复核、可重复的行为和性能基线，完成架构 P0。执行后交付中文报告、统计结果、测量/回放工具和黄金数据索引。不得以代码阅读、仿真或历史测试结果替代本次真机结果。

本手册可单独复制。放在实验机仓库任意位置后，将下面这段任务说明交给当地 Codex；正文中的源码路径均相对于仓库根目录。

> 请执行本手册的 P0 工作。先阅读本机项目规范并核对基线，完成软件检查和测量准备，再按已有授权与现场确认执行硬件阶段。允许编写必要的测量脚本、只观测的临时插桩和特征化测试；不实施 P2～P7，不修改标定、运动算法、容差或旧数据。硬件阶段由现场操作员确认并在场。缺证据就写未完成，不能替操作员确认。最终按第 11 节交付报告与证据包，不自动 commit、push、合并、上传数据或变更项目阶段。

## 1. 验收范围与执行顺序

架构依据是 [v3.3 架构基线](architecture-v3.3.md) §13/P0、§14，以及 `.agents/docs/stages/testing.md` 的第 5/6 项。先读 `HABITS.md`、`AGENTS.md`、`.ai-stage`、`.agents/constraints.md`、`.agents/workflows.md`、`.agents/git.md`，按本机 `SKILLS.md` 加载实际存在的工具。不要照搬编写机器的用户名、绝对路径、设备序列号或技能安装位置。

| 编号 | 工作 | 必须留下的证据 |
| --- | --- | --- |
| B0 | 固定代码、配置与环境 | 主仓/子仓 SHA、dirty 状态、锁文件哈希、硬件/固件与有效配置 |
| B1 | 当前版本的软件回归与测量工具自检 | 每条命令、退出码、passed/failed/skipped、日志；插桩的离线验证 |
| B2 | 设备身份、反馈与现场条件核对 | 实际设备、CAN/USB/串口状态；授权范围与操作员确认 |
| B3 | CLI 与 Web 无相机最小运动 | 回零、对齐、小范围跟随、方向/夹爪、退出和清理结果 |
| B4 | CLI 与 Web 各自短时 RGB-D 采集 | 保存/丢弃结果；各一份完整黄金 raw 与 LeRobot v3 数据集；逐帧回读报告 |
| B5 | 控制时序与数据路径测量 | 原始逐周期数据、分位数、超期/队列/丢帧统计；序列化、复制、写盘与提交耗时 |
| B6 | GELLO 黄金序列及特征化测试 | 初始化条件、驱动输入/调用顺序/输出；无硬件确定性回放与异常路径测试 |
| B7 | 汇总、归档与用户验收 | P0 报告、证据索引/哈希、阶段记录追加片段、用户实测结论 |

顺序：B0 → B1 → B2 → B3 → B4 → B5 → B7；B6 的观测准备在 B1 完成，数据随 B3～B5 获取，回放在设备退出后进行。B4 的黄金采集先用未插桩路径；B5 的详细观测使用单独标记的测量运行。

P0 记录**现有行为**。不要求旧代码已经满足新架构的 raw v3、`full`/`sampled`、新租约或权限状态机，也不把旧行为的缺陷升级为未来必须保留的规范。

## 2. 固定基线并建立证据目录（B0）

### 2.1 本手册核对过的版本

建议使用已推送的 `dev` 快照 **`640aad8ea896b37257c5c7fe8de46220f61cac84`**，主包版本 `0.2.2`。它包含 P1 仿真，但旧 CLI/Web 真机路径尚未切换；本次测这些旧路径。不要在测试中途跟进移动的 `dev`。

| 子模块路径 | 固定提交 |
| --- | --- |
| `third-party/agilex-adapters` | `93492d35bdc1b6dc6b27d35f07694f1b49b2a1cb` |
| `third-party/agilex-contract` | `3bc6bcf3a108a2477338bb46fabe6ab8536aa817` |
| `third-party/agilex-gello-software` | `dd44a6f1d28d994b5185b0efd63faec102fdecde` |
| `third-party/agilex-sdk-python` | `24cac28cdd296607f93defd89158aed70d91e11c` |
| `third-party/camera-realsense-d455f` | `ba47e2669e1ea5b4ecf2a14f168b1d91d7a5123f` |
| `third-party/lerobot-converter` | `976b9385ee388802b542c70b058f93d0fb92d657` |

先执行只读核对：

```bash
pwd
git status --short --branch
git rev-parse HEAD
git submodule status
git submodule foreach 'git status --short'
```

工作副本已有修改时保留，优先建立独立实验副本。不要 reset、覆盖文件或升级子模块。在**尚不存在**的目标目录新建副本的命令如下；已满足基线就跳过：

```bash
git clone --branch dev git@github.com:KnightOrNot/agilex.git agilex-p0
cd agilex-p0
git switch -c dev-p0-baseline 640aad8ea896b37257c5c7fe8de46220f61cac84
git submodule sync --recursive
git submodule update --init
```

`update` 不加 `--recursive`，避免下载 GELLO 的可选 MuJoCo 资产；不使用 `--remote`。若选择其他版本，先列出相对上述快照的控制、采集、依赖与子模块差异，由用户确认新的基线，禁止静默替换。

### 2.2 证据布局

下面变量在每个执行终端设置一次；换终端时从已记录的路径恢复同一个 `P0_RUN`，不要意外创建第二套证据：

```bash
P0_REPO=$(git rev-parse --show-toplevel)
P0_RUN_ID="p0-$(date -u +%Y%m%dT%H%M%SZ)"
P0_RUN="$P0_REPO/data/p0/$P0_RUN_ID"
export P0_REPO P0_RUN_ID P0_RUN
mkdir -p "$P0_RUN"/{environment,configs,logs,metrics,gello,tools,patches,reports,checksums}
```

`data/` 已被 Git 忽略。仅创建实际使用的子目录；本次所有路径写入报告。实际 golden raw/dataset 保留在原应用产生的位置，通过 `artifacts.json` 索引关联，禁止修改原始数据来修正验收。

```text
data/p0/<run-id>/
  environment/  代码、机器、依赖、设备清单
  configs/      原配置副本、各测试配置、有效配置
  logs/         命令输出、浏览器/worker 日志、操作员事件
  metrics/      cycles.csv、stages.csv、summary.json、各入口质量报告
  gello/        初始状态、按调用顺序的输入/输出、回放结果
  tools/        实际执行的测量/统计/回读脚本、特征化测试和使用命令
  patches/      每个有插桩仓库的独立补丁与基线 SHA
  reports/      P0_REPORT.md、TESTING_APPEND.md、artifacts.json
  checksums/    回传包及每个黄金数据目录的文件级 SHA256 清单
```

### 2.3 环境快照

记录以下内容，不输出整个环境变量表、认证文件或 SSH 配置：

- UTC 与本地时区、主机别名、OS/内核、CPU/内存、供电/性能模式、磁盘型号/文件系统/挂载点/可用空间、USB 拓扑。基线和复测要能识别机器或存储发生变化。
- 主仓及六个子模块 SHA、分支、修改状态；若有允许的观测补丁，另存补丁，不把它描述为干净原版。
- `uv --version`、各环境 Python/NumPy/pyzmq/SDK/RealSense/LeRobot/编解码器版本、各 `uv.lock` 与配置文件 SHA256。根、SDK、GELLO、camera、converter、adapters 均有独立环境；contract 是根使用的纯库，也应记录版本。
- 实物型号/标识、PiPER-X 固件/控制模式/SDK 版本、主手电机 ID/波特率/标定、相机固件、USB 速率。历史记录只能作定位提示，必须现场复核。
- 本次运行的命令、覆盖参数、有效配置，以及 CLI 和 Web 各自实际 camera profile、深度单位与标定。

主机只读检查可用 `uname -a`、`lscpu`、`free -h`、`lsblk`、`df -h`、`lsusb -t`、`id -nG`。没有对应工具就记录缺项，不为生成报告擅自升级系统。设备打开及 CAN 配置仍按第 4 节授权。

## 3. 安装、软件回归与观测准备（B1）

### 3.1 环境就绪

先读本版本 `docs/zh/installation.md`。根 `make sync` 只准备根环境，不能替代真机、converter 和 Web 环境。已有环境先运行只检查入口；缺依赖时按固定锁补齐：

```bash
./scripts/setup.sh --check-only
```

需要安装时，已具备系统依赖可运行 `./scripts/setup.sh --skip-system --skip-submodules`，然后运行 `uv run --frozen agilex-data-collection setup`。系统包、用户组、udev、CAN 或网络配置变更依现场授权执行。不得手改 lock、混合 NumPy 环境或升级子模块来绕过安装错误。

确认以下帮助命令成功（不打开硬件）：

```bash
uv run --frozen agilex-controller --help
uv run --frozen agilex-controller record --help
uv run --frozen agilex-controller convert --help
uv run --frozen agilex-data-collection serve --help
```

### 3.2 无硬件检查

硬件会话停止时运行，避免软件测试的 CPU/磁盘负载影响实测。为每条命令分别保存日志和退出码；使用管道时启用 `pipefail`，不要把 `tee` 成功当作测试成功。

```bash
set -o pipefail
make verify 2>&1 | tee "$P0_RUN/logs/root-verify.log"
P0_VERIFY_STATUS=${PIPESTATUS[0]}
printf '%s\n' "$P0_VERIFY_STATUS" > "$P0_RUN/logs/root-verify.exitcode"
```

按各子项目 README 补齐检查。以下命令在对应子项目目录内执行，日志保存到绝对的 `$P0_RUN/logs`：

| 工作目录 | 检查命令 |
| --- | --- |
| `third-party/agilex-sdk-python` | `uv run --frozen pytest`；`uv run --frozen ruff check .`；`uv run --frozen pyright` |
| `third-party/camera-realsense-d455f` | `uv run --frozen python -m unittest discover -s tests -v`；`uv run --frozen pyright` |
| `third-party/agilex-gello-software` | `uv run --frozen pytest -q`；`uv run --frozen ruff check src/agilex_gello_software/cli.py src/agilex_gello_software/paths.py tests experiments` |
| `third-party/lerobot-converter` | `uv run --frozen --extra dataset pytest -q`；按该仓现有 Ruff 范围检查 |
| `third-party/agilex-adapters` | `uv run --frozen --extra app pytest -q`；按该仓现有 Ruff 范围检查 |
| `third-party/agilex-contract` | `uv run --frozen pytest -q`；`uv run --frozen ruff check .` |

根的三项 converter 集成回读在完整环境中应实际执行；如果仍因缺环境跳过，补装后重跑，不能用历史的 170 项通过数填本次报告。记录所有 skip 的原因与其影响。可选硬件依赖测试若被明确设计为 skip，单列说明，不伪造全覆盖；必需软件检查失败时先调查，不进入运动验收。

### 3.3 准备配置副本

从实验机已核对的硬件配置复制出以下文件，保留原标定和安全参数，仅改变测试用途需要的开关、输出路径或明确选择的 profile：

- `configs/cli-no-camera.toml`：`[camera].enabled=false`、`preview=false`。
- `configs/web-no-camera.toml`：`[collection].camera_enabled=false`。
- `configs/cli-rgbd.toml`：启用 RGB-D；SSH 无桌面时关闭本地 Tk 预览；输出放本轮独立根。
- `configs/web-rgbd.toml`：启用 RGB-D，保留实际要测的 `camera_mode`；`[collection].data_root` 指向本轮独立派生目录。

当前路径约定：`[paths]` 的相对路径按仓库根解析；Web 的 raw **固定写在 `data/raw/app/<session_id>`**，不受 `[paths].raw_data_root` 控制，必须从状态中记录实际路径。若 `[collection].hardware_config` 非空，还要复制并记录它指向的硬件配置，不能只保存顶层 TOML。

默认控制频率 50 Hz、数据集 30 FPS；CLI `move_js` 默认 1.0°，Web 为 `[collection].position_tolerance_deg=1.1`。P0 不统一容差，不改为架构目标的 1.0°。相机 CLI 默认配置为 640×480@30；Web `auto` 可能选择 640×360@90，必须记录最终 profile，不能假定两个入口相同。

### 3.4 当前可直接测到什么

| 来源 | 已有数据与限制 |
| --- | --- |
| CLI `episodes/episode_*.jsonl` | `control_period_ns`、命令/观测/墙钟时间、sequence、action 与反馈；仅录制期间保存，不含所有空闲跟随周期 |
| CLI 相机 `frames.jsonl` | 原帧元数据与 PNG 路径；以实际字段确定设备/主机时间及 frame number 的含义 |
| Web `take_*/samples.jsonl` | `robot.command_started_ns/command_finished_ns`、主手动作时间、观测时间和相机元数据；只有数据集采样时刻，**不是完整控制周期序列** |
| Web worker 日志 | `[position_result]` 有目标、容差与残差；是否使能/静止仍需结合反馈和现场观察 |
| writer 的已有计数 | CLI 相机 `_written/_write_seconds` 仅为累计值，不是逐帧延迟分位数；队列水位未完整持久化 |

浏览器完整控制周期、各阶段延迟、队列峰值、GELLO 原始输入仍需第 8/9 节的观测工具。**这些工具不是当前仓库已提供的命令**：实验机 Codex 须按下述接口先实现和自检，并随报告交回。不要写出一个不存在的测量命令后直接声称通过。

## 4. 现场授权与停止条件（B2）

这份手册授权准备测试资料，不代替本次实物状态的确认。先核对当前对话已有授权；缺失时集中确认下列范围，已明确授权的不重复询问：

1. 打开 GELLO、PiPER-X 反馈、相机；必要的 CAN 接口准备；GELLO 初始化会关闭扭矩、相机采集会开流。
2. 无相机最小运动：启动回零、对齐、操作员控制的小范围跟随、夹爪检查、退出回零。
3. 短时 RGB-D 采集及第 8 节约定时长/重复次数的测量；退出仍会尝试回零。

由操作员确认底座固定、工作空间清空、急停可用、主手安装/标定对应、当前姿态允许回零与对齐，并指定本次可运动范围。把确认时间和覆盖的运行编号写入事件记录。**不在手册中预设一组对所有安装都安全的运动目标。**

保留 CLI 目标显示及人工 `yes`、Web 运动勾选与后端 guard。不要用 `--yes`、自动输入、直接调用运动 API 绕过确认；不要把独立 `movejs` 当成只读检查。两入口与其他控制程序不能同时占有设备，不删锁，不结束身份不明的进程。

只读/准备核对在对应授权后执行：

```bash
uv run --frozen agilex-controller status --config "$P0_RUN/configs/cli-no-camera.toml"
uv run --project third-party/camera-realsense-d455f --frozen camera-realsense info --profiles
```

`agilex-controller read` 实际会在初始化时关闭 GELLO 扭矩；严格只读审计只发送 Dynamixel PING/READ。普通 `read` 或 `GelloLeader` 初始化需归入已授权的设备准备，不能标成无副作用。Web 真机 `serve` 会在会话启动前配置 CAN，也需要对应授权。

发现反馈缺失/异常/陈旧、CAN 错误、跳变、方向不符、设备身份或标定不符时停止该阶段，保留错误与数据，先由操作员处置。普通退出会尝试回零；若运动本身不安全，由现场人员按实物急停流程处理，不能承诺 Ctrl+C、停发命令或进程退出等于硬件立即静止。不自动 reset、失能、标定、修改 offset、控制模式或容差。

P0 **不做**运动中拔 CAN、拔串口、杀 SDK/HAL、暂停命令或 runtime 崩溃等故障注入；PiPER-X 断令行为继续记为 `unverified`。该项需另外的受控方案与授权，不是本轮 P0 通过的必要条件，也不会因 P0 通过而自动变成 verified。

## 5. 无相机最小运动（B3，对应阶段记录第 5 项）

### 5.1 CLI

在保留交互终端的情况下启动，操作员核对显示的目标后自行输入 `yes`：

```bash
uv run --frozen agilex-controller follow \
  --config "$P0_RUN/configs/cli-no-camera.toml" \
  --no-camera --no-camera-preview
```

记录启动回零、主手对齐、跟随和退出四个阶段的起止时间、六轴目标/反馈/残差与夹爪值。现有输出不够时用第 8 节的只观测探针记录已发生的反馈读取，不额外插入高频 RPC 改变控制负载。CLI `run_workflow` 先对零位及主手目标各执行一次 `move_js`，默认 1.0°；进入 `run_loop` 后还有 `align_to_leader` 的起始偏差检查与插值。分别记录这些步骤，不把后者误报为另一次 `move_js` 最终到位校验。

按操作员选择的范围逐轴小幅变化并回到起始附近，记录主手变化、期望映射方向、从臂实际方向。记录夹爪开合对应和主手端点原始值，不以软件截断到 0/1 证明机械端点已校准；不能安全覆盖的方向/端点写未完成，不强行推进。

操作员正常 Ctrl+C 后等待清理完成，记录退出回零的目标/误差、异常与服务归属。当前 `run_workflow` 正常处理中断并完成清理后通常返回 0（录制还取决于转换结果）；外层提前中断可返回 130。返回 0 不足以单独证明运动验收通过，返回 130 也不能直接记作正常收尾通过，必须核对实际执行到的阶段、回零与清理日志。

### 5.2 Web

CLI 已完整退出且锁释放后，在未占用端口启动：

```bash
uv run --frozen agilex-data-collection serve \
  --config "$P0_RUN/configs/web-no-camera.toml" --port 18086
```

打开 `http://127.0.0.1:18086`；远程浏览时使用现场已授权的 SSH 转发，不公开监听或临时开放端口。操作员勾选运动确认后启动跟随，等待 `following`，按同一范围检查方向与夹爪，然后点击“停止跟随”，等待 `completed` 且无错误，最后关闭服务。

保存服务输出、状态 JSON、状态中返回的 worker 日志路径及日志副本。重点核对 `startup_zero`、`gello_alignment`、退出定位的 `[position_result]`。不要用网页关闭替代停止跟随。

### 5.3 B3 通过条件

- 两入口均获得完整的启动、跟随、正常退出证据；回零/定位按各自现有判据通过，没有放宽容差。
- 六轴方向、夹爪方向及现场允许范围内端点核对完成；残差按轴报告，弧度转角度方法明确。
- 无未解释的反馈、CAN、控制、回零或清理错误；只释放本次拥有的资源，没有自动失能/reset。
- 未勾选/未确认、重复启动和共享锁拒绝等保护优先由 B1 无硬件测试证明；不为复验互斥锁同时启动第二个真机控制程序。

任一入口未通过则 B3 不通过。不得把另一个入口的结果代填。

## 6. 短采集与黄金数据（B4，对应阶段记录第 6 项）

先运行未插桩的原版路径。每个入口独立采集一段约 10 秒的保存 episode，再采一段约 10 秒的丢弃 episode；时长按真实时间戳报告，不要求恰好 300 帧。动作仍限于 B3 已确认范围，可使用稳定保持与缓慢小幅动作，不要求复杂任务。

### 6.1 CLI RGB-D

下面命令保留正常退出后的自动转换。配置中保持 `[recording].convert=true`，记录实际配置：

```bash
uv run --frozen agilex-controller record \
  --config "$P0_RUN/configs/cli-rgbd.toml" \
  --camera --camera-depth --no-camera-preview \
  --raw-data-root "$P0_RUN/cli-raw" \
  --lerobot-data-root "$P0_RUN/cli-lerobot" \
  --task "P0 CLI RGB-D baseline"
```

操作员确认 → 等待跟随正常 → `R` → 约 10 秒 → `S` → 等保存完成 → `R` → 约 10 秒 → `D` → Ctrl+C → 等退出回零、相机刷新和转换结束。标准输入必须是 TTY；不要通过普通 stdin 管道喂 R/S/D。可保存终端录屏/日志，但不能让日志工具自动回答运动确认。

检查正式 `episode_*.jsonl` 与相机帧索引、PNG、manifest、最终数据集及 `quality_report.json`。CLI 正常丢弃会移除本段临时文件，应记录丢弃事件、前后正式集数与转换结果；不要要求 CLI 产生 Web 才有的 `result.json`。

如果自动转换失败，保留原失败；硬件退出后修复环境再离线重试到**不存在的新目录**：

```bash
uv run --frozen agilex-controller convert \
  "$P0_CLI_SESSION" "$P0_CLI_RETRY_OUTPUT" --fps 30
```

两个变量由本次实际 session 与新目标路径赋值，记录 `repo_id`，不把示例变量原样当成路径。补跑成功不删除首次失败记录；自动导出本身的问题仍需说明并复验。

### 6.2 Web RGB-D

CLI 完整退出后启动：

```bash
uv run --frozen agilex-data-collection serve \
  --config "$P0_RUN/configs/web-rgbd.toml" --port 18086
```

填写任务 → 人工勾选/启动 → `following` → 开始采样 → `recording` → 约 10 秒 → 保存本段 → 等 `following` 且 `saved_episodes` 加一。再录约 10 秒并丢弃，确认集数不增加。保存需要的数据后停止跟随，等待 `completed`，再退出服务。

从状态记录真实 `raw`、`dataset`、`log` 路径。Web raw 是 `manifest.json`、`take_*/samples.jsonl`、`color_*.npy`/`depth_*.npy`、`result.json`；丢弃段的 raw 审计仍保留，dataset 不增加 episode。**不要把这套 raw 直接传给 CLI converter**，它不是 CLI raw v1/v2。

分别观察 RGB、深度、RGB-D、点云预览并留结果；预览切换的时间与模式需记录。前端若没有可用浏览器工具，可由操作员操作并留证据，Codex 继续做日志/数据检查；只有 API 测试不能记作页面实测。CLI SSH 无 Tk 弹窗是本次明确配置，不冒充桌面预览已验收。远程桌面配置不是 P0 核心完成条件，若未验证则保留原待办。

### 6.3 黄金数据回读

Codex 编写并归档只读检查脚本；对每个保存段的全部 raw 行、图像引用和目标数据帧实际回读。小片段应全量解码，不仅看目录存在或截图。

| 对象 | 检查内容 |
| --- | --- |
| raw 数值 | 行数、索引连续性、时间单调、有限值；六轴加夹爪共 7 元素、单位/顺序；已有速度和 xyzw 位姿按原 schema 核对 |
| 原始图像 | RGB 的尺寸/类型、Z16 的整数像素；CLI 16-bit PNG 解码库可能返回 int32，需确认文件位深和数值范围再无损比较；Web depth NPY 应为 uint16 |
| 相机标定 | 最终 profile 的分辨率、FPS、深度尺度、内外参、时钟域与映射；不得用请求 profile 冒充最终 profile |
| 时序/来源 | 主机单调时间与设备时间分别统计；缓存或命令填充值按已有代码说明，不把 RPC 返回时刻称为设备采样时刻 |
| 保存/丢弃 | 已保存集数、转换集数、Web result 对应关系；discard/interrupted/partial 不进入正式数据集 |
| LeRobot | `meta/info.json` 的 `codebase_version=v3.0`、实际 FPS、episode/帧数、7D action/state、RGB/深度解码、任务字段；保存段全部可回读 |
| raw→dataset 对应 | CLI 按 converter 的时间网格/最近邻规则核对，Web 按 samples 索引核对；深度按实际尺度换算，容差含浮点/存储量化，RGB 视频允许编解码误差并报告度量 |

用独立环境加载真实数据，例如参考根 `tests/test_converter_integration.py` 的 `LeRobotDataset(repo_id, root=..., depth_output_unit="m")`。CLI 用 converter 环境，Web 用 adapters app 环境；设置 `HF_HUB_OFFLINE=1`，不登录/上传。报告实际 `repo_id` 和解释器，不能只靠根环境导入成功。

CLI 原生 `quality_report.json` 原样保存；Web 无同名原生报告，由上述脚本生成 `metrics/web-quality.json`，注明生成工具/版本/规则。记录时间匹配误差 p50/p95/p99/max、各流重复/缺口/非单调数与解码错误；50 ms 等阈值从实际配置读取，不能静默丢弃超差样本让报告通过。

在只读检查前后对 raw 做文件级 SHA256，确认工具没有改变数据。保留各入口完整 raw、LeRobot dataset、全部 metadata 和质量报告，作为 golden；不能只留下挑选的几张图。

## 7. 测量工具约束与原始记录格式

P0 可以增加观测，不能改变控制语义。优先外部分析和旁路 wrapper；确需插桩时在独立 `dev-p0-...` 分支保存最小补丁，主仓/子仓分别记录。未提交的补丁也必须随证据交回。不要把插桩改动混入未插桩 golden。

- 使用 `time.monotonic_ns()` 或 `perf_counter_ns()` 测耗时，字段标明所用时钟；墙钟仅用于事件对照。跨进程使用已确认同一主机时钟域，设备时间不可直接相减。
- 控制线程只记时间、计数与必要快照到预分配/有界内存；不逐周期 print、JSON 编码、写盘或等待统计线程。不新增串口/CAN 读取，不改变休眠、超时、锁次序、主手调用频率。
- 队列/缓冲满时不能阻塞控制；标记 `probe_dropped`，该次测量不作为完整基线。数据采集完成、设备正常退出后再导出统计。
- 稳态、初始化、保存/排空、丢弃、退出分别标记；保留全部记录，只能按明确 phase 过滤统计，不能删异常值。
- 关闭观测时验证既有输出与行为不变；开启观测先用 fake/合成数据检查计数、计时、异常清理和缓冲溢出。保存测试脚本及结果。
- 做相同配置/负载下观测开关的对照，记录测量开销与重复间波动。CLI 可利用原生周期；Web 无插桩的逐周期数据不可得，就记录可获得的外部对照与这一限制，再用最轻的周期探针和详细探针对照，不能声称已精确测出“零开销”。

建议输出以下表；允许 CSV/JSONL，但字段含义必须固定，缺值用 null/空值加原因，不用 0 代替缺失：

```text
cycles.csv:
run_id,entrypoint,phase,cycle_index,clock,command_started_ns,command_finished_ns,
period_ns,observation_started_ns,observation_finished_ns,recording,preview_mode

stages.csv:
run_id,entrypoint,phase,stage,stream,sample_id,start_ns,end_ns,input_bytes,
output_bytes,queue_depth,queue_capacity,outcome

summary.json:
基线/配置哈希、测量工具哈希、窗口、数量、分位数方法、各指标、缺失原因、probe_dropped
```

观测记录自身必须带入口/进程/阶段，避免把 camera 线程的时间与控制线程串成一个周期。队列 `qsize()` 是观测值，不作为同步机制或精确证明；峰值须标“观测峰值”，同时记录容量、入队/出队/Full 计数与探针覆盖率。

## 8. 性能测量（B5）

### 8.1 运行矩阵与窗口

先通过约 10 秒 B4，再在已授权时长内执行下表。每组建议固定 **3 次 × 30 秒有效稳态窗口**，每次前留至少 5 秒稳定期。时长与重复数是本手册的测量方案，不是运动安全阈值；若现场不允许，记录实际覆盖并保留 B5 未完成，不能自动延长运动。5 秒稳定期以系统已正常 following/recording 为起点，不包含回零对齐。

| 组 | 配置/目的 |
| --- | --- |
| CLI-A | 无相机 `record`，录制关节数据：取得原生周期基线 |
| CLI-B | RGB-D 录制、无 Tk 预览：控制与写盘负载 |
| Web-A | 无相机，录制：完整控制周期用探针，区分 50 Hz 控制与 30 FPS 采样 |
| Web-B | RGB-D 录制、一个固定 RGB 预览客户端：按本轮默认 profile 测量 |
| Web-C | 与 Web-B 相同，但关闭预览 WebSocket/页面：比较预览负载；关闭网页不停止会话，仍须正常停止 |

CLI Tk 预览、点云预览、多标签与更高 profile 可作为扩展组，明确标 optional，不用它们替代上述核心组。每组最后正常保存并退出，离线转换/数据集 finalize 时间另记，不并入稳态控制统计。执行基线时不要并行跑 pytest、编译、复制大文件或离线压力测试。

必须记录负载差异：CLI 保存原生相机流，Web 保存采样选中的帧且同时调用 LeRobot；CLI 与 Web profile 可能不同。结果首先供同入口、同配置的迁移前后对比，不直接排名。

### 8.2 控制周期与抖动

CLI 原生 `control_period_ns` 对应相邻命令开始时刻差，可用 `command_time_ns` 交叉校验。首周期为 0 时排除并统计排除数量；分段首行若前一时刻不在该文件中，不要求强行校验。保存/丢弃造成的停顿单独列出，不能隐藏在只报稳态的摘要里。

Web 在 `src/agilex_data_collection/session.py::Session._control` **每次** `robot.send_action` 前的现有 `command_started` 处记录；周期是连续两次该值之差，包括未进入采样分支的周期。`samples.jsonl` 中每 30 FPS 才出现的 `command_started_ns` 只能测采样间隔，不可代替此序列。测 `GelloAgent.act()` 调用间隔也不能反推异步 USB 编码器的实际读取频率。

每个 run/phase 单独计算，再提供三次运行的范围；不要仅把全部样本混池掩盖某一次退化：

- `T = 1e9 / configured_control_hz`；报告周期与 `period_ns - T`（有符号抖动）、`abs(period_ns - T)`（绝对抖动）。
- `n`、实测时长、有效频率、min/mean/p50/p95/p99/max；分位数使用 NumPy `method="linear"`，记录版本。有效频率用 `(N-1)/(last_start-first_start)`，注意与周期样本数的区别。
- `period > T`、`period > 1.5T`、`period > 2T` 次数和比例、最长连续超期；这些是诊断分桶，不是新运动限值。`>T` 会包含普通调度微小误差，不能单凭此项宣布失败。
- 命令 RPC 耗时、观测 RPC 耗时、保存/排空/退出耗时；能观测到的主手动作年龄和相机匹配差，明确时间来源和不可观测的硬件延迟。
- CAN 统计的前后增量与采样窗口、相机帧号缺口/时间跳变/重复、队列观测峰值/容量/Full 次数；没有生产端计数则注明末尾丢帧无法证明，不能填“0 丢帧”。

不得用数据集恒定 30 FPS 时间网格、SDK 聚合 CAN 报文 FPS 或浏览器预览 FPS 代替控制频率。此阶段不凭空规定“p99 必须小于某毫秒”；保存测得基线和噪声范围。真正出现 queue.Full、超差停止、损坏数据或无法维持当前配置则是失败，需要处理后重测。

### 8.3 现有路径的序列化、复制与写盘

Codex 按下表定位观测点，保存实际函数/补丁/调用次数，分别在根与 Web app 原环境测量：

| 路径 | 定位点与拆分方式 |
| --- | --- |
| CLI 控制 RPC | `src/agilex_controller/robot_client.py` 的 pickle encode/decode 与完整请求往返分别计时，不能把等待硬件时间全部称作序列化 |
| Web IPC | `third-party/agilex-adapters/src/agilex_adapters/transport.py` 与 `src/agilex_data_collection/worker.py` 的实际 send/recv/对象序列化；先确认源码所用协议，不替换成 P1 的 msgpack |
| CLI 数值 raw | `RawEpisodeRecorder.add_sample/_writer_main`：入队、出队等待、JSON 序列化、写入、flush/fsync、save 提交分别计时 |
| CLI 图像 raw | `ImageEpisodeWriter.add/_write`、`_save_png`：队列等待、像素复制/字节序转换、PNG 编码、文件写入与逐帧 fsync、索引提交 |
| Web raw/数据集 | `Session._append`：数组转换/复制、NPY 写入、JSON 序列化/flush、`dataset.add_frame` 分开；`save_episode/finalize` 另计 |
| 相机复制 | 设备帧→NumPy、快照/预览/IPC 处实际发生的 copy 或序列化缓冲；注明哪些仅为 view、引用传递或可能由库内部复制 |

细分插桩若会明显改变实时负载，使用黄金帧离线重放原函数测细分项，在线只保留轻量总耗时。报告标 `live_observation` 或 `offline_replay`，两者不能互相冒充。

离线重放要求：

1. 使用本机黄金 RGB/Z16 与数值样本，注明尺寸、dtype、内容与实际编码参数。先预热，再至少 3 轮，序列化/复制微基准每轮至少 1,000 个样本；完整 writer 吞吐每轮至少 30 秒。空间不足时缩小计划并标覆盖不足，不自动占满磁盘；同时报告数量和持续时间。
2. 使用与正式采集相同文件系统的新建 scratch 目录，设定字节/时间上限并检查余量。不覆写 raw/dataset，不使用裸盘、drop_caches 或系统调优。测试写完保留/清理范围由用户授权。
3. 分别测 `ndarray.copy`、实际元数据序列化、PNG 编码到内存、NPY 序列化到内存、同格式磁盘写入与同步、完整 writer 重放。命名清楚，不能把 `.tobytes()` 结果叫零复制。
4. 不擅自给原来没有逐帧 fsync 的 Web 路径加 fsync 再声称是原性能；明确 buffered/flush/fsync/close 边界。内存编码基准与磁盘组合测试不简单相减推断纯磁盘时延。
5. 对每阶段报告 p50/p95/p99/max、样本数、输入/输出字节、有效 MiB/s、frames/s、失败数；吞吐分母是完整墙钟窗口，注明是否包括最终排空与同步。完整流水线另报稳态与端到端吞吐。
6. 采集后的只读 hash/全量解码与性能测量错开。NVMe/page cache 的短测结果不能写成断电持久性或长时间持续吞吐保证。

最后给出基于数据的建议：当前 profile 是否存在积压；控制路径里哪一段占时；录制放线程或进程的证据；是否值得再测共享内存。P0 可以得出“目前不足以决定，需要补测”，但必须列清尚缺什么；不能只用 `width × height × fps` 理论带宽代替测量。

## 9. GELLO 黄金序列与特征化测试（B6）

只保存最终 action 无法验证 GELLO 提取是否保持行为。当前 `DynamixelRobot` 有 ±2π 初始化偏移展开、夹爪裁剪、`_alpha=0.99` 平滑和 `_last_pos`；构造时 `get_joint_state()` 本身可能消费一次输入并改变平滑状态。

### 9.1 黄金记录

在创建 `GelloAgent/DynamixelRobot` **之前**安装只观测探针，覆盖构造、对齐、连续 act 与清理。观察现有 `DynamixelDriver.get_joints()` 返回的原始弧度值，不额外调用一次去“采样”，也不在驱动尚未启动时伪造编码器值。

`gello/initial.json` 至少包含：

- 设备/代码/配置身份、joint_ids、joint_offsets、joint_signs、follower_signs、gripper_config、start_joints 的实际值；relative_alignment 设置和对齐的主从原点。
- 构造前 `_last_pos`/alpha 的默认状态、构造后的展开 offsets 与实际已消费输入数量；缺失就标未知，不从最终输出反推。
- 调用层次与调用次序，预期频率、实测 `act()` 间隔；驱动内部缓存是否可识别、时间字段的真实含义。

`gello/sequence.jsonl` 每次记录调用序号、阶段、入口/返回单调时间、`get_joints` 输入序列、`get_joint_state`/`act` 输出、主手映射后的命令，以及若有的控制限幅后目标。六轴/夹爪语义和单位分开说明。构造内部嵌套读取用 parent call ID 或明确阶段关联，不能漏掉初始化读取。

黄金序列随已授权的正常小范围操作获取，覆盖静止、平滑变化、方向变化与夹爪开合。±2π 边界、超范围夹爪、通信失败等额外情况用离线合成序列补，不为覆盖测试在真机做极端运动或断线。

### 9.2 确定性回放与特征化

在没有硬件访问的测试中，用严格回放 driver 替代真实串口 driver，按保存的初始条件重建原 `DynamixelRobot/GelloAgent/GelloLeader`。回放耗尽、读取次数不符立即失败，禁止退回真实硬件或静默 fake 随机数。对通信失败、禁止 fake fallback、构造失败和 close 后资源释放，用现有 fake/monkeypatch 模式测试。

- 核对完整输出序列、夹爪边界、初始化展开与映射；记录最大误差和预先声明的数值比较容差。相同 float64 算法可从绝对误差 `1e-12`、`rtol=0` 开始，失败先查原因，不事后放宽以求通过；该值仅为离线数值比较，与机械臂到位容差无关。
- 比较的是已记录的输出，不能在测试时调用同一个被测函数重新生成“期望值”。按调用顺序验证有状态平滑；不需要用真实时间 sleep 重放，但保留原调用间隔供 P3/P7 比较。
- 从 B4 黄金数据补充特征化：旧 raw schema、保存/丢弃/partial 语义、时间匹配与深度尺度、CLI/Web 有意存在的差异。能复用已有测试就引用其具体节点及本次结果；缺少黄金回放的部分补测试。
- 小型数值夹具、回放脚本与测试结果随回传包返回；RGB-D 大数据可引用独立归档。测试不得需要 CAN、串口、相机或 Hub 网络。

B6 完成以回放实际运行成功为准，不以“已保存一个 GELLO JSON 文件”判定。

## 10. 完成判据与异常处理

### 10.1 P0 完成检查表

每项填写 `PASS / FAIL / NOT_RUN / BLOCKED`，附证据路径；不能把 `NOT_RUN`、`unverified` 或“预计正常”写成 PASS。

- [ ] B0：基线、环境、有效配置、硬件身份齐全；每个允许的改动有独立补丁/哈希。
- [ ] B1：当前软件必需检查通过；真实 converter 集成回读执行；观测工具已无硬件自检。
- [ ] B2/B3：现场条件确认，两入口第 5 项运动/方向/夹爪与退出完整验收通过。
- [ ] B4：两入口第 6 项保存/丢弃验收；各自完整 golden raw + LeRobot 数据集全量回读，原始数据未改变。
- [ ] B5：两入口逐控制周期基线、测量窗口/重复性/开销、队列/时序与序列化/复制/写盘性能有原始记录和统计，非观测项的限制明确。
- [ ] B6：GELLO 完整输入/初始化/输出可确定性回放；特征化测试通过并可迁移到后续版本。
- [ ] B7：报告、脚本、数据索引和哈希可复核；现场用户明确确认本轮实测通过。

全部必需项通过后才写 **P0 COMPLETE**；否则写 **P0 INCOMPLETE** 并列出下一步。PiPER-X 断令 `unverified`、可选长稳/多相机/高 profile、远程桌面未验收可单列为 P0 范围外，不借此隐藏必需项失败。

复制一份只有“通过”结论的报告不会自动完成 P0。完整黄金数据必须保留且能找回；报告必须有小型可复核证据和实际验证结论。P0 完成也不表示 P2～P7 或真机故障注入完成。

### 10.2 常见阻塞

| 现象 | 处理 |
| --- | --- |
| uv/解释器/子模块环境缺失 | 按固定锁恢复对应环境，重跑失败检查；不跨环境拼 PYTHONPATH 来掩盖依赖冲突 |
| GELLO 端口/offset 不对应 | 停止设备准备，核对本机标定；不复制历史序列号、自动扣 offset 或打开 fake fallback |
| 无 DISPLAY、Tk 预览失败 | CLI 使用 `--no-camera-preview`；记录预览未测，RGB-D 采集仍可执行；不因此配置远程桌面 |
| 回零或对齐超差 | 保存逐轴目标/反馈和日志，标 B3 失败；不调整 1.0°/1.1°、滤波或反馈值 |
| Web raw 不能被 converter 读取 | 按第 6 节分别回读，不改写 Web raw 伪装 CLI schema |
| 相机超差、queue.Full、采样落后 | 保存故障、profile、负载和队列证据，停止本轮；新配置另建 run，不能覆盖原失败 |
| 观测缓冲丢数据或明显扰动 | 改善旁路观测并先离线自检，重新采样；旧结果标无效，不编造分位数 |
| 测量揭示需要修生产逻辑 | 先写缺陷与影响；修复另立版本/补丁，经验证后重新冻结基线、重跑受影响项，不能把改前改后混为一次 |

## 11. 回传与报告模板（B7）

### 11.1 必交产物

1. `reports/P0_REPORT.md`：使用下方模板，主要结论和统计直接写入，不仅引用实验机绝对路径。
2. `reports/TESTING_APPEND.md`：可追加到开发机 `.agents/docs/stages/testing.md` 的摘要，记录日期、SHA、B0～B7 状态、证据归档、未验证项。不要覆盖历史记录，也不要自行将 `.ai-stage` 改为 DEPLOY。
3. `reports/artifacts.json`：每个 artifact 的 ID、类型、入口/run、基线/配置、原始路径、归档位置、文件数、总字节、清单哈希、状态、用途。CLI/Web golden 各自包含 raw 和 dataset，明确二者关联和 repo_id。
4. 小型回传包：报告、配置（脱敏）、统计 CSV/JSON、GELLO 数值夹具、全部测量/回放/特征化工具、补丁、必要日志与校验清单。不能只交一份无法重新计算的汇总表。
5. 大型黄金数据：尽量一并复制；如暂留实验机，明确保管位置/责任人、不可覆盖约定、恢复方法，并完成一次只读清单验证。回传报告记录每个目录文件清单的哈希；后续需要在开发机回放时必须提供数据，不能用路径文字替代实际读取。

使用仓库外已有工具或 Python `hashlib` 生成**相对路径**的文件清单；逐文件记录 size、SHA256，排序固定，排除清单文件自身。先把源数据复制到新的归档位置，再验证副本清单一致；不要移动/删除原始数据。哈希是内容校验，不代替语义回读。

可以用 `tar` 将本轮小型证据目录打包到其父目录的新文件；大数据单独打包或复制，避免套入包自身。不得包括 `.venv`、Git 对象、密钥、token、认证配置或无关实验数据。报告可以写脱敏设备别名，实验机保留别名到实物身份的对应关系。证据拷贝时保留测量工具和 fixture 的对应哈希，不手工编辑统计值。

### 11.2 P0_REPORT.md 模板

以下模板由实验机 Codex 填实；没有执行的格子保留未完成，不预填成功。

````markdown
# P0 基线与测量报告

- 状态：P0 COMPLETE / P0 INCOMPLETE
- 测试日期/时区、操作者、实验机别名：
- 主仓 SHA/版本、子模块清单、dirty 状态/观测补丁：
- 测试范围与手册版本/哈希：
- 现场授权与用户实测确认：时间、原话摘要、覆盖运行编号
- 一句话结论：

## 环境与配置

机器/存储/USB、各解释器/关键依赖、硬件/固件/控制模式：
配置文件与 SHA256、有效参数覆盖、profile/深度尺度/标定：
与手册建议基线的差异及原因：

## 执行结果

| 项 | PASS/FAIL/NOT_RUN/BLOCKED | 运行/命令与退出码 | 证据 | 限制/下一步 |
| --- | --- | --- | --- | --- |
| B0 | | | | |
| B1 | | | | |
| B2 | | | | |
| B3 CLI / Web（分行） | | | | |
| B4 CLI / Web（分行） | | | | |
| B5 各组（分行） | | | | |
| B6 | | | | |
| B7 | | | | |

## 最小运动

| 入口/阶段 | 目标 rad | 初始/最终反馈 rad | 六轴残差 deg | 实际判据/容差 | 结果/现场观察 |
| --- | --- | --- | --- | --- | --- |

方向/夹爪核对、正常退出与清理、未覆盖范围：

## 黄金数据与质量

| 入口 | raw/dataset artifact ID | 保存/丢弃数 | 时长/原始与导出帧数 | RGB/Z16/profile | 回读/时序结论 |
| --- | --- | --- | --- | --- | --- |

CLI 质量报告；Web 质量报告生成方法；raw 前后哈希；dataset 逐帧对应误差：
时间来源/缓存/无法观测的末尾缺帧限制：

## 控制与数据路径性能

单位统一标注，逐 run 报告，不只混池：

| run/phase | 周期数/窗口 | 有效 Hz | 周期 p50/p95/p99/max ms | 绝对抖动 p99 ms | >T/>1.5T/>2T 次数 | 队列/丢帧 |
| --- | --- | --- | --- | --- | --- | --- |

| run/stage | live/offline | n/字节 | p50/p95/p99/max ms | MiB/s 与 frames/s | flush/fsync 边界 | 失败/限制 |
| --- | --- | --- | --- | --- | --- | --- |

分位数方法、暖机/稳态/保存边界、三轮波动、插桩开销、probe_dropped：
CAN 前后增量、相机时间差、保存/排空/退出延迟：
线程/进程、共享内存与后续吞吐配置的建议及证据：

## GELLO 与特征化

初始化条件、输入/输出 fixture、调用数与 act 间隔：
回放命令、数值容差、最大误差、异常路径覆盖、测试结果：
可供 P3/P7 使用的比较方法：

## 缺陷与未验证项

失败首次出现的 run/日志、原因证据、修复/重跑记录：
PiPER-X runtime 停发 / HAL 崩溃 / 链路中断：均为 unverified（本次不做故障注入）。
可选长稳、高 profile、多设备、RDP 等未执行项：
阻塞 P0 的项与仅阻塞后续阶段的项分开列明：

## 证据交接

小型包文件名/大小/SHA256、artifacts.json 与清单哈希：
CLI/Web 完整 golden 的归档位置、大小、清单、保管/恢复方式：
拷贝后校验结果、raw 未改证据：
用户实测确认；允许继续的软件工作与仍待验收的真机工作：
````

填写完毕后运行本机 `make docs` 检查新增项目记录链接，再核对报告中的路径、命令、数量和哈希。最终向用户报告 P0 是否完整、阻塞项和需要带回的文件。**不自动提交、推送、合入 main 或升级依赖。**
