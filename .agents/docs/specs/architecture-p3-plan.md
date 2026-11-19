# P3 真实 HAL 包装的软件实施计划

> **For agentic workers:** Use superpowers:executing-plans。用户已明确要求 P2 无需追加真机实验时直接实施 P3；沿用 inline 执行，不再次请求设计/计划批准。项目提交门槛优先，不创建任何 commit/push。

**Goal:** 在既有驱动上实现 PiPER-X、GELLO、RealSense HAL 与 runtime 部署支持，完成无硬件契约/生命周期/回放验证并提供异机验收手册；真实验收保持待办。

**Architecture:** 根新增 `agx_hal` 共用服务、权限与边界实现及三个 `agx_hal_*` 驱动包装模块，仿真兼容入口复用共用层。runtime 只用配置/描述/IPC 启动设备解释器，不导入驱动。HAL 在目标设备环境执行，暂随根 wheel 安装以免 P7 前重排仓库；既有 SDK/GELLO/camera 公共 API 保留。

**Tech Stack:** Python 3.12、agilex_contract、pyzmq/msgpack；设备进程使用既有 numpy、pyAgxArm、DynamixelSDK、pyrealsense2，runtime 不新增硬件依赖。

**Spec:** [架构基线](architecture-v3.3.md) §4～7、§9、§12、§13/P3；[ADR 0005](../decisions/0005-position-tolerance-baseline.md)。

## Global Constraints

- P0 COMPLETE，P2 软件验收 250 passed；本轮不访问 CAN/串口/USB、不开流、不使能、不运动。fake 后端只可测试注入，生产入口禁止隐式 fake fallback。
- 保留 P2 未提交工作、P0 冻结证据和 GELLO 预存三项排版变更。root 工作分支 dev-architecture-p3；SDK 如需新增反馈字段单独工作分支，无 gitlink 更新。
- 不切换旧 CLI/Web；root 待测元数据按未提交候选统一维护，提交/分发待单独授权。
- DISCOVER 严格只读。PiPER-X connect 与只读状态和 authorize 后运动限值/enable 分开；GELLO 扭矩关闭和相机配置/开流声明为 PREPARE 副作用；授权、租约、命令期限不得被耗时驱动阻塞。
- 用独立 watchdog 检测无后续命令、租约失效及驱动阻塞。失权后作废 pending，任何迟到 prepare/authorize/apply 不得恢复 ACTIVE；不可取消的在途 SDK 调用及硬件断令行为仍不作保证。
- 保存反馈原始时间/缓存年龄与来源；未知或命令补值不能冒充新鲜实测。相机保留原生 RGB8/Z16、时间映射、不确定度及最终标定。GELLO act 不按查询次数增加调用，保留原库平滑与初始化。
- 1.5° 到位基线不变；PiPER-X 兼容正常/异常回零仅在新权限、新鲜有效反馈/状态/限位保护下尝试，不自动失能；硬件断令仍 unverified。
- PiPER-X 故障注入依赖断令行为证据；该未知不阻塞本轮软件包装，也不能用仿真把 P3 真机验收标为完成。

## Review Focus

- 驱动 prepare/authorize/read/apply 阻塞或迟到时，watchdog 是否独立撤权；旧租约、旧命令和迟到结果不能恢复新 owner。
- hello/prepare 的副作用边界、初始化失败与退出是否清理资源；SDK close 不隐式失能，GELLO 不掉进 fake。
- 反馈时间未变、墙钟跳变、缺夹爪反馈、命令补值、相机重启/重复帧是否正确标注并拒绝不安全控制。
- 实际相机 profile/原生字节/标定进入 raw，runtime 无设备导入，独立解释器和已有 HAL 的归属、参数与错误来源清楚。
- PiPER-X 回零/对齐顺序、GELLO 包装前后完整 act 序列与调用数、确认前无从臂写操作由 fake/IPC 实测，不能仅检查 mock 调用。

### Task 1: 共用 HAL 服务与独立权限看门狗

**Files:** 新建 src/agx_hal/{__init__,control,server,streams}.py；修改 src/agx_sim/{control,server,devices}.py；新建 tests/test_hal_services.py。
**Interfaces:** ControlGate(device, deadlines) 支持 discover/prepare/authorize/apply/revoke/close hooks；HalServer(device,directory,**deadlines) 不依赖 agx_sim；StreamPublisher 维护 seq/epoch/缓存/episode 边界，可用于原生数据生产端。管理 metadata RPC 返回有界描述元数据。

- [x] RED：真实私有 IPC、无命令/租约失效、驱动调用阻塞、授权后才执行目标、迟到授权不能恢复、边界/epoch/cache 语义；旧 P1/P2 契约继续覆盖。
- [x] GREEN：提取通用实现，设备 I/O 与短时权限状态分离；独立 watchdog，无文件/驱动 I/O 权限锁；所有子进程正常/失败关闭有界。
- [x] Verify：uv run --frozen pytest tests/test_hal_services.py tests/test_hal_control.py tests/test_hal_ipc.py tests/test_hal_loop.py tests/test_runtime_boundaries.py -q；Expected: PASS。

