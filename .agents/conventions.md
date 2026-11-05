# 开发约定

依据根目录 [HABITS.md](../HABITS.md) 生成；项目专属数据和接口契约见 [project.md](project.md)。

## 语言与命名

- 中文沟通，AI 项目资料与中文文档用中文；代码、标识符、英文文档用英文。
- Python 四空格缩进，公共接口有类型注解，函数/模块 `snake_case`，类 `PascalCase`，测试文件 `test_*.py`。
- README 和用户文档按语言分开：根 README 双语，`docs/en/`、`docs/zh/` 页面路径一一对应，页顶提供双向语言链接；使用相对链接，保持术语、命令、默认值同步。

## 代码与职责

- 清晰、简单、可维护；不为当前需求之外的场景引入依赖、抽象或重构，不预建空目录或占位文档。
- 简单功能直接组织模块；确需分层时使用 `core/`、`services/`、`adapters/`、`runtime/`，核心不依赖外层，禁止循环依赖。本项目保留现有模块，不因规范化重排运行时代码。
- 第三方源码放 `third-party/`，用 Git submodule 固定版本；保留上游风格，不做无关格式化。
- 设备统一创建与释放，RPC 等待有界；单调时钟用于调度与时间审计，墙钟用于诊断。重负载导入在硬件启动前完成，避免首帧阻塞。

## 工程与工具

- 使用 uv、`src/<package>/` 布局；包、依赖、工具和入口集中在 `pyproject.toml`。锁文件仅由 uv 维护，Python 与本地/CI 保持兼容，`.venv/` 只在本地生成。
- 根 Ruff 配置在 `pyproject.toml`，检查 `src`、`tests` 与文档检查脚本；pytest 路径和 integration marker 也在该文件。
- 根项目未配置 mypy，不报告其通过；已有 SDK/camera 的 Pyright 继续由各自配置维护。本轮不额外引入类型检查依赖。
- 根 `make lint`、`make test`、`make docs` 与 `make verify` 是统一检查入口；具体命令与验证范围见 [workflows.md](workflows.md)。

## 测试与文档

- 测试真实行为，按风险选择范围，不写仅复述实现的测试。覆盖配置、超时、错误、中断、初始化失败、清理顺序和数据兼容。
- 硬件使用 fake，实际行使本地 ZMQ、私有 IPC 和真实数据集读回。测试锁使用 pytest 临时目录，不争用操作员锁。
- 现有 `tests/` 保留；需要分类时再建 `unit/`、`integration/`；当前没有 Agent/LLM 实现，不建空 `eval/`。
- 行为变更同步双语 README、对应用户文档和英文 CHANGELOG；AI 规范与阶段状态只维护在 `.agents/`，用户手册不记录开发流水账。
