# HABITS.md

## 个人习惯

| 类别 | 基础约定 |
| --- | --- |
| 语言 | 使用中文沟通和编写中文文档；使用英文实现代码、标识符和编写英文文档。表达直接、简洁，说明关键原因。 |
| 代码 | 保持清晰、简单、可维护；职责与依赖边界明确，不引入当前需求之外的抽象、依赖或重构。 |
| 协作 | 先同步工作区，理解已有资料与实现，保留用户现有工作；在授权范围内主动完成任务，仅对影响正确性、范围或重大成本的不确定事项提问。 |
| 交付 | 以实际验证结果说明完成情况；明确区分事实、假设和未验证项，保持实现、文档与命令一致。 |

## 基础架构

统一目录职责与命名，基础文件必须保留，扩展内容按需创建，不预建空目录、占位文档或无用分层。已有项目增量调整，保留现有工作。

```text
project-root/
├── AGENTS.md                     # 规范索引与路由，≤60 行
├── CLAUDE.md                     # @AGENTS.md
├── HABITS.md                     # 基础约定
├── .ai-stage                     # 当前阶段
├── README.md                     # 英文落地页
├── README.zh-CN.md               # 中文落地页
├── LICENSE                       # 许可证原文，必备
├── CHANGELOG.md                  # 英文版本记录，必备
├── CONTRIBUTING.md               # 英文贡献指南，必备
├── .agents/                      # AI 项目资料
│   ├── project.md
│   ├── conventions.md
│   ├── workflows.md
│   ├── constraints.md
│   └── docs/
│       ├── stages/               # 阶段记录
│       ├── specs/                # 详细规格
│       ├── decisions/            # 关键决策
│       └── reviews/              # 评审与复盘
├── docs/                         # 面向用户的发布物文档
│   ├── en/                       # 英文文档
│   │   ├── index.md              # 首页与导航
│   │   ├── installation.md       # 安装与快速开始
│   │   ├── usage.md              # 基础用法，可选
│   │   ├── faq.md                # 常见问题，可选
│   │   ├── reference/
│   │   │   ├── cli.md            # CLI 参考
│   │   │   ├── config.md         # 配置参考
│   │   │   └── errors.md         # 错误码与异常
│   │   ├── guides/               # 进阶教程，可选
│   │   └── assets/               # 图片与示例文件
│   └── zh/                       # 简体中文文档
│       ├── index.md
│       ├── installation.md
│       ├── usage.md              # 可选
│       ├── faq.md                # 可选
│       ├── reference/
│       │   ├── cli.md
│       │   ├── config.md
│       │   └── errors.md
│       ├── guides/               # 可选
│       └── assets/
├── pyproject.toml                # 包、依赖、工具与命令入口
├── uv.lock                       # uv 维护
├── .python-version
├── src/<package>/                # 源码，按实际职责分层
├── tests/                        # 行为验证
├── .gitignore
└── Makefile                      # 统一操作入口
```

扩展内容有实际用途时再加入，路径保持一致：

| 场景 | 位置 |
| --- | --- |
| 贡献指南译本与治理 | `CONTRIBUTING.zh-CN.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md` |
| 独立 Git 约定 | `.agents/git.md` |
| 独立脚本或第三方源码 | `scripts/`、`third-party/` |
| GitHub 自动化与协作 | `.github/` 下的工作流、Issue 与 PR 模板 |
| 提交前检查 | `.pre-commit-config.yaml` |

以下内容用于把基础架构落地：先建立必需的目录与文件，再按本节写入内容。`HABITS.md` 原样放入根目录；与个人习惯相关的文件（`conventions.md`、`workflows.md`、`constraints.md`，需要时还有 `git.md`）直接依据本文件生成；与具体项目相关的文件（`project.md`、阶段文档、用户文档）依据现有资料填写，资料未覆盖处标 `待确认`，不编造。标为可选的目录与文件只在有实际内容时创建，生成后项目的具体规范以 `.agents/` 中的文件为准。

## AI 项目资料

`AGENTS.md` 只做索引与阶段路由，不超过 60 行；`CLAUDE.md` 使用 `@AGENTS.md`；同一规范只维护一份，其他位置引用。

### AGENTS.md

- 首屏：项目一句话定位、当前阶段（读 `.ai-stage`）、项目资料入口
- 路由表：按任务指向 `project.md`、`conventions.md`、`workflows.md`、`constraints.md`、阶段文档与用户文档
- 只说明“什么时候读什么”，不复制具体规则，阶段变化时同步更新

### CLAUDE.md

- 内容仅一行：`@AGENTS.md`

### project.md

- 定位：一句话说明项目做什么、为谁解决什么问题
- 目标与验收：可检验的目标与完成标准
- 范围与非目标：明确不做什么
- 术语表：核心概念与缩写，中英文对照
- 事实来源：需求、计划、README 等资料及其位置
- 未知信息标 `待确认`，不自行假设

### conventions.md

