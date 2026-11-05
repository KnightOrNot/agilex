# Repository Guidelines

> 本文件是 AgileX 项目的唯一项目指令文件。按“最新日期优先”阅读；标为“历史”的内容只用于追溯，不再作为操作依据。开始改动前先读 `README.md` 和 `docs/index.md`；安装、硬件和子模块操作读 `docs/installation.md`。

## 1. 工作方式与 AI 工具

- 只用根目录 `CLAUDE.md` 作为项目指令文件，不再维护根目录 `AGENTS.md`。
- 使用全局 gstack。开始前确认 `~/.claude/skills/gstack/bin` 存在；缺失就停止并让用户安装：

  ```bash
  git clone --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
  cd ~/.claude/skills/gstack && ./setup --team
  ```

- 所有网页浏览用 `/browse`，不用 `mcp__claude-in-chrome__*`。常用技能：`/qa`、`/review`、`/investigate`、`/ship`。
- `.claude/settings.json` 的 PreToolUse 钩子运行 `.claude/hooks/check-gstack.cjs`，缺少 gstack 时阻止 Skill 调用。缺 Node.js 时让用户安装；不要绕过。
- 用户会监控五小时 AI 额度。当用户通知剩余 15% 时，立即停止新实现，在 `CLAUDE.md` 记录完成项、检查、失败和 TODO。代理无法读取额度，不要声称自动监控。
- 默认只读优先：先审计，再改代码；先模拟，再真机。
- 不提交、不推送、不发布子模块，除非用户明确要求。改动保持未提交时，在回复中说明。
- 模拟结果和真机结果分开报告。不要把模拟、headless 浏览器或 mock 说成硬件验证。
- 文档与代码冲突时，以最新日期和实际代码为准，并在本次改动中修正文档。

## 2. 项目定位与两个入口

AgileX PiPER-X 六轴机械臂 + GELLO 主手 + RealSense D455F 的遥操作、数据采集和精密装配项目。

| 入口 | 用途 | 输出 |
|---|---|---|
| `agilex-controller` | 终端命令与 Shell 脚本：跟随、录制、JS 定位、离线转换 | raw JSONL + 图像，再由 converter 生成 LeRobot Dataset v3 |
| `agilex-data-collection` | 浏览器面板：跟随、采样、保存/丢弃、实时预览、LeLab 管理 | 直接写 LeRobot Dataset v3，同时保留 raw 审计数据 |

两个入口并列且同等常用，不是“主项目 + 扩展”。两者都读 `config/default.toml`。`[collection]` 只属于浏览器应用，controller 忽略它；`[robot]`、`[gello]`、`[camera]`、`[safety]`、`[paths]` 两个入口共用。

当前下一阶段工作是无传感器末端力估计与精密装配，见第 10 节。

## 3. 仓库结构与职责

### 3.1 根目录

- `src/agilex_controller/`：配置、客户端组合、SDK 子进程生命周期、JS 定位/跟随、raw RGB-D 录制。
- `src/agilex_data_collection/`：浏览器应用、硬件 worker、预览编码、LeLab 集成。
- `config/default.toml`：唯一应用配置，含安装相关的 GELLO 标定。
- `scripts/`：`setup.sh` 和四个 controller Shell 包装，覆盖 legacy/camera 的 follow/record。
- `tests/`：controller 行为测试。`docs/`：架构、安装、CLI、配置、故障排查，保留硬件参考资产。
- `data/raw/`：不可变输入；`data/lerobot/`：可重建输出。两者都不进 Git。

### 3.2 五个子模块（全部在 `third-party/`）

| 路径 | 职责 | 发行/导入名 |
|---|---|---|
| `third-party/agilex-sdk-python/` | CAN 硬件、运动控制、反馈、ZMQ 服务 | `agilex_sdk_python` |
| `third-party/agilex-gello-software/` | GELLO/Dynamixel 读取、设备校准 | `agilex_gello_software` |
| `third-party/camera-submodule-d455f/` | RGB-D 采集、设备时间戳、深度单位与标定 | 发行/CLI `camera-realsense`，导入 `camera_realsense` |
| `third-party/lerobot-converter/` | raw 校验、时间戳重采样、LeRobot 输出 | `lerobot_converter` |
| `third-party/agilex-adapters/` | LeRobot Robot/Teleoperator 协议、私有 IPC 客户端 | `agilex_adapters` |

