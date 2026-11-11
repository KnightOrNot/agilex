# 项目资料

## 定位与目标

为操作 AgileX PiPER-X 六轴从臂、GELLO 主手和 RealSense D455F 的研究人员提供遥操作与 RGB-D 数据采集。命令行与浏览器入口并列，共用设备配置和硬件互斥锁。

| 入口 | 职责 | 验收标准 |
| --- | --- | --- |
| `agilex-controller` | 跟随、raw 录制、JS 定位、离线转换 | 错误和中断正确清理，正式 raw 可被 converter 回读，partial 不冒充完整数据 |
| `agilex-data-collection` | 浏览器跟随、保存/丢弃、预览、LeLab 管理 | 模拟生命周期可回读，真机需另行验收；保留原始 RGB/Z16、标定和时间审计 |

当前阶段读取根目录 `.ai-stage`；当前验收与待办只维护在 [测试记录](docs/stages/testing.md)。末端力估计与精密装配是后续研究范围，见 [规格草案](docs/specs/force-estimation.md)，尚未实现或验收。

## 模块与依赖边界

| 路径 | 所有权 |
| --- | --- |
| `src/agx_sim/` | P1 无硬件设备仿真、IPC 与控制权限；不接管现有真机入口 |
| `third-party/agilex-contract/` | 独立纯类型与消息校验契约包，导入名 `agilex_contract` |
| `src/agilex_controller/` | 配置、SDK 客户端与进程、JS 跟随、raw 生命周期 |
| `src/agilex_data_collection/` | 浏览器 UI、worker、预览、直接 LeRobot 写入与 LeLab 集成 |
| `config/default.toml` | 唯一应用配置；两个入口共用硬件表，浏览器额外读取 `[collection]` |
| `third-party/agilex-sdk-python/` | CAN、机械臂控制与反馈、ZMQ 服务 |
| `third-party/agilex-gello-software/` | GELLO/Dynamixel 读取与设备校准 |
| `third-party/camera-realsense-d455f/` | RGB-D、时钟映射、深度单位与标定；导入名 `camera_realsense` |
| `third-party/lerobot-converter/` | legacy raw 校验、时间匹配和 LeRobot 输出 |
| `third-party/agilex-adapters/` | LeRobot Robot/Teleoperator 协议与 owner-private Unix IPC |

CAN 访问保持在 SDK；相机采集保持在相机库；转换逻辑保持在 converter。新采集应用不调用旧 `run_workflow`，复用低层 helper 并共享硬件锁。网页编码与点云计算不能阻塞控制/录制，私有 IPC 有命令看门狗，不通过 TCP 暴露 pickle。

## 配置与数据契约

- `config/default.toml` 是单一应用配置，不另建第二份应用默认配置。`[collection].hardware_config` 为空时复用本文件硬件表；显式实验文件保留原加载语义。
- controller 忽略 `[collection]`；浏览器读取该表及硬件表。子模块通过公开 CLI/API 显式接收参数，不隐式读取父 TOML；当前 camera/converter 有自己的打包默认 TOML，其他模块以当前接口为准。
- GELLO 标定通过 `DynamixelRobotConfig` 传入，不修改库的全局端口表。`joint_offsets`/`joint_signs` 与 `follower_signs` 是不同映射。
- 全部解释器使用 uv 管理的 Python 3.12，各项目有独立 frozen lock 和 `.venv`。根/GELLO 为 `>=3.12,<3.13`。
- GELLO 导入 `agilex_gello_software`，固定 PyPI DynamixelSDK 4.0.5，无旧 `gello.*` 命名空间或必需嵌套 SDK。
- adapters 的 `app` extra 使用 LeRobot 0.6.0 和 LeLab `9b5afaee33baa1d773e499937564f3831d25de22`；converter 使用 LeRobot 0.6.1。保留嵌套 extras 闭包及 CPU torch/torchvision 索引，修改后做真实数据集回读。
- `data/raw/` 是不可变输入，`data/lerobot/` 可重建；浏览器 raw/app 与 legacy raw v1/v2 不混用转换命令。保留原生 Z16、深度尺度、最终 profile 标定与单调时钟来源。
- 浏览器相机 `auto` 优先 640×360@90，再按实测回退；legacy 显式 profile 不变。不能在录制中切换 profile。点云只接受零畸变 rectified 内参，不做 RGB 纹理投影。
- 预览 generation/sequence 防止跨会话缓存；两 viewer 上限需在 accept 前占位。FPS 区分预览、采样、捕获；默认 30 FPS 数据集不等于相机 90 FPS。
- 浏览器 JS 定位容差配置为 1.1°；CLI `move_js` 默认仍为 1.0°。不把浏览器的容差声明套用到 CLI，详见 [决策](docs/decisions/0001-baseline-and-validation.md)。

## 范围与非目标

P1 新增独立契约包与无硬件 HAL 仿真，根版本为 0.2.2 待测快照。原有真机控制、标定、数据格式和五个子模块提交不变；runtime 与录制迁移留到后续阶段。训练、推理、SO101 标定与 Hub 删除不属于当前应用能力；`/jobs` 的 404 是预期行为。

## 术语

| 中文 | 英文 / 标识 | 含义 |
| --- | --- | --- |
| 主手 / 从臂 | leader / follower | GELLO 输入端 / PiPER-X 执行端 |
| 分步定位 | JS positioning | 现有 SDK JS 服务的小步命令与反馈验收 |
| 原始深度 | Z16 | 原生 uint16 测距，乘设备深度尺度得到米 |
| 回合 | episode | 一段保存或丢弃的采样 |
| 采集会话 | session | 生命周期、配置、多个 episode 的容器 |
| 末端受力 | wrench | 三维力与三维力矩；P1 仅有假设备输出，真实传感器尚未接入 |

## 事实来源与待确认

- 约定来源：[HABITS.md](../HABITS.md)，项目路由：[AGENTS.md](../AGENTS.md)。
- 实现来源：根 `src/`、`config/default.toml`、`pyproject.toml`、`.gitmodules` 及固定子模块提交。
- 用户资料：[中文入口](../README.zh-CN.md)、[中文文档](../docs/zh/index.md)、[英文文档](../docs/en/index.md)。
- 既有结果来自原 `CLAUDE.md`、会话实际工具输出和本地忽略的测试报告；证据等级、路径与限制记录在 testing，不以迁移文档等同重新执行。
- 历史调查：[历史复盘](docs/reviews/history-2026-10.md)。外部研究来自用户指定的 `~/lab/demo/` 资料摘要，本轮不将其当作重新检索的最新研究结论。
- 待确认：Windows 实际 RDP 登录、图形会话预览、GELLO 夹爪完整端点、当前真机运动验收、持续吞吐和时序；力估计 Phase 0 的单位、接口、频率及标定参数。

- 项目级许可证待确认：根 LICENSE 当前为未选定状态说明，不能擅自替换成 MIT 或其他许可。

## 2026-11-08 规范与仓库更新

远程主仓为 `git@github.com:KnightOrNot/agilex.git`，Python 发行名和 CLI 不因仓库重命名改变。当前元数据版本 0.2.1。新版 HABITS 的分支与确认门槛见 [git.md](git.md)，取代 2026-11-05 的长期 dev 删除约定。既有数据/硬件待办保留，新增技能入口见 [SKILLS](../SKILLS.md)。
