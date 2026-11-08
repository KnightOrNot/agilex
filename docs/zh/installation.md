# 安装与环境

[English](../en/installation.md) | 简体中文

## 要求

使用支持 SocketCAN 的 Linux、PiPER-X/AGX 夹爪、USB-CAN 与 GELLO Dynamixel 主手。软件工具为 Git、uv、iproute2、FFmpeg、编译工具和 lsof。系统包与转换依赖在 converter 环境中验证，不进入实时控制环境。

controller 与五个子模块统一使用 Python 3.12。根目录的 `requires-python` 当前限制为 `>=3.12,<3.13`，与 GELLO 包一致。

## 一键配置

```bash
git clone --branch main git@github.com:KnightOrNot/agilex.git
cd agilex
./scripts/setup.sh
```

setup 从脚本位置找到仓库，初始化五个一级 submodule，由 uv 按各自 `.python-version` 安装 Python，再按锁文件同步独立 `.venv`。当前 GELLO 使用 PyPI DynamixelSDK 4.0.5；脚本也兼容声明了嵌套 SDK 的历史版本。它会安装 Ubuntu 系统包、按需安装 uv，并检查 dialout。配置过程不访问 CAN/串口，不发送运动命令。

浏览器数采使用独立的 Python 3.12 环境，首次使用前安装：

```bash
uv run agilex-data-collection setup
```

它同步 `third-party/agilex-adapters/.venv`，安装 LeRobot（官方 v0.6.0）、LeLab（固定提交）
和网页依赖，并构建前端，需要网络和 Node。默认由 uv 选择 Python 3.12；已有完整解释器
可用 `setup --python /path/to/python3.12`。根目录的 Python 3.12 环境不会安装
这些依赖，两个环境互不替换。

常用参数：

| 参数 | 用途 |
| --- | --- |
| `--skip-system` | 已装好系统依赖时跳过 apt 与用户组修改 |
| `--skip-submodules` | 保留本地子项目修改，不重新检出锁定提交 |
| `--check-only` | 只检查已安装环境与命令 |
| `--gello-extra NAME` | 仅为 GELLO 独立环境安装可选 camera/simulation/robots/full |
| `--with-simulation-assets` | 显式下载 GELLO 的 MuJoCo Menagerie |

控制只需要 GELLO 基础依赖；RealSense 使用单独的 camera-realsense 库，不需要 GELLO 的 camera extra。默认安装不下载仿真模型。GELLO 的 `simulation` / `full` 额外约束
`pin==3.7.0` 对应的 urdfdom 4 与 tinyxml2 10 ABI，避免安装成功后导入失败。

## 手工同步

安装 uv 后：

```bash
git submodule sync --recursive
git submodule update --init
uv python install 3.12
uv sync --project third-party/agilex-sdk-python --frozen --managed-python --python 3.12
uv sync --project third-party/agilex-gello-software --frozen --managed-python --python 3.12
uv sync --project third-party/lerobot-converter --frozen --extra dataset --managed-python --python 3.12
uv sync --project third-party/camera-submodule-d455f --frozen --managed-python --python 3.12
uv sync --frozen --managed-python --python 3.12
uv sync --project third-party/agilex-adapters --frozen --extra app --managed-python --python 3.12
mkdir -p data/raw data/lerobot
```

`agilex-adapters` 的 `app` extra 包含浏览器数采所需的 LeRobot、LeLab、FastAPI
与 uvicorn。它不是根环境的依赖，也不影响命令行 controller。

GELLO 和 camera-realsense 包通过根目录 `tool.uv.sources` 中的本地 editable 路径安装。controller 与 GELLO 独立 CLI 各自安装相同代码的基础依赖，这是两个独立环境；无需将多个虚拟环境加入 PYTHONPATH。

GELLO 当前使用 `agilex_gello_software` 导入命名空间和锁定的 PyPI DynamixelSDK 4.0.5。开发期间使用 `--skip-submodules` 保留本地改动。初始化应使用主项目固定的子模块提交；需要主动升级时才运行 `git submodule update --init --remote`（五个 `.gitmodules` 均跟踪 `branch = main`），并在测试通过后提交新的引用。

更新已有工作副本前，将原子模块目录中的 `.venv` 移到仓库外备份。
迁移后的入口脚本必须由新环境生成，再按以下顺序更新：

