# P3 HAL 真机验收与回传手册

状态：待实验机执行。P3 软件包装已实现，实际验证结果以 [当前测试记录](../stages/testing.md) 为准。此手册交给实验机 Codex；本机未访问硬件。任务只验收 P3，不自动实施 P4～P7、不升级标定、不补做容差实验。

## 0. 授权与冻结版本

- 在实验机用单独工作目录取得 GitHub `dev` 上的 0.2.4 候选；根提交以交接单提供的完整 SHA 为准。按父仓固定记录检出六个子模块（SDK/GELLO/camera/contract 候选 0.1.1）。不要用 `git submodule update --remote`，不要覆盖冻结的 P0 工作副本。
- 记录根及六个子模块实际 SHA、dirty diff 哈希、各 pyproject/lock 哈希、Python/uv、主机/内核、CAN/USB/串口身份。各环境按 [设备指南](../../../docs/zh/hardware-hal.md) frozen + hal extra 安装；保留原可选包，根包装模块以 no-deps 安装到各设备环境。
- 操作员必须明确允许本轮读设备、准备副作用、使能与最小运动；阶段授权分开记录。无人值守代理不自行运动。机械臂固定、空间清空、急停可用，不同时运行旧 CLI/Web，不杀已有服务或删除锁。
- P0 COMPLETE、B4 黄金数据及 B6 真实输入保持只读。用户已确定 1.5° 每轴到位基线，不继续专门容差实验；记录实际残差，不修改反馈或自动扣 offset。
- 证据保存在新建 `data/p3/<UTC运行ID>/`；原 raw 不覆盖，失败段保留 partial，不改 complete 记录制造通过。

## 1. 无设备预检（先做）

1. 确认源码/子模块版本一致、包可导入；三个设备解释器运行 `-m agx_hal_<设备> --help` 不应访问设备。检查 `make verify`、lock/build 的实际结果与 skips。
2. 从 `config/runtime-hardware.example.toml` 复制为本地配置，替换稳定 GELLO 端口与相机序列号。校准与 follower 映射从 P0 已验证配置逐项复制，不按示例猜测。
3. CAN 配置属于主机层；沿用已批准的 bitrate/接口，不由 HAL hello 配置。不因 ping/status 自动使能或写运动限值。
4. 创建无相机最小配置（仅 leader/arm 与对应四条流策略），再创建 RGB-D 配置。解释器路径相对配置文件目录解析，确认均指向对应 .venv。
5. 记录硬件锁/端口归属和已有进程。占用原因不明时停止，不尝试接管或强杀。

## 2. DISCOVER 严格只读验收

只在操作员允许只读检查后执行。使用 `Supervisor.launch()` 拉起已配置 HAL，再逐设备 `rpc(name, "hello")` 和 `rpc(name, "status")`，**不要调用 `Supervisor.discover()`**，它会进入 PREPARE。在 finally 中关闭只归本轮创建的 HAL。

验收并记录：

- PiPER-X connect/反馈线程能建立；hello/status 不使能、不写运动参数、不改控制模式、不发送运动目标。用可取得的 CAN 审计/日志和启动前后状态核对，不把进程存在当作只读证据。
- GELLO PING 只读探针可确定七个舵机身份，探针后串口关闭；不调用原 `DynamixelDriver` 初始化来冒充只读，它会写扭矩关闭。
- 相机只枚举指定设备；没有 stream start 或 sensor option 写入。
- 描述与设备 ID、通道、rad/m、限位、prepare_effects、exit_policy 一致；disconnect_behavior 对实际硬件仍为 unverified。

若启动链出现未声明写入，终止此阶段并回报；不继续授权运动。

## 3. PREPARE 及确认前验收

在操作员明确接受准备副作用后创建 Session 并 prepare，等 CONFIRM/READY；先不 confirm。

- GELLO 原库关闭扭矩并按原校准初始化；没有 fake fallback。关节/夹爪流可读，纯查询状态和 metadata 不增加 act 调用。
- PiPER-X 未被本轮使能或写运动限值、未收到运动目标。已有外部使能状态如实记录，不能把“启动前已使能”说成本轮写入。
- 相机单独配置下 PREPARE 会配置、开流、预热；记录实际 profile、global/system clock、原生 RGB8/Z16、depth scale、标定摘要与关闭后的选项恢复。未知 hardware_clock 不能冒充 host_monotonic。
- 缓存消息保持原采样时间，反馈过期会被拒绝；夹爪缺失/unknown/command_filled 不得当作新鲜实测控制。记录错误，不补假数据绕过启动检查。
- 软件会独立撤权，实际长调用/强杀后的硬件行为未获证明。准备需长时间时按实际预算复核 startup/lease，不自动放宽 ACTIVE command/ack 期限。

