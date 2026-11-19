# 统一 runtime 仿真（P2）

[English](../en/runtime-simulation.md) | 简体中文

本指南说明仿真 HAL 路径。P3 已增加[真实 HAL 包装](hardware-hal.md)，硬件验收仍待完成。现有真机 CLI 和浏览器仍使用原有路径。P0 真机测量已验收；真实 HAL 验收、旧 raw 迁移和 LeRobot 导出仍属于后续阶段；仿真通过不能证明 PiPER-X 断令后的硬件行为。

## 运行和检查

在本开发分支检出目录执行 `make sync` 后，可运行纯传感器会话（两相机加六维力传感器）或仿真跟随：

```bash
uv run --frozen agx-runtime run --config config/runtime-sensors.toml --seconds 1
uv run --frozen agx-runtime run --config config/runtime-sim.toml --seconds 1 --confirm yes
uv run --frozen agx-runtime run --config config/runtime-sim.toml --mode sampled --seconds 1 --confirm yes
uv run --frozen agx-runtime run --config config/runtime-extended.toml --seconds 1 --confirm yes
```

最后一个例子包含主手、从手、两相机和六维力传感器。不传 `--confirm yes` 时，跟随会显示目标并要求输入 `yes`；纯传感器会话无需运动确认。输出为 JSON 会话报告，包含 `data/raw-v3` 下的 episode 路径。`--data-root` 和 `--lock-path` 可覆盖配置；默认锁与现有 controller 共用。

```bash
uv run --frozen agx-runtime check data/raw-v3/EPISODE_ID
uv run --frozen agx-runtime replay data/raw-v3/EPISODE_ID
uv run --frozen agx-runtime replay data/raw-v3/EPISODE_ID --commands
```

将 `EPISODE_ID` 替换为报告中的目录名。检查会验证文件哈希、原生图像长度、边界、行数和选择引用。命令回放根据每条命令实际使用的观测重算映射与步长限制，不发送运动。CLI 样本回放输出元数据和字节数；Python 的 `replay_episode()` 返回含原始 RGB8/Z16 字节的样本。

## 配置与生命周期

统一入口为 `agx_runtime.config.load_config()`，依次加载默认值、TOML 文件和显式覆盖。安装包没有源码配置文件时使用与其一致的模型默认值。每项 `[[devices]]` 声明仿真 `kind`、ID，可选 `axes`、`hz`、解释器 `python`，以及已有服务的绝对目录 `endpoint`。仅终止自己拉起的进程；描述符必须匹配所配置的仿真设备与准备动作。

每条流都必须声明 `role` 和 `monitor_when`。控制流必须为 `control_required`；录制流通常为 `record_required`；`optional` 故障只告警；sampled 选择排除不可用样本，epoch 改变则隔离该可选流直到本段结束，manifest 保留告警。两个必需角色发生故障均停止会话。示例相机在 `READY`、`ALIGN`、`FOLLOWING`、`RECORDING` 阶段受监视，包含未录制的跟随阶段。新设备不继承回零策略；默认 `stop_simulated_targets`，从臂显式选择 `simulated_zero` 后才会用新的权限回零，每步检查反馈有效性、新鲜度和限位。这两种策略都不能说明真实硬件行为。

| 配置项 | 默认值 | 含义 |
| --- | --- | --- |
| `record.mode` | `full` | 记录所有流，可限制相机保存频率 |
| `record.dataset_fps` | `30` | sampled 选择频率，不高于控制频率 |
| `record.capture_fps_max` | `90.0` | full 模式 RGB/depth 上限，主动跳过单独计数 |
| `record.max_skew_ms` | `50.0` | 在线相机对时与 sampled 选择容差 |
| `record.queue_size` | `512` | 非阻塞写入队列，满时本段及会话失败 |
| `record.boundary_timeout_s` | `1.0` | 所有生产端共用一个边界确认期限 |
| `record.drain_timeout_s` | `5.0` | 剩余接收、写入、核对与发布共用一个期限 |
| `motion.position_tolerance_deg` | `1.5` | 对齐及显式仿真回零的每轴到位容差 |
| `runtime.watchdog_s` | `1.0` | 守护服务控制客户端的心跳期限 |