### Task 2: PiPER-X 反馈与授权包装

**Files:** src/agx_hal_piperx/{__init__,__main__,device}.py；SDK driver 公共反馈字段；tests/test_hal_piperx.py；SDK 相关测试。
**Interfaces:** PiperXDevice(settings, driver_factory=None)，严格发现、prepare、authorize/authorize_cleanup、samples、apply、revoke/close。接用 PiperXDriver，不调用 GelloPiperXRobot.start。反馈桥保留关节/夹爪时间；SDK 兼容增加时间字段、写入前权限检查和只读运动就绪检查，保留既有运动校验。

- [x] RED：discover/prepare 无使能或运动参数写入；authorize 顺序/失败；缓存不刷新原时间、无反馈/墙钟跳变无效、gripper measured/cached/command_filled；每次目标仍通过真实 SDK 驱动的状态/跨度/使能保护；close 不失能。
- [x] GREEN：实现包装、最小 SDK 时间元数据补齐及源代码副作用审计记录；描述 disconnect_behavior=unverified，显式 piperx 退出策略。
- [x] Verify：uv run --frozen pytest tests/test_hal_piperx.py -q，及 SDK 环境现有 driver/follower/reader 测试；Expected: PASS。

### Task 3: GELLO 与 RealSense 包装

**Files:** src/agx_hal_gello/{__init__,__main__,device}.py；src/agx_hal_realsense/{__init__,__main__,device}.py；tests/test_hal_gello.py、tests/test_hal_realsense.py。
**Interfaces:** GelloDevice(settings,agent_factory=None,probe=None)，RealSenseDevice(settings,stream_factory=None,probe=None)。生产 factory 延迟导入；所有采样进入 StreamPublisher。保留实际驱动初始化，测试可注入 fake。

- [x] RED：GELLO hello 仅 PING/READ、prepare 才写扭矩关闭、初始化/异常清理、校准/完整平滑序列与原 Agent.act 同输入输出/同次数；多次状态查询不额外采样。
- [x] RED：相机 hello 不开流，prepare 复用 ColorStream profile/预热；独立 RGB/Z16 时间和字节、scale/标定、未知时钟/重复/重启、关闭恢复配置。
- [x] GREEN：只包装既有库，不提取 GELLO，不引入预览/编码/录制到 HAL，不替换设备时间为发布时间。
- [x] Verify：uv run --frozen pytest tests/test_hal_gello.py tests/test_hal_realsense.py -q；Expected: PASS；相机原有 offline 测试保持通过。

### Task 4: 部署配置与 runtime 真实 HAL 接入

**Files:** agx_hal/config.py 与入口参数；src/agx_runtime/{config,supervisor,session}.py；config/runtime-hardware.example.toml；tests/test_runtime_hardware.py。
**Interfaces:** DeviceConfig 增加 backend 与严格 settings（sim/gello/piperx/realsense）；解释器显式配置并启动对应 -m 模块，已有 endpoint 不启动/kill。metadata 保留到 episode。PiPER-X 配置显式回零策略；sim 行为不变。

- [x] RED：未知设置/不兼容 backend/映射拒绝；runtime 新进程导入不含设备库；真实 IPC fake 驱动组合授权前无运动、回零→对齐顺序、失联/停止/退出策略、两种 raw 回读及实际 metadata 通过。
- [x] GREEN：保持驱动在自己解释器内，prepare 后复核最终描述与元数据；CAN 配置仍在主机预检，不由握手修改。
- [x] Verify：uv run --frozen pytest tests/test_runtime_hardware.py tests/test_runtime_session.py tests/test_runtime_service.py -q；Expected: PASS。

### Task 5: 文档、分发准备与完整验证

**Files:** 双语 hardware HAL 指南/参考/导航、README、CHANGELOG、pyproject/uv.lock；P3 异机验收手册、阶段与评审记录。

- [x] 实际设备环境 nodeps 安装说明和独立解释器 smoke/import/help 检查；不运行任何设备命令；不初始化更多仓库或升级原依赖。
- [x] 提供 P3 真机手册：先只读/准备副作用确认，再操作员在场最小运动；1.5° 不补容差试验；断令证据和故障注入 gate 明确，记录 P0 周期/act 序列对比。
- [x] make verify、lock/build、wheel checkout 外导入与 fake IPC 验证，必要子模块测试；Expected: 软件 PASS，硬件 NOT_RUN。
- [ ] 独立评审已收到的发现均已处理并回归，详见 [评审记录](../reviews/architecture-p3-review-20261119.md)；未收到独立评审最终汇总。