关闭未确认会话应无从臂运动。异常原因、cleanup_errors 和资源释放都记录。

## 4. 无相机最小运动

只有上述阶段通过、操作员在场且明确允许使能/运动后执行。真实跟随要求交互终端，`--confirm yes`、管道输入和 `serve` 的无人值守跟随会被拒绝。

1. 使用最小配置启动 `agx-runtime run`，查看当前目标，再由操作员输入 yes。
2. 验证确认后才写运动限值/使能；显式 `piperx_return_zero` 顺序为小步回零→对齐→跟随。所有目标仍经过 SDK 的 CAN/反馈/状态/实际使能/限位/跨度检查。
3. 小范围平滑操作主手和夹爪，约 10～20 秒；不要接触装配或运动到限位。记录 raw 命令、实际观测引用、到位残差、命令确认与状态。
4. 正常停止先撤销原权限、作废 pending。只有原授权会话、有效新鲜反馈和六轴仍使能时，才尝试小步回零；专用权限不写限值、不重新使能或自动失能。任一校验失败应拒绝回零，不为“完成清理”重试运动或绕过保护。
5. 操作员确认实际运动与退出结果。检查无本轮遗留 HAL/套接字，外部 HAL 未被 kill，锁已释放，CAN 错误/bus-off/丢弃计数变化如实记录。

若超差或必需流故障，保持报错停止，不修改角色、偏差、反馈或自动继续控制来制造通过。记录真实硬件最终位置，不能用软件阶段 IDLE/FAILED 代替硬件观察。

## 5. P0 行为对比与无故障 RGB-D

- 软件已用冻结 B6 数值夹具比较新包装的全部 1,996 次 Agent.act（含对齐观察），在 atol=1e-12/rtol=0 下通过；不替代现场的 act 调用频率/串口和 IPC 时序对比。
- 现场记录实际 act/capture/control 频率、周期 p50/p95/p99/max、超期、队列/缺口。可从 raw command.issued_mono_ns 和样本计数分析相应节拍，但它不等于 P0 原生 command-start 或硬件采样延迟，指标口径必须写清。
- 源初始化、平滑、映射、夹爪归一化与 P0 一致；不因提高状态/预览频率增加 act。若频率/输出不一致，保留序列、初始条件和完整配置用于诊断，不直接修改平滑系数。
- 无相机路径通过后再启用相机做一段约 10 秒的无故障采集，检查 profile/字节/时间/标定及清理。P3 只验收包装与接入；两种模式、真实 full 吞吐/抖动不劣于 P0、capture_fps_max 和 raw 迁移属于 P4，不据短段宣布 P4 完成。
- 用 `agx-runtime check EPISODE`、`replay EPISODE`、`replay EPISODE --commands` 实际读回；抽查 RGB/Z16 字节、单位、时间来源及原观测重算目标，不仅检查 complete 文件存在。

## 6. 断令行为与故障注入 gate

**PiPER-X 断令仍为 unverified 时，不执行依赖未知断令行为的杀进程/断 CAN/拔线/断令真机故障注入。**P2/P3 fake 注入不能当作真机动作证据。

查清证据需要单独经批准的方案、设备/固件/模式/SDK 版本和可观察结果；明确软件保证（撤权/停止转发/清空 pending）与硬件结果（保持、减速、继续追踪等）。没有证据就保持 NOT_RUN/UNVERIFIED，不猜测“保持”或“立即静止”。这个 gate 不阻塞已经可独立验证的只读/准备/正常最小运动。

## 7. 返回的报告

输出 `P3_REPORT.md`、`artifacts.json`（路径/大小/SHA256）及操作员验收回执，并包含：

- 根/子模块/环境/配置与源哈希、实际设备身份/固件、测试时间与权限范围。
- 上述各阶段 PASS/FAIL/NOT_RUN、原始日志和实际错误；软件/只读/开流/使能/运动分别标注。
- 确认前副作用、回零/对齐顺序、实际残差、act/control/profile/时间审计与 P0 对比口径；原始 raw/命令回放结果。
- 正常和异常历史均保留；清理错误与主错误分开，原数据不改写。
- 断令状态及证据或 gate，P4～P7 未验收项。未拿到操作员明确结论时不把真机 P3 标 COMPLETE。
- 实验机仅提交报告与证据，不自行 commit/push/merge、改 gitlink、删除基线或发布数据。