相机远程是 `git@github.com:KnightOrNot/camera-realsense-d455f.git`。目录名 `camera-submodule-d455f` 与发行名 `camera-realsense` 不同，不要改导入名。

### 3.3 职责边界

- 硬件访问只在 SDK。controller 和采集应用通过 SDK 的 CLI/API/ZMQ 消费，不直接打开 CAN。
- 相机库负责采集和 SDK 到主机时钟映射；controller 负责生命周期和 raw 持久化；converter 负责时间戳匹配和 LeRobot 输出；adapters 负责 LeRobot 设备协议。
- 应用层拥有 Web UI、worker 生命周期、控制和持久化；adapters 不拥有网页或工作流。
- 不要在 controller 里复制 converter 的匹配逻辑，也不要在 adapters 里放硬件访问。
- SDK 硬件层保持上游实现不变；其独立 CLI/server 默认加载 SDK 自己的 TOML。

## 4. 分支、子模块与版本

### 4.1 分支策略

- `main` 是已发布基线；结构迁移和相机重命名先在 `main` 发布。
- 后续开发在 `dev`，包括 Python 3.12 迁移。不要把 Python 迁移混进 `main` 的结构提交。
- 五个 `.gitmodules` 在 `dev` 上跟踪子模块的 `dev`。只有显式升级才用 `--remote`。
- 子模块先提交并发布测试通过的改动，再更新父仓库 gitlink。

### 4.2 子模块操作

```bash
git submodule sync --recursive
git submodule update --init
# 只有明确升级时：
git submodule update --remote --merge
```

移动目录后重建虚拟环境。不要手改 `.gitmodules` 的 branch/url 来绕过版本问题。

### 4.3 Python 与依赖

- `dev` 上 controller、GELLO、SDK、camera、converter、adapters 全部使用 Python 3.12。
- 根和 GELLO 要求 `>=3.12,<3.13`；其他子项目 `>=3.12`。使用各项目的 frozen lock，不跨解释器复用 `.venv`。
- LeRobot：adapters 的 `app` extra 固定 0.6.0，converter 固定 0.6.1。两者都要跑真实数据集回读。
- LeLab 固定 `9b5afaee33baa1d773e499937564f3831d25de22`。
- GELLO 固定 PyPI `dynamixel-sdk==4.0.5`，使用 `agilex_gello_software` 命名空间；不要引入嵌套 SDK 或 `gello.*` 导入。
- adapters 的 `app` extra 保留完整嵌套 extras 闭包和 torch/torchvision CPU index。删掉闭包会丢数据集依赖；上游 Git LeRobot 与 CPU torch index 冲突。
- 浏览器数采仍使用独立的应用环境（`uv run agilex-data-collection setup`），位于 `third-party/agilex-adapters/.venv`，与 controller 的环境分开。
- 相机性能默认 640x360@90，失败回退 60，再回退基线分辨率 30 FPS；每个流先探测实际接收帧率再暴露帧。

## 5. 环境与命令

### 5.1 初始化

```bash
./scripts/setup.sh                                  # 首次完整安装
./scripts/setup.sh --skip-system --skip-submodules  # 保留本地子模块改动
./scripts/setup.sh --check-only                     # 只检查，不安装、不访问硬件
uv run agilex-data-collection setup                 # 浏览器数采的独立 3.12 环境
```

`setup.sh` 不配置 CAN、不访问串口、不发运动命令。加入 `dialout` 后需要重新登录。

### 5.2 只读检查

```bash
uv run agilex-controller config
uv run agilex-controller read
uv run agilex-controller status
uv run --project third-party/camera-submodule-d455f camera-realsense info --profiles
```