```bash
git pull --ff-only
git submodule sync --recursive
git submodule update --init
./scripts/setup.sh --skip-system --skip-submodules
uv run agilex-data-collection setup
```

五个子模块集中在 `third-party/`；相机远程仓库为
`git@github.com:KnightOrNot/camera-realsense-d455f.git`，本地目录为
`third-party/camera-submodule-d455f/`，包名/命令仍为 `camera-realsense`。
目录迁移后旧 `.venv` 的入口脚本可能仍指向旧绝对路径。请先将各子模块的
`.venv` 移到仓库外备份，再运行上述 setup 重建；不要修补旧入口脚本。
有未提交的子模块修改时先保存工作，再执行更新；普通更新检出主项目固定的提交，
不自动跟随远程分支。GELLO 的可选 Menagerie 资产仍按需初始化。
Python 3.12 与 uv 迁移已合并至 `main`，已合并的 `dev` 分支不再保留。
普通使用安装稳定 main；开发集成到 dev，每次在独立 dev-<任务名> 工作分支修改，并遵守贡献指南的提交门槛。

## 安装验证

```bash
./scripts/setup.sh --check-only
uv run --frozen agilex-controller --help
uv run --frozen agilex-controller config
uv run agilex-data-collection --help
uv run --frozen pytest
```

浏览器数采自身的环境用 `uv run agilex-data-collection setup` 安装；`--help` 只验证
根入口，不加载独立网页环境。

脚本会检查 CLI、FFmpeg 与 converter 的 TorchCodec 加载。真实转换回归可通过 `uv run --frozen pytest -m integration` 单独运行。

## 串口与 CAN

```bash
sudo usermod -aG dialout "$USER"
```

注销并重新登录后检查 `/dev/serial/by-id/`，修改 `config/default.toml` 中的 port 与标定参数。不要只凭串口名沿用另一台主手的校准。

```bash
./third-party/agilex-sdk-python/scripts/config_can.sh can0 1000000 100
uv run agilex-controller read --json
uv run agilex-controller status
```

`read` 初始化 GELLO 时会关闭主手扭矩；严格只读审计应仅使用 Dynamixel PING/READ，
不要调用该命令。它不发送从臂运动指令，但会改变主手原有扭矩状态。

确认状态完整、CAN 收包正常后按 README 启动。安装路径改变时重新创建对应 `.venv`，不要修补旧 console-script shebang。

## RealSense 首次接入

查看[相机安装指南](../../third-party/camera-submodule-d455f/docs/installation.md)配置 Linux udev 权限，重新插拔设备；setup 不会自动安装 udev 规则。推荐 USB 3 数据连接，避免与其他采集程序争用设备。

```bash
uv run --project third-party/camera-submodule-d455f camera-realsense info --profiles
```

根据实际 profile 设置 controller 的 `[camera]`，不要用相机库独立实验的 TOML 代替 controller 配置。首次联调按 README 先做只读检查，再启动跟随和短集采集；检查质量报告后再长时间采集。无图形桌面运行包装脚本时加 `--no-camera-preview`，因为脚本参数优先于 TOML。

## 普通终端与远程运行

使用全新的普通终端核对 uv，避免只验证部署专用 PATH：

```bash
command -v uv
uv --version
id -nG
```

若 uv 只装在专用工具目录，将该目录加入 Shell PATH，或安装到标准用户 bin 目录。激活项目虚拟环境本身不会安装 uv。

加入 dialout 后重新连接 SSH，或者启动加载新组权限的 Shell：

```bash
newgrp dialout
```

普通 SSH 通常没有图形显示环境。相机包装脚本显式开启 Tk 弹窗，仅设置 TOML preview=false 不能覆盖它：

```bash
./scripts/start_camera_follow.sh --no-camera-preview
```

这只关闭本地窗口，不关闭配置的 RGB-D 采集。远程查看浏览器预览时保持 HTTP 回环监听，通过 SSH 转发：

```bash
ssh -L 8000:127.0.0.1:8000 robot@RON
```

在 RON 启动采集服务，客户端打开 localhost:8000。真机模式启动服务会准备 CAN，启动真机会话仍需运动确认。也可在配置好的远程图形桌面中打开终端运行 CLI，确保 DISPLAY 可用。远程桌面需要独立配置证书、凭据和网络访问；敏感信息不得放入项目文件。TCP/RDP 握手成功不代表实际桌面登录或相机预览通过。
