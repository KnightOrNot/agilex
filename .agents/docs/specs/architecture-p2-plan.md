# P2 统一 runtime 与仿真采集实施计划

> **For agentic workers:** Use superpowers:executing-plans。用户已授权实施 P2；沿用当前会话直接实现，任务间不重复请求批准。项目禁止未经用户验收提交的约束优先。

**Goal:** 交付只接仿真 HAL 的统一 runtime，支持遥操作及纯传感器会话、full/sampled 录制、raw v3 检查和确定性回放、可配置期限及独立故障处置。

**Architecture:** 保留旧 CLI/Web 与六个子模块。根新增 agx_runtime；共用 IPC 工具移至 agx_transport，agx_sim.transport 保留兼容导出。运行循环拥有控制/接收 socket；管理、录制边界与磁盘工作隔离，控制线程只入队，episode 唯一提交者负责完成记录。生产端提供有界的按时间边界计数，支持发现尾部丢帧。

**Tech Stack:** Python 3.12、stdlib、agilex_contract、pyzmq/msgpack、pytest、uv；不引入硬件或 LeRobot 依赖到 runtime 导入链。

**Spec:** [架构基线](architecture-v3.3.md) §5～9、§12、§13/P2。

## Global Constraints

- P0 已完成并于 2026-11-17 验收；本次不访问 CAN、串口、物理相机，不宣称真机、性能或断令行为验收通过。
- 保留未提交 P0 手册/索引/阶段记录；工作在 dev-architecture-p2，不 commit、push、合并，不更新 gitlink。
- 不切换现有 CLI/Web；按用户 2026-11-17 的后续指令，三个入口的默认到位容差统一为 1.5°，不追加容差真机实验；P0 的 1.0°/1.1° 原始记录保留。见 ADR 0005。
- record.boundary_timeout_s=1.0、record.drain_timeout_s=5.0 为仿真默认，写入统一配置；以故障注入验证期限，不当作硬件吞吐证据。已据 P0 保留隔离线程/ZMQ，P4 再测新路径实际吞吐。
- raw v3 本轮只保证仿真采集/检查/回放；旧 raw 迁移、真机录制、LeRobot 导出、Web 切换属于 P4/P5/P6。
- 故障默认报错停止；optional 仅告警；新设备不得隐式继承回零。模拟设备可显式选择零位策略用于验证保护，实际硬件策略仍 unverified。
- 存储耗时、边界 RPC、排空不占用控制线程，不与撤权共用串行任务队列；固定 episode 级期限，不按流或重试续期。
- source/freshness、原生 RGB8/Z16、力的单位/坐标/参考点/零偏/标定、命令实际使用观测引用均保留。

## Review Focus

- 边界之前/之后的数据、首尾丢帧、epoch 重启、迟到样本不得混入别的 episode（Task 1/3/4）。
- 超时或失败后的写盘/边界回调不得成功提交，且不得阻塞撤权和 HAL 释放（Task 3/4）。
- 配置不能通过缺少 control_required 阶段、NaN/bool/负期限、未知流或错误映射绕过检查（Task 2）。
- IPC endpoint 的 owner、权限、符号链接、坏消息、进程归属及客户端看门狗需受验证（Task 1/5）。
- 检查/回放必须真正读取 raw、核对数量/字节/引用/标定，而非信任 complete.json 或相同生成器（Task 3/6）。

### Task 1: 共用 IPC 与生产端 episode 边界

**Files:** 新增 src/agx_transport/__init__.py；修改 src/agx_sim/{transport,devices,server}.py；tests/test_runtime_boundaries.py。

**Interfaces:** HalClient API 保持；增加 boundary_begin(episode_id,start_mono_ns)、boundary_end(episode_id,end_mono_ns)，带 session_id/lease。结果由 EpisodeBoundary 线格式组成，空流计数 0。生产端按原始产生时间计数，管理操作有界且不等待消费者。

- [x] RED：边界排除前后样本、重复 end 幂等、错误 owner/epoch/时间拒绝、尾部计数、客户端拒绝不私有端点。
- [x] GREEN：提取共用传输；仿真端有界历史与单个活动 episode 的计数；结束固定边界且不改变采样与控制权限。
- [x] Verify：pytest tests/test_runtime_boundaries.py tests/test_hal_control.py tests/test_hal_ipc.py tests/test_hal_loop.py；预期全部通过。

### Task 2: 分层配置、流监视与映射 Safety

**Files:** src/agx_runtime/{__init__,config,safety}.py；config/default.toml 与仿真配置；tests/test_runtime_safety.py。

**Interfaces:** load_config(path=None, overrides=None) -> RuntimeConfig；设备部署、每流 role/monitor_when、RecordingConfig、MotionConfig；StreamMonitor 接收 Sample、验证时钟/epoch/新鲜度并生成 required 故障或 optional 警告；JointMapping/Safety 通过描述验证名称/单位/限位、目标步长和反馈条件。