`read` 只打开主手串口；`status` 调用 SDK 只读检查，要求 CAN 已配置。手工配置 CAN：

```bash
./third-party/agilex-sdk-python/scripts/config_can.sh
```

### 5.3 两个入口

```bash
# CLI
./scripts/start_gello_follow.sh
./scripts/start_data_record.sh
./scripts/start_camera_follow.sh
./scripts/start_camera_record.sh
uv run agilex-controller follow      # Python 等价入口
uv run agilex-controller record
uv run agilex-controller convert data/raw/SESSION data/lerobot/DATASET

# 浏览器
uv run agilex-data-collection serve
uv run agilex-data-collection serve --simulate
```

四个 Shell 脚本都是 CLI 包装。相机脚本默认启用采集和预览；legacy 脚本默认无相机。会控制真实机械臂的命令，运行前必须固定底座、清空工作区、确认急停，并完成只读检查。默认启动流程在运动前显示目标并要求输入 `yes`。

### 5.4 测试、lint、构建

```bash
uv run --frozen pytest
uv run --frozen ruff check src tests
uv run --frozen ruff format --check src tests
uv run --project third-party/agilex-adapters --extra app pytest third-party/agilex-adapters/tests -q
uv build
bash -n scripts/*.sh
```

测试默认不访问硬件：本地 ZMQ 假服务、模拟主手、合成 RGB-D 帧。适配包测试包含真实 LeRobot 工厂、Unix IPC、模拟 RGB-D 保存/丢弃/回读。测试中的 flock 文件放在 pytest 临时目录，避免和操作员的活动硬件锁竞争；生产锁语义不变。

## 6. 配置规范

- 唯一应用配置是 `config/default.toml`。不要新增 `config/data_collection.toml` 或第二份应用配置。
- `[collection].hardware_config` 为空表示 `[robot]`/`[gello]`/`[camera]`/`[safety]`/`[paths]` 从同一文件读取；指定实验 TOML 时，硬件配置从该文件读取，应用配置仍来自 `default.toml`。
- controller 的 legacy loader 保留但忽略 `[collection]`；`AppConfig.load` 在有 `[collection]` 时读取它，也接受独立的扁平 TOML。不要反过来让浏览器应用忽略 controller 段。
- 五个子模块各自暴露 `config/default.toml`；使用各仓库自己的 loader，不要假设父 TOML 会自动下发。四个新 loader 支持部分覆盖；相机保留整文件选择语义。保留上游嵌套子模块和 GELLO 原生 YAML 工具不变。
- 显式传入 profile 的 `ColorStream` 调用保持手动语义，除非调用方显式选择 mode。`[collection]` 的 `camera_mode` 只影响浏览器应用，legacy controller profile 不变。
- 打包的默认 TOML 链接指向仓库内唯一源文件，并物化进 wheel；改打包时验证 wheel 在 checkout 外能加载默认值。
- GELLO 标定通过 `DynamixelRobotConfig` 传入；不要为了这套安装修改库的端口映射。设备 ID、弧度 offset、方向、夹爪端点必须与当前标定一致；`follower_signs` 是额外的主手到从臂方向映射。
- 相机 `camera_mode` 从 `[collection]` 读取，默认 `auto`。不要在活动录制流中切换 profile；不要丢失原生 Z16、时间戳来源或最终 profile 的标定。
- 预览配置：`preview_depth_max_m=3.0`、`preview_cloud_stride=4`。点云只支持零畸变的 rectified intrinsics；颜色编码深度，不做 RGB 外参投影；输出 little-endian float32 XYZ 米，最多 20000 点。
- 路径字段相对于项目根目录解析。

## 7. 编码与测试习惯

