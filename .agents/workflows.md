# 协作流程

## 新会话与开发循环

1. 先读根 [HABITS.md](../HABITS.md)、[AGENTS.md](../AGENTS.md) 和 `.ai-stage`，再按路由读取本次任务所需资料；默认只读当前阶段记录。
2. 同步工作区状态：`git status --short`、分支和 `git submodule status`；区分用户已有修改。这里的同步不等于自动 pull、checkout、reset 或升级子模块；远端写入遵守 [constraints.md](constraints.md)。
3. 理解已有资料与实现 → 说明计划 → 在授权范围实现 → 按风险验证 → 同步用户文档与阶段记录。重要未知标 `待确认`，不编造。
4. 收尾说明实际改动、命令、结果、失败/跳过和未验证项；未获提交授权时保留未提交。

## 统一命令

在根目录运行，Python 脚本通过 `uv run --frozen` 执行：

| 命令 | 真实行为 |
| --- | --- |
| `make sync` | uv 按 frozen lock 同步根开发环境；不更新 gitlink，不配置系统或硬件 |
| `make lint` | 根 Ruff lint/format 检查，逐个检查 Shell 语法 |
| `make test` | 根 pytest，包含已有 converter 环境时的真实集成回读；缺失环境的 skip 由 pytest 明示 |
| `make docs` | 检查基础文件、AI 路由、双语路径/语言链接、相对链接/锚点与双语命令/配置示例一致性；不访问网络 |
| `make verify` | 汇总 lint、docs、test；任何失败均返回非零，不以占位命令代替检查 |

完整运行环境仍用 `./scripts/setup.sh` 和 `uv run agilex-data-collection setup`；保留子模块修改时加 `--skip-submodules`。这些命令需要网络/系统权限时应明确说明。硬件命令不在任何 Make 验证目标或 CI 中运行。

跨仓更改时补跑受影响子模块的 README 检查和真实 RGB-D converter 回读。浏览器改动补跑：

```bash
uv run --project third-party/agilex-adapters --frozen --extra app pytest third-party/agilex-adapters/tests -q
```

当前根没有 mypy 或覆盖率门槛；CI 不声称执行这些检查。根 CI 与本地使用同一 Make 目标；没有配置 pre-commit，不将它报告为已运行。CI 无 converter 独立环境时明确跳过 integration，不能声称覆盖六仓完整验收。

## 阶段与证据维护

- `.ai-stage` 只保存一个值：`PLANNING`、`CODING`、`TESTING`、`DEPLOY`。切换时先改标记，再建立实际需要的阶段文档，不预建其他阶段。
- 当前为 `TESTING`，只维护 [testing.md](docs/stages/testing.md)；记录范围、命令、证据等级、结果、缺陷、授权边界与下一步。
- 已有记录与本轮实际运行分开；软件/模拟、只读硬件、操作员运行日志、运动验收不得混写。阶段名不代表通过或发布授权。
- 关键跨阶段决策写入 `docs/decisions/` 的 ADR，并在阶段文档中链接；详细规格放 `docs/specs/`，长期复盘放 `docs/reviews/`。
- 用户通知五小时 AI 额度剩余 15% 时立即停止新实现，将完成项、检查、失败与 TODO 写入当前阶段记录。额度无法通过工具读取，不声称自动监控。

## AI 工具

- 保留本项目全局 gstack 要求；开始任务确认安装根目录下有 `bin/`（优先 `$GSTACK_ROOT`，否则检查实际安装路径，当前为 `~/.claude/skills/gstack`）。缺失时停止并说明安装方法，不绕过 gate。
- 网页浏览使用实际可用的 gstack `/browse`；技能只按实际可用性和适用范围使用。`.claude/settings.json` 与 `check-gstack.cjs` 保持现状；缺 Node 或钩子时说明错误，不绕过。
- 技能建议、计划和产物不构成授权。旧 gstack 初始化不得覆盖规范索引或桥接文件；本轮不改变 gstack 配置。
- `HABITS.md` 原样保留，修改需用户授权并记录原因、范围和依据。项目规则不自动同步其他项目，临时要求不自动成为长期习惯。