- 语言：中文沟通与中文文档；英文代码、标识符与英文文档
- 命名：目录、模块、类与函数、测试与文档文件的命名规则
- 代码：清晰、简单、可维护；职责与依赖边界明确，不引入当前需求之外的抽象
- 分层：简单功能直接组织模块；需要分层时使用 `core/`、`services/`、`adapters/`、`runtime/`，核心不依赖外层，禁止循环依赖
- 依赖：第三方源码放入 `third-party/` 并以 submodule 固定版本
- 工程：uv 与 `src/<package>/` 布局，依赖、工具配置与命令入口集中在 `pyproject.toml`；锁文件仅由 uv 更新，Python 版本与本地、CI 保持兼容；`.venv/` 仅本地生成
- 工具：ruff、mypy、pytest 的规则与配置位置
- 测试：验证真实行为，按风险选择范围；需要分类时使用 `unit/`、`integration/`，涉及 Agent/LLM 行为时加入 `eval/`
- 文档：中英页面一一对应，术语一致，使用相对链接

### workflows.md

- 新会话：先读 `HABITS.md` 与 `AGENTS.md`，再按路由加载所需资料
- 开发：同步工作区 → 理解现有资料与实现 → 计划 → 实现 → 验证 → 同步文档
- 命令：`make sync`、`make lint`、`make test`、`make docs`、`make verify`；脚本通过 `uv run` 执行
- 验证：`verify` 汇总真实检查，未配置项明确说明，不以占位命令报成功；文档检查覆盖双语同步与链接有效性
- 阶段流转：修改 `.ai-stage`，只建立当前阶段文档，关键跨阶段决策写 ADR
- 文档维护：README 与 `docs/` 双语同步
- 协作：使用 GitHub 时配置 CI；本地、pre-commit 与 CI 使用一致标准；Issue、PR 模板只收集问题、变更与验证所需的信息
- 技能：使用实际可用的技能，遵守本文件与项目约束，具体流程交由技能负责；技能建议与产物不构成授权
- 失败处理：不隐藏失败，说明已完成的验证与未验证项

### constraints.md

- 授权：破坏性操作、远端变更、发布、对外发送、付费及生产操作须有相应授权；已有授权不重复确认
- 禁止：密钥、环境、缓存和本地数据不入版本控制；敏感信息不写入日志或文档
- 工作区：不覆盖用户修改，保留现有工作
- 质量：不以削弱测试或验收标准掩盖问题
- 范围：不引入当前需求之外的依赖、抽象或重构
- 结构：不预建空目录、占位文档或无用分层

### git.md（按需）

- 分支：命名规则与用途
- 提交：一次提交一项可验证的变更，信息说明变更内容与原因
- PR：变更内容、验证方式与结果、风险
- 合并：允许的合并方式与清理规则
- `.gitignore`：覆盖 `.venv/`、缓存、本地数据与环境文件

### 规格、决策与评审

| 位置 | 内容 |
| --- | --- |
| `.agents/docs/specs/` | 详细规格：接口、数据、行为与验收标准 |
| `.agents/docs/decisions/` | ADR：背景、选项、决定、后果与状态 |
| `.agents/docs/reviews/` | 评审与复盘：范围、发现、证据、结论与后续动作 |

只记录需要长期保留与追溯的内容，不写流水账。

## 用户文档

根目录必备文件：

- `LICENSE`：许可证法律原文
- `CHANGELOG.md`：英文，采用 Keep a Changelog 格式，按版本记录新增、变更、修复与移除
- `CONTRIBUTING.md`：英文，说明环境准备、开发命令、测试要求与 PR 流程

README：

- `README.md`：英文落地页，包含项目定位、核心特性、安装、最小可用示例、文档首页链接与许可证
- `README.zh-CN.md`：与英文版内容同步，提供双向语言切换链接，并链接中文文档首页

`docs/`：

- `docs/en/` 与 `docs/zh/` 结构与文件名一一对应，每页顶部提供指向另一语言对应页面的相对链接
- `index.md`：项目简介、特性与导航
- `installation.md`：环境要求、安装步骤、快速开始与验证命令
- `usage.md`（可选）：基础用法与常见任务
- `faq.md`（可选）：常见问题与排查
- `reference/cli.md`：命令、参数与示例
- `reference/config.md`：配置项、默认值与示例
- `reference/errors.md`：错误码、原因与处理方式
- `guides/`（可选）：进阶教程
- `assets/`：图片与示例文件
- 命令与示例必须可用，不放 AI 规范或阶段记录

贡献指南中文版、行为准则与漏洞报告流程按需提供，中文版与英文版保持一致。

## 阶段文档

`.ai-stage` 只保存一个当前阶段值，随实际工作更新，允许回退与循环。阶段文档统一放入 `.agents/docs/stages/`，默认只读当前一份，必要时追溯。

| 阶段 | 文件 | 内容 |
| --- | --- | --- |
| `PLANNING` | `planning.md` | 需求、范围、验收标准、风险与依赖 |
| `CODING` | `architecture.md` | 模块、接口、数据流与依赖边界 |
| `TESTING` | `testing.md` | 测试范围、命令、结果、缺陷与遗留 |
| `DEPLOY` | `deployment.md` | 环境、步骤、验证与回滚 |

- 只建立当前阶段的文档，推进阶段时先更新 `.ai-stage`
- 记录结论与证据，不预填完成状态；阶段标记不代表验证通过或发布授权
- 关键跨阶段决策保存为 ADR，并在阶段文档中链接

## 维护约定

- 本文件的约定经用户授权后修改，并记录原因、范围与依据，同步相关引用
- 项目记录按事实维护，区分事实、假设与未验证项
- 临时要求不自动变为长期习惯，项目规则不自动同步到其他项目
- 规则冲突时明确指出，不自行放宽约束