- 四空格缩进；公共接口写类型注解；函数/模块 `snake_case`，类 `PascalCase`。测试文件 `test_*.py`。没有覆盖率阈值。
- 测试 mock 硬件，但真实使用本地 ZMQ 和 raw 兼容路径。覆盖错误、中断、初始化失败和清理顺序。
- 真机验证需要文档化步骤和操作员确认。不要把 mock、仿真或 headless 浏览器结果写成真机验证。
- 保留上游 GELLO 风格，不做无关格式化；在它的目录运行 pytest 和现有 CI lint。
- 不要通过 TCP 暴露 pickle IPC；不要运行相互竞争的控制循环。浏览器 worker 复用低层硬件 helper、共享硬件锁，并使用 owner-private Unix IPC 和命令 watchdog。
- 重负载导入（数据集等）放在硬件启动前，避免首帧录制时 GIL 停顿。
- 修改行为时同步更新 `README.md`、`docs/` 和 `CHANGELOG.md`；文档和代码同一次改动。
- 不要删除 `data/raw/`；不要把 `data/raw/app/` 或 `data/lerobot/app/` 里的合成会话当成操作员数据。

## 8. 硬件、安全与数据边界

- 没有操作员明确授权，不配置 CAN、不访问串口/相机、不发送运动、不做负载标定、不做 F/T 对比。
- 测试和 CI 使用 fake 设备、本地 IPC、合成 RGB-D；模拟不得访问物理硬件。
- JS 定位容差 `position_tolerance_deg` 当前为 **1.1 度**（用户 2026-10-20 决定）。不要减 offset、改运动模式或自动重校准。启动和退出使用同一容差。
- 默认启动流程必须在运动前显示目标并要求 `yes`；浏览器启动必须保留未勾选的运动确认和后端 guard。开始按钮同时依赖确认、任务和状态，防止重复提交，错误原因用中文显示。
- 力控/导纳闭环必须低通、限幅、死区和看门狗，并保留力/力矩上限和急停。估计力只读，不能未经安全处理直接进闭环。
- 数据完整性：保留原生 Z16、标定和单调时间戳来源；raw 输入不可变；LeRobot 输出可重建。新 raw app 格式独立于 legacy converter 输入。
- Hugging Face 上传会发布外部数据，必须由操作员认证并明确授权；本地删除只允许删 `data/lerobot/app` 下的本地数据集，禁止 Hub 删除。
- 真机结果单独报告，包含 session、命令、容差和异常。

## 9. 文档、提交与发布

- `README.md` 覆盖两个入口的安装、配置、CLI、浏览器数采、预览、JS 容差、数据、LeLab 和故障排查。没有单独的 collection 手册。
- 提交信息用简洁祈使句和 conventional prefix。PR 说明行为、受影响仓库、检查、硬件验证状态和相关 issue。
- 子模块先提交并发布，再更新父仓库 gitlink。父仓库和子模块不会自动同步。
- 默认不提交、不推送、不发布，除非用户明确要求。用户说“保留未提交”时，不要顺手提交。
- 不把合成数据、临时截图或 `/tmp` 产物写进仓库。

## 10. 当前工作：末端力估计与精密装配（2026-11-05）

用户指定 `~/lab/demo/` 中的 `精密装配-演示方案.pdf`、`README.md` 和 `CLAUDE.md` 作为下一阶段工作依据。目标是让 AgileX PiPER-X 在不额外安装末端力/力矩传感器的前提下估计末端受力，并把力/接触信息接入插销等精密装配策略。demo README 更详细，PDF 是范围与决策的原始依据。

### 10.1 目标与路线优先级

装配流水线：任务指令 → 阶段规划器 → VLA（抓取、接近、粗对准）→ 接触建立与阶段切换 → 接触策略（搜索、调整、插入）→ 完成验证 → 释放。失败时退让或重新抓取。接触调整和异常中断在本机执行，不得阻塞等待高层模型响应。

按新增硬件成本排序的三条路线：

1. **电机电流 → 关节力矩 → 动力学残差 → 末端 wrench**（首选，只需驱动器可读电流）。代表工作 TA-VLA，在 LeRobot 数据中增加 `observation.effort`。
2. **本体感觉局部接触策略**，不显式估计力（读不到电流时的兜底）。代表工作 Blind Precise Assembly，只用 q、q̇、末端位姿/速度和上一动作；真机零样本插销成功率 73%。
3. **腕部 6D F/T 或机械臂内置腕力估计**（精度最高，建议作为真值校验而非第一步）。代表工作 ForceVLA / ForceVLA2；ForceVLA2 的代码和数据尚未发布。