期限必须为有限正数。边界期限从保存固定结束时间开始；排空期限从边界确认结束开始。设备数量或部分进度不重置期限。1/5 秒仍是仿真默认值，P4 须测量新 raw 路径。P0 当前 profile 支持保留隔离写盘线程和 ZMQ 传帧；不代表多相机 90 FPS 吞吐通过，也不覆盖独立的 LeRobot 导出耗时。

`full` 支持纯传感器和多频率力数据；`sampled` 支持主手/从手/相机组合，并记录目标采样时间和选中样本引用，拒绝含力传感器或没有主手的配置。旧 `[recording].dataset_fps/queue_size` 会发出迁移告警，显式 `[record]` 优先。用户于 2026-11-17 将 CLI、Web 和 runtime 的到位基线统一为 1.5°，不再补做容差实验；P0 证据保留原 1.0°/1.1° 判据及实测残差。

## 嵌入与守护接口

`Session(config)` 提供 `prepare`、`confirm(True)`、`record`、`save`、`discard`、`stop`、`status`、`preview` 和 `wait`。调用确认状态转换已接受，完成状态通过查询获得。准备完成后才进入确认和授权。保存/丢弃只结束本段边界，期间继续跟随，`FINISHING` 结束后可以新建录制。丢弃保留 partial 审计目录。停止会中断未保存段，不等待磁盘再释放设备。结束后的 Session 不复用，需要新建。HAL 租约释放或失效会冻结活动段计数，已有外部 HAL 无需重启即可服务下一会话。

```bash
uv run --frozen agx-runtime serve --config config/runtime-sensors.toml --endpoint-dir /tmp/agx-runtime-api
```

自动化通过 `RuntimeClient(directory, client_id)` 调用：先 `acquire`、`prepare`，再以短于 `runtime.watchdog_s` 的间隔发送 `heartbeat`。查询 `status`，调用 `record`、`save`、`discard`、`stop` 或 `shutdown`；遥操作还需 `confirm(confirmed=True)`。`preview` 返回最新元数据及图像字节数。`status`/`preview` 不续心跳。目录必须由当前用户所有、权限 0700，socket 为 0600；不替换已有端点，不开放 TCP 监听。

```bash
uv run --frozen agx-runtime request --endpoint-dir /tmp/agx-runtime-api --client-id operator acquire
uv run --frozen agx-runtime request --endpoint-dir /tmp/agx-runtime-api --client-id operator status
uv run --frozen agx-runtime request --endpoint-dir /tmp/agx-runtime-api --client-id operator shutdown
```

这些单次命令用于查询和控制服务；自动化的活动会话必须持续发送心跳。

## Raw v3 与故障处理

每段从 `ID.partial` 开始。按流保存 JSONL，保留类型化消息头、时钟/来源/新鲜度与 epoch；图像保存原生二进制；力样本保留描述符中的单位，以及坐标系、参考点、零偏和标定 ID。manifest 分别记录产生、接收、写入、主动跳过、传输丢失、写入失败数量和缺失序号范围。`commands.jsonl` 保存控制实际使用的观测，可能早于录制开始；这是命令审计上下文，与边界内的流数据分开。

唯一提交者核对必需流数量、写入 `complete.json`，然后发布 episode 目录。sampled 完成至少需要一个覆盖所有必需流的有效选择组合，过短录制明确报错。检查/回放独立复核描述、策略、流统计、选择覆盖和时间偏差；失败、丢弃和 partial 段均拒绝。底层 I/O 可能在超时后继续，但不能将失败段改回成功。故障处理和撤权不等待写盘或边界请求；各 HAL 内还有独立命令/租约看门狗。主错误和清理错误分开报告。会话后续故障不影响已保存段的读取。

```bash
uv run --frozen pytest tests/test_runtime_boundaries.py tests/test_runtime_safety.py tests/test_runtime_recording.py tests/test_runtime_session.py tests/test_runtime_service.py tests/test_runtime_review.py
make verify
```

上述检查只用合成数据和本地 IPC，不访问串口、CAN 或物理相机，不代表硬件性能或运动验收通过。
