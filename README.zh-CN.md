# agilex-controller

[English](README.md) | 简体中文

使用 GELLO 主手遥操作 AgileX PiPER-X，并采集 RealSense D455F RGB-D 数据。六个项目统一使用 uv 管理的 Python 3.12 和各自独立的 frozen 环境。

| 入口 | 用途 | 输出 |
| --- | --- | --- |
| `agilex-controller` | 终端跟随、episode 录制、JS 定位和转换 | raw JSONL/图像，再由 converter 生成 LeRobot Dataset v3 |
| `agilex-data-collection` | 浏览器跟随、保存/丢弃、实时预览和 LeLab 管理 | LeRobot Dataset v3，另保留不可变 RGB/Z16 输入和时间审计 |

两个入口并列，共用 `config/default.toml` 和硬件锁；同一时间只运行一条真机链路。

## 特性

- 有界控制/录制队列、显式运动确认和 JS 退出清理。
- 保留原生 Z16、标定和单调时间戳来源。
- 浏览器 RGB、深度、左右并排和交互式点云预览。
- LeLab 浏览、本地合并/删除，以及用户主动触发的 Hugging Face 上传。
- 五个子模块固定在 `third-party/`，SDK、GELLO、相机、converter 和 adapters 各自独立。

## 安装

在具备 Git 和所需系统依赖的 Linux 上执行：

```bash
git clone --branch main git@github.com:KnightOrNot/agilex-controller.git
cd agilex-controller
./scripts/setup.sh
uv run agilex-data-collection setup
```

安装流程准备 uv/Python 和固定环境，不打开设备；浏览器 setup 安装独立应用环境。加入 `dialout` 后重新登录。要求、可选依赖与升级步骤见[安装指南](docs/zh/installation.md)。

## 不连接硬件的最小运行

```bash
uv run --frozen agilex-controller --help
uv run agilex-data-collection serve --simulate
```

打开 <http://127.0.0.1:8000>。模拟会写入合成数据，但不访问机械臂、主手或相机。

真机跟随需要完成标定核对、设备检查和现场确认。普通 SSH 会话使用 `--no-camera-preview` 关闭本地弹窗；浏览器预览可通过 SSH 隧道查看。运动命令前先读[用法](docs/zh/usage.md)。

## 开发

```bash
make sync
make verify
```

这些目标同步根环境，执行真实的风格、文档与无硬件根测试。converter 集成测试需要独立环境，缺少时会明确显示跳过；完整子模块和真机验收另行执行。

## 文档

- [文档首页与架构](docs/zh/index.md)
- [安装](docs/zh/installation.md) · [用法](docs/zh/usage.md)
- [CLI](docs/zh/reference/cli.md) · [配置](docs/zh/reference/config.md)
- [子模块配置](docs/zh/reference/submodule-config.md)
- [RGB-D 与时间对齐](docs/zh/cameras.md) · [故障排查](docs/zh/reference/errors.md)
- [贡献指南](CONTRIBUTING.zh-CN.md) · [英文版本记录](CHANGELOG.md)

## 许可证

新编写代码的项目级许可证**尚未选定**。[LICENSE](LICENSE) 记录了这一状态，不额外授予使用权。第三方声明保留在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，各子模块仍使用各自许可证。