关键判断：插销任务不一定需要连续、精确的力数值。显式力矩路线和 blind 路线可以并行验证。

### 10.2 本仓库相关的硬件事实

- PiPER-X 是 6 自由度。SDK 的 `get_motor_diagnostics()` 已逐轴返回 `motor_current_a`、`motor_torque_nm`、驱动器电压/温度、FOC 状态和反馈频率；`PiperXState` 目前只含关节位置、法兰位姿、使能/错误状态和反馈时间，不含电流或力矩。该诊断方法是逐轴轮询，不是高频流。
- Phase 0 仍需实测确认：电流/力矩的单位与符号、电机侧还是关节侧、反馈频率、`k_t`、温漂，以及控制接口是否支持力矩、阻抗或力位混合。当前基线只有位置控制。
- GELLO 是主端，Dynamixel 的电流/负载是主端信号，不能当作从端 PiPER-X 的末端力。
- 硬件访问保持在 SDK；控制器和采集应用只消费 SDK 输出，不直接打开 CAN。

### 10.3 数据采集

统一记录并对齐时间戳：`timestamp`（单调时钟）、`q`、`q̇`、`i` 或 `τ_meas`、`τ_cmd`、`tcp_pose`、`gripper_width`、`action`、`images`（前视/腕部可选）、`success`。策略数据 50–100 Hz；底层电流/力矩 1 kHz，用于参数辨识。LeRobot 数据把力矩放入 `observation.effort`（单臂 6 维，双臂 14 维），与 `observation.state` 并列；力矩归一化统计必须与 state 分开。

### 10.4 估计器实现顺序

1. `τ_joint,i ≈ k_t,i · i_i · N_i · η_i`，先加低通滤波，观察插销过程中的力矩曲线。
2. 加入空载、夹爪和零件重力项 `g(q)`，以及库仑加粘滞摩擦 `τ_f = f_c·sign(q̇) + b·q̇`，得到 `τ_ext = τ_meas − [M(q)q̈ + C(q,q̇)q̇ + g(q) + τ_f]`。
3. 不要直接对编码器位置做二阶差分；使用广义动量观测器，稳态 `r ≈ τ_ext`。接触检测带宽 10–50 Hz，力控闭环一般不超过 20–30 Hz。
4. 映射到 TCP：`τ_ext = Jᵀ(q)·F_ext`。6 自由度非奇异时 J 为 6×6，可直接求逆；接近奇异用阻尼最小二乘 `(J·Jᵀ + λI)⁻¹·J·τ_ext`。J 必须按工具长度、夹爪和零件抓取位置标定；零件质量要作为独立负载辨识，不能并进 `g(q)`，否则接触力会被低估。
5. 噪声过大时降低带宽，或改用学习式回归和接触状态分类（TCN、MLP 或小型 Transformer；标签来自临时 F/T、仿真真值或已知质量悬挂）。

标定顺序：空载重力补偿 → 加夹爪重新辨识 → 加典型零件辨识负载 → 用已知质量悬挂检查幅值和方向 → 有条件时借 F/T 传感器做对比，拟合系统偏差。

### 10.5 仿真、策略集成与评测

