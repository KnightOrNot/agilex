# P1 契约与扩展仿真实施计划

> **For agentic workers:** Use superpowers:executing-plans. 按下列任务执行；项目禁止提交的约束优先于技能默认提交步骤。

**Goal:** 在不访问硬件、不切换旧入口的前提下，交付独立契约包与可经本地 IPC 操作的扩展仿真设备。

**Architecture:** `agilex-contract` 是 `third-party/agilex-contract` 下的独立本地 Git 仓库，纯类型/校验无硬件依赖；`src/agx_sim` 提供设备仿真与 ZMQ/msgpack 传输。父仓保留原五个 gitlink，新增仓库的首次提交、远端与正式 gitlink 依用户后续明确的 dev 异机分发授权完成，例外记录于 git.md。

**Tech Stack:** Python 3.12、dataclasses、msgpack、pyzmq、pytest、uv。

**Spec:** [架构基线](../../../ARCHITECTURE_v3.3.md)，重点 §5、§12、P1。

## Global Constraints

- 用户已授权开始架构实施与清理无用 dev 分支；只删除已合入 dev 且无独有提交的本地旧分支。
- 现有入口、五个子模块、共享硬件锁、运动容差与故障策略保持现状；P0 真机验收、P2 录制/runtime 另行推进。
- 不访问 CAN、串口或物理相机。实施阶段先保留未提交；用户后续明确授权先提交并推送 dev 供异机实验，版本仍标为待测，不声称硬件通过。
- 当前工作分支 `dev-architecture-p1` 已隔离 dev；沿用当前工作区，保留用户文档，不另建 worktree。
- 新契约仓库保持独立，按用户指定命名为 agilex-contract，Python 导入为 agilex_contract；子仓 dev 先推送后再发布父 gitlink，并验证 GitHub 新克隆。

## Review Focus

- 错误 schema、非有限数值、图像字节长度与维度不一致应拒绝，不影响下一次请求。
- 旧租约、重复序号、未来/过期命令不得刷新控制看门狗。
- 无命令到来时也能超时；租约恢复不得直接 ACTIVE；对齐有总期限及步骤间隔期限。
- 重发缓存保留采样时间，服务重启更换 epoch；不可混淆 measured 与 command_filled。
- 多相机与六维力数据经真实 IPC 往返，owner-private 端点、进程退出、权限阶段可验证。

### Task 1: 独立契约与数据校验

**Files:** `third-party/agilex-contract/{pyproject.toml,src/agilex_contract/*.py,tests/test_contract.py}`。
**Interfaces:** DeviceDescriptor/StreamSpec；SampleHeader 与 JointState/PoseState/ImageFrame/DepthFrame/WrenchSample；Command/Ack；EpisodeBoundary；基础类型 wire 转换与校验。

- [x] 写覆盖 Review Focus 中数据错误与无硬件依赖的行为测试并观察失败。
- [x] 实现最小类型/校验与 schema 版本拒绝；保留原生 RGB/Z16、时间字段、来源与新鲜度。
- [x] 运行契约测试与 Ruff。Expected: 全部通过；无 NumPy/硬件依赖。

### Task 2: 仿真设备与控制权限

**Files:** `src/agx_sim/{devices.py,control.py}`、`tests/test_hal_control.py`。
**Interfaces:** 纯仿真 leader/follower/camera/wrench；同一控制权限对象处理 acquire/prepare/authorize/align/activate/command/release；poll 驱动本地看门狗。

- [x] 写权限顺序、旧会话、重复命令、命令过期、看门狗与租约失效、对齐期限测试，观察失败。
- [x] 实现有界租约、最新目标覆盖、提交前二次过期检查、故障撤权与队列清空；不会因 query/rejected 命令延长期限。
- [x] 验证两个相机、力传感器、非六轴 follower 的描述与样本；缓存和重启语义。Expected: 全部通过。

### Task 3: 本地 IPC 仿真服务与入口

**Files:** `src/agx_sim/{transport.py,server.py,__main__.py,__init__.py}`、`tests/test_hal_ipc.py`、`tests/test_hal_loop.py`、根配置/锁/Makefile。
**Interfaces:** 独立 REP 管理通道、PULL 连续命令、PUB 样本与确认；本机单调时钟，msgpack 元数据+图像独立字节帧；0600 socket、0700 会话目录。

- [x] 写真实子进程 IPC 测试，观察缺功能失败；包括无后续消息仍超时、坏消息后继续服务、epoch 重启与资源释放。
- [x] 实现定时轮询驱动的独立 HAL；管理通道不会等待录制/外部 I/O，连续命令有限批次处理并使用非阻塞确认流。
- [x] 提供无硬件 CLI 用于选择设备类型/ID；两相机与六维力以相同协议接入。Expected: IPC 测试通过。

### Task 4: 文档、集成与验证

**Files:** 双语仿真指南、CHANGELOG、ADR 0004、testing.md 与计划账本。

- [x] 文档记录安装、调用、权限步骤、数据时间语义与独立仓库未发布限制。
- [x] 运行根 make verify、新契约测试/Ruff、模拟命令帮助与分进程往返。Expected: 软件检查通过或准确列出环境限制。
- [x] 对本次未提交代码做一次独立评审，修复重要问题并回归受影响测试。
- [x] 更新当前阶段证据；保留 TESTING，不声明完成 P0/P2 或真机验收；后续提交遵循本次异机分发授权。
