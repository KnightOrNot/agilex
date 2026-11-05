# 安装与环境

## 要求

使用支持 SocketCAN 的 Linux、PiPER-X/AGX 夹爪、USB-CAN 与 GELLO Dynamixel 主手。软件工具为 Git、pyenv、uv、iproute2、FFmpeg、编译工具和 lsof。系统包与转换依赖在 converter 环境中验证，不进入实时控制环境。

controller 与五个子模块统一使用 Python 3.12。根目录的 `requires-python` 当前限制为 `>=3.12,<3.13`，与 GELLO 包一致。

## 一键配置

```bash
git clone --branch dev git@github.com:KnightOrNot/agilex-controller.git
cd agilex-controller
./scripts/setup.sh
```

setup 从脚本位置找到仓库，初始化五个一级 submodule，通过 pyenv 选择各自 Python，再用 uv 的锁文件同步环境。当前 GELLO 使用 PyPI DynamixelSDK 4.0.5；脚本也兼容声明了嵌套 SDK 的历史版本。它会安装 Ubuntu 系统包、按需安装 pyenv/uv，并检查 dialout。配置过程不访问 CAN/串口，不发送运动命令。

浏览器数采使用独立的 Python 3.12 环境，首次使用前安装：

```bash
uv run agilex-data-collection setup
```

它同步 `third-party/agilex-adapters/.venv`，安装 LeRobot（官方 v0.6.0）、LeLab（固定提交）
和网页依赖，并构建前端，需要网络和 Node。默认 Python 3.12.14；已有完整解释器
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

已有 pyenv 与 uv 时：

```bash
git submodule sync --recursive
git submodule update --init
pyenv install -s "$(pyenv latest -k 3.12)"
python312="$(PYENV_VERSION="$(pyenv latest -k 3.12)" pyenv which python)"

UV_NO_MANAGED_PYTHON=1 uv sync --project third-party/agilex-sdk-python --frozen --python "$python312"
UV_NO_MANAGED_PYTHON=1 uv sync --project third-party/agilex-gello-software --frozen --python "$python312"
UV_NO_MANAGED_PYTHON=1 uv sync --project third-party/lerobot-converter --frozen --extra dataset --python "$python312"
UV_NO_MANAGED_PYTHON=1 uv sync --project third-party/camera-submodule-d455f --frozen --python "$python312"
UV_NO_MANAGED_PYTHON=1 uv sync --frozen --python "$python312"
UV_NO_MANAGED_PYTHON=1 uv sync --project third-party/agilex-adapters --extra app --python "$python312"
mkdir -p data/raw data/lerobot
```

`agilex-adapters` 的 `app` extra 包含浏览器数采所需的 LeRobot、LeLab、FastAPI
与 uvicorn。它不是根环境的依赖，也不影响命令行 controller。

GELLO 和 camera-realsense 包通过根目录 `tool.uv.sources` 中的本地 editable 路径安装。controller 与 GELLO 独立 CLI 各自安装相同代码的基础依赖，这是两个独立环境；无需将多个虚拟环境加入 PYTHONPATH。

GELLO 当前使用 `agilex_gello_software` 导入命名空间和锁定的 PyPI DynamixelSDK 4.0.5。开发期间使用 `--skip-submodules` 保留本地改动。初始化应使用主项目固定的子模块提交；需要主动升级时才运行 `git submodule update --init --remote`（按 `.gitmodules` 的 `branch = dev`（`main` 基线仍跟踪 `main`）），并在测试通过后提交新的引用。

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
后续功能与 Python 版本迁移在 `dev` 分支进行，`main` 保留已验证的稳定基线。

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

确认状态完整、CAN 收包正常后按 README 启动。安装路径改变时重新创建对应 `.venv`，不要修补旧 console-script shebang。

## RealSense 首次接入

查看[相机安装指南](../third-party/camera-submodule-d455f/docs/installation.md)配置 Linux udev 权限，重新插拔设备；setup 不会自动安装 udev 规则。推荐 USB 3 数据连接，避免与其他采集程序争用设备。

```bash
uv run --project third-party/camera-submodule-d455f camera-realsense info --profiles
```

根据实际 profile 设置 controller 的 `[camera]`，不要用相机库独立实验的 TOML 代替 controller 配置。首次联调按 README 先做只读检查，再启动跟随和短集采集；检查质量报告后再长时间采集。无图形桌面保持 `preview=false`。

## Python 3.12 验证记录（2026-11-05）

目录迁移已先发布到 `main`（`a8ab196`），Python 迁移只在其后的 `dev` 中进行。
根项目与五个子模块均使用 Python 3.12.16。软件回归共 276 项：controller 122、
GELLO 12、SDK 59、camera 59、converter 12、adapters/application 12。
包含真实 LeRobot 数值/RGB-D 数据集回读、模拟帧和本地 IPC；未进行真机实验。
SDK/camera Pyright、现有 lint、六个分发包构建及仓库外 wheel 导入均通过。

GELLO `full` 依赖完成安装与关键模块导入检查，包括 DynamixelSDK、RealSense、
MuJoCo、Pinocchio、pygame 和 Qt。发现并修正了 pin 3.7 与新版 urdfdom/tinyxml2
的 ABI 不匹配；不以安装成功代替二进制导入检查。xarm 上游存在转义字符串的
SyntaxWarning，不阻止导入。未运行图形仿真、Menagerie 模型或 ROS 2 构建；
本机未安装 pyenv，未执行一键脚本的 pyenv 安装分支，使用现有完整解释器验证。