- 仿真基准用 AssembleBench（圆/方销、齿轮、螺母；默认不向策略暴露力观测），资产用 mjfit（多形状插销、齿轮、螺纹）。Isaac Lab 可用 `get_link_incoming_joint_force()` 读取力真值；MuJoCo 接触力和关节力矩可做标签。域随机化覆盖零件尺寸/形状、间隙、摩擦、质量、抓取与夹具位姿、接触参数。
- 策略集成三选一：A) TA-VLA 式，把估计关节力矩作为 effort token 注入 π0，历史 10 帧，辅以未来力矩预测；B) Blind 式，接触阶段只用 q/q̇/动作历史；C) ForceVLA/ForceVLA2 式，有 6D F/T 且控制器支持力位混合时使用。
- 控制层：有力矩/阻抗接口时用阻抗或力位混合；只有位置接口时用导纳 `q_cmd = q_meas + K⁻¹·(F_des − F_ext)`。估计力进入闭环前必须低通、限幅和加死区；始终保留力/力矩上限、看门狗和急停。
- 评测同时记录：成功率（按形状、尺寸、间隙）、插入时间或搜索路径长度、峰值接触力和超调、与 F/T 或仿真真值的估计误差、未见零件泛化、sim2real 差距。

### 10.6 风险与边界

电流估力矩受摩擦、重力、负载、温漂和电流环噪声影响；二阶差分 q̈ 会让噪声淹没接触信号；J、工具长度和抓取位置误差会放大；6 自由度本臂没有冗余零空间问题，但奇异位形仍需阻尼最小二乘；连续力大不等于装配成功（卡住时力大但方向可能错），需要搜索策略或接触状态分类；学习式估计依赖标签，存在 sim2real gap；估计力有延迟和偏差，力控闭环必须限幅、看门狗和急停。

### 10.7 待确认与仓库侧下一步

Phase 0 硬件审计：控制接口（位置/速度/力矩/阻抗）、电流/力矩读取频率与单位、`k_t`、夹爪型号与开度反馈、相机布局、GPU、安全限制（关节速度/力矩上限、急停）。仓库侧优先做：

- 在 SDK 增加带时间戳的高频电机电流/力矩流式读取，不逐帧轮询诊断接口；保留现有只读接口和 CLI 兼容性。
- 在控制器新增估计器模块（重力/摩擦辨识、动量观测器、J 映射），先用 fake 或回放数据测试。
- 在采集和 LeRobot 输出中增加 `observation.effort`（6 维）及标定元数据。
- 所有力信号默认只读并限幅；物理运动、负载标定和 F/T 对比必须由操作员授权，本工作流不得自动执行。

本摘要来自代码检查和文档阅读，未进行任何硬件读取、标定或运动验证。

## 11. 历史检查点与决策

### 11.1 2026-11-05 布局、分支与 Python 迁移

- 五个子模块移到 `third-party/`；相机目录改名 `camera-submodule-d455f`，发行/CLI 仍为 `camera-realsense`，导入仍为 `camera_realsense`。
- `main` 先发布结构迁移，`dev` 从该基线创建并做 Python 3.12 迁移。
- 根/GELLO `>=3.12,<3.13`；controller/GELLO/SDK/camera 全部 3.12；`.gitmodules` 在 `dev` 跟踪子模块 `dev`。
- 旧文档中把 `agilex-sdk-python/`、`agilex-adapters/`、`camera-realsense/` 等直接放在根目录的路径说明已废弃。

### 11.2 2026-10-29 远端 main 基线

- 用户授权把五个子模块迁到可获取的远端 main，因为旧 gitlink 无法 fetch；先发布测试过的子仓库，再更新父 gitlink。
- 当时 GELLO main 使用 `agilex_gello_software` 命名空间和 PyPI DynamixelSDK 4.0.5；不要嵌套 SDK 或 `gello.*`。物理 `DynamixelRobot(real=True)` 拒绝 fake fallback。
- 当时基线验证：controller 122、adapters/application 12、camera 59、SDK 59、GELLO 12、converter 12；lint、camera/SDK Pyright、六个发行构建和 wheel 外部导入通过。系统 FFmpeg 和 libusb 由用户安装。ROS 2 远端工作流在 GELLO `04c6e1a` 通过（run `40887299012`，16m39s），post-step 用 `push: never` 修复。新 clone 检出五个 pinned commit 并通过离线 lock 一致性检查。
- 这些计数是 2026-10-29 快照；`dev` 迁移后以最新测试输出为准。
- 随后的相机/配置验证：298 tests 通过（controller 91、camera 64、SDK 65、GELLO 29、converter 28、adapters 21）；camera/SDK Pyright、各仓库 lint、GELLO 离线 upstream audit 和发行构建通过；五个 wheel 在 checkout 外解压并加载了与仓库一致的物化默认 TOML。该次没有相机采集、CAN 运动或远端推送。