- [x] RED：非法期限、未知字段/流、控制检查阶段缺失；多维映射；缓存不刷新年龄；optional 警告；无效状态/陈旧反馈拒绝定位。
- [x] GREEN：单一默认来源；旧 [recording] 仅做显式迁移别名并给出告警，明确新 [record] 优先；sampled 拒绝多频率 wrench/无明确遥操作节拍组合。
- [x] Verify：pytest tests/test_runtime_safety.py；预期通过，旧配置测试保留通过。

### Task 3: 唯一提交录制器、raw v3 检查与回放

**Files:** src/agx_runtime/{recording,raw}.py；tests/test_runtime_recording.py。

**Interfaces:** Recorder.start(descriptors,policies,boundary_clients) -> Episode；offer(Sample)、selection(target_ns,refs)、command(Command,observations)、finish(end_ns)、fail(reason)、poll/status；inspect_episode(path)、replay_episode(path)。

- [x] RED：纯传感器/两相机+力的 full、机械臂+相机 sampled；计数分类/尾丢帧；RGB/Z16 原字节与力元数据回读；选择目标与样本引用；篡改/缺失拒绝。
- [x] RED：边界不响应、多流共享期限、写盘阻塞、队列满、迟到结果、失败隔离下一段；停止处理不等待保存。
- [x] GREEN：每个 episode 独立 .partial 目录，流 JSONL + 二进制原帧、command/selection 审计；记录 produced/received/written/skipped/transport_lost/write_failed。磁盘执行隔离，唯一提交者校验完成后最后原子发布 complete.json；失败只留 partial/失败证据。
- [x] Verify：pytest tests/test_runtime_recording.py；预期全部通过，期限不因设备增加而成倍增长。

### Task 4: Session、控制环与 HAL 监管

**Files:** src/agx_runtime/{supervisor,session}.py；tests/test_runtime_session.py。

**Interfaces:** Session(config)；prepare、confirm、record、save、discard、stop、status、preview；只通过已配置解释器启动 -m agx_sim，不 import 驱动；支持连接已有仿真 HAL，归属不同则不 kill。

- [x] RED：真实子进程纯传感器采集/检查/回放；非六轴跟随和反馈到位；确认前不运动；重复/错误状态拒绝；两种录制模式。
- [x] RED：HAL 退出、陈旧、runtime 停止发送、过期命令、确认超时、租约失效；边界/写盘阻塞同时触发故障仍及时停止/撤权；兼容相机在非录制 following 阶段失联也停止。
- [x] GREEN：统一生命周期、共享硬件锁、只归属自己的进程清理；非阻塞目标和实际使用样本审计，独立租约维护；故障主错误与清理错误分别报告，未保存 episode 不自动成功提交。
- [x] Verify：pytest tests/test_runtime_session.py；预期通过且无遗留子进程/套接字。

### Task 5: 命令服务与可运行入口

**Files:** src/agx_runtime/{service,__main__}.py；pyproject.toml；tests/test_runtime_service.py。

**Interfaces:** agx-runtime run/serve/request/check/replay；私有 IPC 命令/状态/预览，客户端会话与 heartbeat；真实设备描述或配置在 P2 明确拒绝。

- [x] RED：CLI 帮助/传感器 run；真实 IPC 命令顺序/确认/坏请求；owner/权限；客户端超时与正常停止；独立新 Python 进程导入 runtime 不加载硬件库。
- [x] GREEN：嵌入与守护使用同一 Session；signal 只发停止请求、不抢先杀 HAL；守护命令返回接受状态，不在 RPC 线程等待录制写盘。
- [x] Verify：pytest tests/test_runtime_service.py；预期通过。

### Task 6: 文档、集成与独立评审

**Files:** docs/en/runtime-simulation.md 与 docs/zh/runtime-simulation.md、导航、配置/CLI 参考；CHANGELOG、pyproject/uv.lock、ADR 0004、阶段记录与本计划。

- [x] 版本只升一次为 0.2.3 待测；uv 更新锁，不升级现有依赖；双语说明操作、raw、期限/故障、P0 已验收结论及 P3～P7 边界。
- [x] make verify、uv lock --check --offline、uv build、CLI 两种模式及纯传感器的独立进程验收；预期软件通过且真实 golden 不被访问。
- [x] 按 executing-plans 要求一次独立整体评审；重要问题补 RED→GREEN，回归完整验证。
- [x] 阶段记录证据、已知限制和验收矩阵；保留未提交，供用户验收。

## 完成记录（2026-11-18）

六项任务的 P2 仿真范围已完成，未提交。最终 `make verify` 为 250 passed / 66.91s；四组独立 CLI、lock/build 和 checkout 外 wheel 采集/检查通过。一次整体评审的五项 Important 已通过 RED→GREEN 修复；时序调查、管理通道优化、历史失败与限制见 [评审记录](../reviews/architecture-p2-review-20261118.md)。后续仍按 P3～P7 验收，不将 P0 或 P2 的完成扩展为硬件通过。
