# HAL 契约与无硬件仿真（P1）

[English](../en/hal-simulation.md) | 简体中文

P1 提供独立 `agilex-contract` 包，以及 Leader、Follower、RGB-D 相机、六维力传感器的合成 HAL。各设备运行在独立进程，通过本机 IPC 使用同一契约通信。现有 CLI 与浏览器仍使用原实现；本阶段不提供新 runtime 的录制、回放或真机服务。

## 工作副本与安装

`third-party/agilex-contract` 是独立 Git 子模块，父仓固定其提交，并通过 uv 本地路径引用。获取待测版本时必须初始化所有子模块；原五个子模块保持原提交。根版本 0.2.2 与契约版本 0.1.0 是 dev 待测快照，真机验收仍待完成。

在另一台计算机首次获取待测版：

```bash
git clone --branch dev --recurse-submodules git@github.com:KnightOrNot/agilex.git
cd agilex
make sync
uv run --frozen agx-sim --help
make verify
```

已有工作副本先保存本地修改，再更新：

```bash
git switch dev
git pull --ff-only origin dev
git submodule sync --recursive
git submodule update --init --recursive
make sync
```

以上只准备根环境和 P1 仿真。实验机运行已有真机 CLI/Web 前，还需按[安装指南](installation.md)同步 SDK、GELLO、相机、converter 和浏览器的独立环境，并保留该机器的设备配置与标定。`agx-sim` 不控制真实设备。

`make verify` 包含契约测试、仿真权限测试、真实子进程 IPC 和原有回归测试。均不访问物理设备。操作系统必须允许本机测试 socket；受限沙箱的绑定失败不能视为硬件问题。

## 启动与读取

终端一启动合成相机，终端二使用相同端点目录查询：

```bash
uv run --frozen agx-sim serve --kind camera --device-id front --endpoint-dir /tmp/agx-front
```

```bash
uv run --frozen agx-sim inspect --endpoint-dir /tmp/agx-front
```

目录必须属于当前用户且权限为 0700，socket 为 0600；服务拒绝覆盖已有端点。Ctrl+C/SIGTERM 释放本进程创建的 socket。强杀可能留下端点，排查所有者后再处理，不自动删除未知进程的资源。

握手只返回描述，不开始产流。获取租约并执行 PREPARE 后读取样本：

```python
from agx_sim.transport import HalClient

with HalClient("/tmp/agx-front") as client:
    owner = {"session_id": "demo"}
    owner.update(client.request("acquire", **owner))
    client.request("prepare", **owner)
    for _ in range(6):
        sample = client.receive(0.5)
        if sample is not None:
            print(sample.header.device_id, sample.header.stream, sample.header.seq)
    client.request("release", **owner)
```

`--kind` 支持 `leader`、`follower`、`camera`、`wrench`。使用不同 `--device-id` 和 `--endpoint-dir` 启动第二相机或力传感器，无需改动消费者协议。Follower 可用 `--axes 2` 验证通用契约不写死六轴或七维。图像是 8×6 合成数据，用于协议验收，不代表真实设备吞吐。

## 权限与时间语义

Follower 必须依次 acquire、prepare、authorize、align_begin、align_step、activate，才接受连续命令。`align_step` 传入 `agilex_contract.Command`；它的关节名与顺序必须匹配描述，目标满足限位，时间由本机 `time.monotonic_ns()` 生成。仿真对齐即时更新合成状态，不能作为真机到位证据。

连续目标通过 `HalClient.send(command)` 非阻塞发送，返回 False 表示连接尚未就绪或队列暂不可写。管理请求、连续命令和样本/确认使用不同 socket；确认仅为 received/accepted/submitted/rejected，不承诺物理执行。尚未提交的目标采用最新值覆盖，提交前再次检查有效期。每次只处理有限批消息；接收端仍有积压时推迟提交，避免执行中间旧目标，同时继续处理管理请求、看门狗和采样。

采样轮询按下次采样期限等待，`--hz` 表示目标频率；Python 与操作系统调度不提供硬实时保证。消息大小、类型和嵌套深度均有上限；坏消息被拒绝后服务仍可处理后续请求。

服务独立检测命令超时、租约失效、对齐步骤间隔与总期限；状态查询、无效命令、租约续期都不会延长连续命令期限。失效会清空待执行目标并撤销权限，重新 acquire 后仍须重新授权与对齐。`--command-timeout-s`、`--lease-timeout-s` 是仿真参数，不是 PiPER-X 已验证的设备策略。

每条样本携带设备/流/epoch/序号、采样/接收/发布时间、时钟域、有效性及来源。合成数据标为 estimated；缓存保留原采样时间和序号，标为 cached/stale。RGB8 与小端原生 Z16 使用独立字节帧，深度尺度随帧保存；力数据包含坐标系、力矩参考点、零偏与标定标识。

PUB/SUB 可能丢消息，接收序号用于识别缺口。P1 定义 episode 边界字段，完整录制、生产端边界核对与完成记录属于 P2；不能将 P1 的消息往返描述为完整数据采集验收。