### 11.3 2026-10-20 物理启动调查

- session `20261020_121045_811fe47f` 通过 CAN/相机初始化，但 J3 在启动和清理时停在 +1.032 度，超过当时的 1 度容差。只读诊断：六轴使能、反馈约 3.6 ms、无电机/臂故障、CAN 1 Mbit/s 无总线错误。
- session `20261020_153551_6f98d01b` 再次失败，J3 +1.015 度。SDK `limits` 显示 J3 范围 -170..0 度，零位是上限；静止时输出侧 +1.015 度、电机侧 +0.516 度、保持力矩 -7.6 N·m、无故障位。约 0.5 度差来自限位处的输出侧柔顺/回差。
- 用户随后明确把 `position_tolerance_deg` 提到 **1.1 度**，取代 1 度。仍不得减 offset、改运动模式或自动重校准。
- 应用定位日志记录 stage、六轴启动/最终反馈、残差、观测范围和成功命令数；worker 分开报告主错误和清理错误，浏览器优先显示结构化诊断。
- session `20261020_121535_49fee27a` 通过启动零位（J3 残差 0.921 度）、GELLO 对齐和退出零位；首个保存 episode 513 帧 @30 FPS。操作员明确说按了 Ctrl+C；不要仅凭心跳超时推断保存时 GIL 停顿。1.032 度残差的可重复性仍未验证。
- 当时检查：108 root、22 adapter/app；Ruff 和根构建通过。测试 flock 隔离到 pytest 临时目录。改动当时未提交。

### 11.4 2026-10-20 采集 UI 优化

- 步骤 1–4：1) `serve` 在现有锁下用 SDK 脚本和硬件 TOML 配置 CAN；模拟和 setup 跳过；失败阻止启动。2) 删除未使用的本地数据集列表链接。3) `/dataset-browser` 包装官方 `/edit-dataset` 并提供永久返回链接。4) UI 紧凑化，保留运动确认；原始状态放进可展开 details。
- 步骤 5：预览支持 `rgb|depth|rgbd|cloud` 四种 WebSocket 模式；显示浏览器呈现 FPS、观测/目标采样 FPS、启动探测的捕获 FPS 和模式对应的分辨率；`pointcloud.js` 原生 WebGL，支持 orbit/zoom/双击复位，无 CDN；同源检查、两 viewer 上限、断线释放、固定 deadline、旧显示帧丢弃。原生 Z16、标定和时间戳不变。
- 预览实现不变量：编码和点云计算在控制线程外，不能阻塞控制或录制；viewer slot 在 `accept` 前占用，避免并发握手超过上限；会话 generation/sequence 防止跨会话缓存帧；FPS 时钟在首帧解码后开始，避免 WebGL 初始化压低首次读数；原 JPEG 端点保持兼容。
- 验证：root 118、adapter/app 32 通过；Ruff 和两个构建通过；`pointcloud.js` 进入 root wheel 并以 JS MIME 提供；headless Firefox 在 64x48 模拟下四种模式约 30 FPS，点云 192 点，拖拽/缩放/双击生效。只读保存元数据确认 D455F USB 3.2、640x360@90、rectified depth intrinsics 和原生单位。不是真机或全分辨率验证。
- 待办：真机全分辨率吞吐/时序、CAN/sudo 行为、操作员显示器响应式布局和长时间多标签行为。

### 11.5 2026-10-20 LeLab 合并、上传、删除

