# 真实 HAL 开发与验收（P3）

[English](../en/hardware-hal.md) | 简体中文

P3 为既有 PiPER-X、GELLO 和 RealSense 驱动增加隔离 HAL 服务。软件测试使用 fake 后端与真实私有 IPC；**真机验收尚未完成**。旧 `agilex-controller` 和浏览器入口保留原路径。本页的运行命令连接真实设备，只在实验机完成主机预检、操作员在场并确认授权后运行；加载配置和 `--help` 不访问硬件。

## 独立设备环境

从仓库根目录执行安装。`hal` extra 只增加 contract/msgpack 等协议依赖，保留各自 frozen lock；`--inexact` 保留原来已装的可选包。包装模块暂随根 wheel 分发，设备环境使用 `--no-deps` 安装根应用，以免拉入其他设备依赖；根 runtime 不导入任何设备库。

```bash
uv sync --frozen
uv sync --project third-party/agilex-sdk-python --frozen --extra hal --inexact
uv sync --project third-party/agilex-gello-software --frozen --extra hal --inexact
uv sync --project third-party/camera-realsense-d455f --frozen --extra hal --inexact
uv pip install --python third-party/agilex-sdk-python/.venv/bin/python --no-deps -e .
uv pip install --python third-party/agilex-gello-software/.venv/bin/python --no-deps -e .
uv pip install --python third-party/camera-realsense-d455f/.venv/bin/python --no-deps -e .
```

随后直接使用各设备 `.venv/bin/python` 执行 HAL。若重新精确同步设备环境移除了根应用，请重新执行对应的 `uv pip install --no-deps -e .`。这是 P7 包拆分前的分发安排，不代表三个 HAL 已发布成独立 PyPI 包。此开发版需主仓及相关子模块内容一致，不能把旧 gitlink 与新根源码混用。

```bash
third-party/agilex-sdk-python/.venv/bin/python -m agx_hal_piperx --help
third-party/agilex-gello-software/.venv/bin/python -m agx_hal_gello --help
third-party/camera-realsense-d455f/.venv/bin/python -m agx_hal_realsense --help
```

## 部署与准备副作用

复制并核对 [示例配置](../../config/runtime-hardware.example.toml)。`[[devices]]` 的 `backend` 为 `sim`、`gello`、`piperx` 或 `realsense`，`kind` 仍表达 leader/follower/camera/wrench 角色；未知或不兼容设置在启动前拒绝。设备 `python` 相对配置文件目录解析，现有 `endpoint` 必须是绝对路径，连接已有 HAL 时不启动也不结束它。

替换 GELLO 稳定端口、相机序列号，并从已验证配置复制校准与映射；示例数值不适用于任意主手。GELLO 编码器 offset/sign 与 runtime 的 follower 映射不同，HAL 不重复做 follower 映射。GELLO 的 `hz` 应保持原控制调用频率，默认 50 Hz；平滑按 act 调用次数演进，不应通过提高查询频率改变它。

| 阶段 | PiPER-X | GELLO | RealSense |
| --- | --- | --- | --- |
| DISCOVER / hello | 连接 CAN 并启动 SDK 反馈线程，不写运动参数或使能 | 独立 PING 探针，不写舵机寄存器 | 枚举指定相机，不配置或开流 |
| PREPARE | 标记准备，不使能 | 原库初始化，关闭主手扭矩并保留 offset 展开/平滑 | 原库配置、开流、预热与时钟资格检查，记录最终 profile |
| AUTHORIZE | 确认后写运动限值并使能 | 无从臂动作 | 无从臂动作 |
| 停止/故障 | 先撤权、清空待执行目标，再按显式退出策略处理 | 关闭串口 | 关闭流并恢复原库记录的设置 |

准备不是严格只读。HAL 的状态/metadata 查询不额外调用 GELLO act；采样只由 HAL 节拍驱动。SDK 的不可取消在途调用可能仍返回，独立 watchdog 会阻止迟到结果重新恢复权限，但不能宣称已发送的硬件目标被撤回。

## 运行与控制策略

先按项目真机手册完成只读、准备和无相机最小运动，再运行采集。真实 PiPER-X 跟随要求在终端查看 `hardware_motion_target` 后输入 `yes`，拒绝 `--confirm yes`、管道输入与 `serve` 的无人值守跟随。纯采集无需运动确认。

```bash
cp config/runtime-hardware.example.toml config/runtime-hardware.local.toml
uv run --frozen agx-runtime run --config config/runtime-hardware.local.toml --seconds 10
uv run --frozen agx-runtime run --config config/runtime-hardware.local.toml --mode sampled --seconds 10
```

示例显式使用 `piperx_return_zero`：确认后先小步回零、再对齐。退出先撤销原租约；同一会话只有在状态有效、反馈新鲜、六轴仍使能且通过限位检查时才可取得专用权限尝试小步回零。该路径不写运动限值、不重新使能，也不自动失能。新 PiPER-X 部署默认 `stop_targets`。到位判据沿用已确认的 1.5°，不补做专门容差实验。

示例为耗时准备保留 30 秒 startup/lease 预算，ACTIVE 命令与确认看门狗仍为 0.25 秒。驱动长调用不持有权限状态锁，HAL 独立线程检测期限；管理请求仍各自有界，不能用状态查询续期有效控制命令。异常反馈/必需流丢失/超差保留报错停止。

## 数据和证据边界

PiPER-X 承接 SDK 的实际反馈时间；旧缓存保留年龄与来源。缺失夹爪反馈只保留旧实测缓存；从未取得实测时标为 unknown 或 command_filled 且无效，不冒充新鲜反馈。SDK 墙钟到本机单调时钟的桥接在时钟跳变时拒绝继续。

GELLO 输出原 Agent.act 的关节序列（origin=estimated）和换算为米的夹爪；读取源时间暂引用固定版本原库的私有字段，P7/升级库时需复核。跨后台更新的读取采用较旧时间加不确定度。

相机保留原始 RGB8/Z16、depth scale、独立采样/接收时间及不确定度；可选 `CameraFrameInfo` 保存 SDK 时间/domain/frame number/clock offset 和标定摘要引用。raw manifest 的 `hal_metadata` 保存最终 profile 和标定，检查器重新核对标定摘要、图像尺寸及时间映射。无该可选字段的 P2 raw 仍可回读，无来源字段的旧帧线格式保持不变；要接收新来源字段，消费者须同步升级契约。

检查/回放命令沿用 [runtime 仿真指南](runtime-simulation.md)。短时 fake 数据通过不证明 CAN/USB 稳定性、多相机 90 FPS 吞吐或 PiPER-X 断令后的硬件动作。P3 最小运动与 P0 调用频率对比、P4 真机录制/吞吐与迁移、相关断令故障注入仍须按阶段验收；断令行为保持 `unverified`，不能据软件停止推定硬件静止。
