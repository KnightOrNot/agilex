# 贡献指南

[English](CONTRIBUTING.md) | 简体中文

## 开发环境

当前主项目及五个子模块统一使用 `main`，已合并的 `dev` 不再保留；需要隔离改动时从
`main` 创建临时功能分支，合并完成后删除。新链路仅修改 `src/agilex_data_collection/`
和独立 `agilex-adapters` 子模块，保持原 controller 运行链路不变。
新应用环境安装、模拟验证及接口边界见[README](README.zh-CN.md)与
[架构与数据流](docs/zh/index.md)。

所有项目的 Python 3.12 解释器、独立 `.venv` 和依赖统一由 uv 管理；controller 依赖由 `pyproject.toml` 与 `uv.lock` 管理。GELLO 与 camera-realsense 通过本地 editable 依赖安装；不要在 controller 环境中安装 SDK 硬件依赖、LeRobot 或 PyTorch。

```bash
./scripts/setup.sh --skip-system --skip-submodules
uv sync --frozen
uv run agilex-controller --help
```

SDK、GELLO 与 camera-realsense 的独立环境使用 Python 3.12，converter 使用 Python 3.12。各子项目的环境用于其独立工具和开发；一个子项目的 `.venv` 不会自动成为另一个解释器的导入路径。

## 模块分工

| 文件 | 责任 |
| --- | --- |
| `cli.py` | 参数解析、命令分派、退出码 |
| `configuration.py` | TOML、命令行覆盖、校验与路径解析 |
| `robot_client.py` | 对接现有 SDK 的 ZMQ 协议、超时、错误响应与资源关闭 |
| `gello.py` | 显式传入主手校准、主从方向与启动相对映射 |
| `control.py` | JS 定位、启动检查、频率控制、跟随循环、录制按键 |
| `recording.py` | raw v1/v2 session/episode、有界异步队列、保存/丢弃/`.partial` |
| `camera.py` | RGB-D 采集生命周期、独立预览进程、有界无损图像队列 |
| `workflow.py` | 设备预检、进程、信号、客户端组合、安全退出、转换器子进程 |

主手库保持上游读取接口；controller 不导入 GELLO 的应用命令模块。CAN 与硬件保护属于 SDK；时间戳对齐和数据转换属于 converter。camera-realsense 提供独立 RGB-D 帧及主机时间映射，controller 保存 raw；RGB/深度匹配和单位转换留给 converter。

## 修改原则

- Python 使用四空格缩进、公开接口类型标注、`snake_case` 函数/模块和 `PascalCase` 类名，使用 Ruff 检查与格式化。
- 设备实例在 workflow 中创建并统一释放；新步骤失败时仍需完成之前已获取资源的清理。
- 使用单调时钟安排控制周期和记录相对时序；墙钟用于诊断。当前 raw 的 observation 是 action 下发后的反馈，修改配对语义必须同时评估转换与训练用途。
- 保持 RPC 等待有界。REQ 请求超时或被中断后关闭该 socket，退出回零使用独立客户端。
- 录制使用有界队列，写盘或队列错误必须显式上报；失败数据保持 `.partial`。保存中断不能遗留等待 sentinel 的线程。
- 退出时先结束硬件控制，再做耗时刷新与转换。不要跳过 JS 退出流程或在退出期间切换普通 J 模式。
- `scripts/` 保留五个 Shell 入口：一个负责安装，四个只调用 controller CLI。原入口默认无相机，新相机入口显式启用 camera 与预览；不要在启动脚本中复制运行流程。
- 校准写在配置文件中，通过 `DynamixelRobotConfig` 传给 GELLO；不要为当前串口修改库中的全局端口表。

## 检查与测试

从 controller 根目录运行：

```bash
make lint
make docs
make test
make verify
uv build
```

pytest 的 `tests/test_*.py` 覆盖配置优先级、SDK wire protocol、启动检查、JS 步长、录制、信号与清理顺序。测试不访问硬件。

完整测试还会调用 `third-party/lerobot-converter/.venv/bin/python` 执行真实数值/RGB/RGB-D 转换、视频解码与米制深度读回；未安装该环境时跳过这项测试。安装环境后可单独执行：