- `/datasets/merge`、`/upload-dataset`、`/dataset-info`、`/hf-auth/login` 代理官方路由；merge 写 `data/lerobot/app/local/<name>`，不改源；upload 走 LeLab `push_to_hub`，需要操作员 HF 认证；`/jobs` 和 `/jobs/hub` 故意保持 404。motion、SO101 标定、training/inference 和 Hub 删除故意不提供。
- `/dataset-browser` 携带 LeLab 支持的 `?api=` 覆盖，让 localhost/127.0.0.1 和自定义端口无需 CORS 补丁。未实现 SPA 路径（`/recording`、`/teleoperation`、`/training`、`/training/{id}`、`/inference`、`/calibration`）服务端重定向到 `/dataset-browser`。
- `/delete-dataset` 是应用自有路由，只允许本地删除；`delete_from_hub` 返回结构化 400；未知数据集 404；活动 session 409。官方 handler 在配置根内执行受保护的 `rmtree`。
- LeRobot 在 import 时冻结 `HF_LEROBOT_HOME`；`create_app` 同时重绑 `lerobot.datasets.dataset_metadata.HF_LEROBOT_HOME`，让上传/删除/dataset-info 指向本地数据根。
- `/dataset-browser` 用 MutationObserver 向同源 iframe 注入策略：禁用 Back/Back to Home、Skip Upload、Record more、Create new dataset、tour、Hub 删除复选框；保留 Merge/Upload/Delete、选择、回放和上传表单。`pushState`/`replaceState` 把未实现路由改写到 `/edit-dataset`；`fetch` 包装在删除成功后重载 picker。
- 验证：118 root、41 adapter/app；Ruff 和构建通过；Node fake DOM 验证策略；headless Firefox 验证禁用项、删除、merge 模态和上传摘要。没有真实 HF 上传；upload 用 monkeypatch `push_to_hub`；merge/delete 用合成 probe 数据集。

### 11.6 2026-10-20 UI 信息清理

- 移除首页原始状态 JSON（“会话详情”、`<pre id="status">`）；上传页隐藏 Repository ID 和 About HuggingFace Hub Upload 块，保留摘要、tags、private 和 Upload；merge 对话框隐藏内部 “Saved locally as local/<name>” 提示。
- 保留：预览 FPS/分辨率/捕获统计、LeLab 数据集元数据、禁用控件/Jobs 侧栏/tour、上传 tags/private。
- 验证：118 root、41 adapter/app；Ruff 和构建通过；headless Firefox 验证四个页面。改动当时未提交。

### 11.7 2026-10-20 文档与配置合并

- 用户把 `agilex-controller` 和 `agilex-data-collection` 定为两个并列、同等常用的入口，不是主项目加扩展。
- `README.md` 覆盖两个入口；删除 `docs/data-collection.md` 和 `docs/data-collection-quickstart.md`，内容并入 README、`docs/index.md`、`docs/installation.md`、`docs/reference/{config,cli,errors}.md` 和 `docs/reference/submodule-config.md`。
- `CHANGELOG.md` 精简为按版本摘要。`config/data_collection.toml` 删除，collection 设置进入 `config/default.toml` 的 `[collection]`。
- `AppConfig.load` 支持 `[collection]` 和独立扁平 TOML；legacy loader 保留但忽略 `[collection]`。默认配置路径改为 `config/default.toml`。
- 当时没有代码路径、硬件行为或数据集格式变化；改动当时未提交。

## 12. 待办与已知限制

- 操作员监督下的物理验证：GELLO/PiPER-X/RealSense 启动、CAN/sudo、运动响应、全分辨率预览/录制吞吐、时间戳质量、响应式布局、多标签长时间运行。
- 精密装配：Phase 0 硬件审计、力估计器、`observation.effort` 输出、仿真标签和策略集成，均未开始或未验证。
- 相机 profile 切换只允许在非录制状态；物理吞吐验证仍未完成。
- 端口 8000 的旧服务在 2026-10-20 清理后消失，未被直接终止；重启需操作员授权。
- 合成会话可能在 `data/raw/app/` 和 `data/lerobot/app/`；不要当操作员数据，不要删除 raw。
- ForceVLA2 代码/数据未发布；不能直接复现。
- `gstack-team-init` 会重建 `CLAUDE.md`；不要在本仓库重跑，以免覆盖本文件中的项目约定。