```bash
uv run --frozen pytest -m integration
uv run --frozen pytest -m "not integration"
```

没有全仓覆盖率门槛。为行为变化增加针对性测试，尤其是异常、取消和数据兼容；避免只复述实现的测试。

修改 GELLO 后，在其目录执行 `uv run --frozen pytest`，并运行现有 CI 的 lint：

```bash
uv run --frozen ruff check src tests experiments scripts --select E9,F63,F7,F82
```

不要格式化无关上游文件；必要行为适配写入本地 `src/`。当前 GELLO 使用
`agilex_gello_software` 命名空间和 PyPI `dynamixel-sdk==4.0.5`，没有嵌套 SDK、
`gello/` 导入或离线上游审计命令。共享依赖变化同步更新 GELLO 与 controller 的
`uv.lock`；SDK 单独修改时，使用其 README 中的检查流程。

## Submodule 与多仓库工作流

`../agilex-gello-software/` 是独立工作副本，controller 内的 `third-party/agilex-gello-software/` 是另一个 Git 工作副本。它们不会自动同步文件。

发布版本时，先在 GELLO 仓库提交、测试并推送，再让 controller submodule 检出该提交，最后在 controller 提交 gitlink。不要提交无法从远端获取的子项目提交。

```bash
git -C third-party/agilex-gello-software status --short
git submodule status
git diff --submodule
```

开发期间子模块有未提交修改时，使用 `scripts/setup.sh --skip-submodules`。默认 setup 会拒绝脏子模块，避免把正在审阅的内容切回锁定版本。为普通使用者更新版本后，应验证一次干净检出的安装流程。

## 提交与 PR

使用简洁、祈使式主题，可采用 `feat:`、`fix:`、`refactor:`、`docs:`、`chore:` 前缀。将行为修改、必要测试和对应文档放在同一可审阅变更中。

PR 描述应说明问题与最终行为、涉及仓库及版本、运行过的检查、真实硬件是否验证，以及相关 issue。终端工具通常不需要截图。不得把模拟测试描述为真实机械臂验收。

## 数据与文档

`data/raw/` 是不可变输入，`data/lerobot/` 是可重新生成的输出。不要提交采集数据、虚拟环境、构建产物和缓存。路径相对于仓库计算，不写死个人 home 目录。

参数或默认行为变化时同步更新 README、`config/default.toml`、`docs/reference/`、CHANGELOG 和必要测试。新增硬件资料按语言放入 `docs/en/assets/` 与 `docs/zh/assets/`，有内容时再建目录。第三方代码的来源和许可文本记录在 `THIRD_PARTY_NOTICES.md`。

## 相机修改的验证

相机库目录运行 `uv run --frozen pyright` 和 `uv run --frozen python -m unittest discover -s tests -v`。转换器目录运行 `uv run --frozen --extra dataset pytest` 和 `uv run --frozen --extra dataset ruff check --isolated .`。跨仓修改需要根目录真实 RGB-D round trip；确认 PNG/深度数值、时间匹配、raw 不变以及相机故障时的 JS 清理。实机 USB 带宽、曝光延迟和持续帧率另行验收，不能从模拟测试推断。

## 双语文档与 CI

英文落地页为 README.md，中文为 README.zh-CN.md；用户文档放 docs/en 与 docs/zh，路径一一对应，每页顶部提供语言切换。AI 规范和阶段记录不写入用户手册。

`make sync` 只同步根开发环境，不初始化/升级子模块或配置系统、硬件；完整环境仍使用 setup。`make docs` 检查实际存在的链接、阶段路由和双语可执行示例；文字翻译仍需人工审阅。根 mypy、覆盖率门槛和 pre-commit 未配置，不报告为已通过。

GitHub CI 复用 make sync / make verify。私有子模块需要仓库配置只读 `SUBMODULES_READ_TOKEN`，默认 GITHUB_TOKEN 不一定有跨仓权限。CI 不安装 converter 的独立数据环境，集成测试会明确 skip；不代表完整六仓验收。工作流在发布后才能远端运行，本地检查不冒充远端 CI 结果。

项目级许可证尚未选定，保留 LICENSE 的原有状态说明；不擅自补写授权条款。根和子模块分别维护，规范化不自动传播至其他仓库。
