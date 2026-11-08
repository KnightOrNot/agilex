# 技能索引

本索引于 2026-11-08 核对当前会话可用清单与本地 SKILL.md 文件，仅记录与本项目相关的技能，不保证其他主机安装相同。加载时从会话技能清单解析对应包的位置，再读取表中 SKILL.md，不把本机绝对路径作为通用约定。

| 名称 | 适用场景 | 加载入口 |
| --- | --- | --- |
| `superpowers:brainstorming` | 需求澄清 | Superpowers 包的 `brainstorming/SKILL.md` |
| `superpowers:writing-plans` | 实施计划 | Superpowers 包的 `writing-plans/SKILL.md` |
| `planning-with-files` | 复杂任务跟踪（按需） | planning-with-files 包的 `planning-with-files/SKILL.md` |
| `caveman:lean-build` | 小范围完整实现 | Caveman 包的 `lean-build/SKILL.md` |
| `caveman:safe-refactor` | 保持行为的重构 | Caveman 包的 `safe-refactor/SKILL.md` |
| `caveman:investigate-first` | 证据优先排错 | Caveman 包的 `investigate-first/SKILL.md` |
| `superpowers:systematic-debugging` | 系统性定位故障（与前项择一） | Superpowers 包的 `systematic-debugging/SKILL.md` |
| `superpowers:test-driven-development` | 行为测试与实现 | Superpowers 包的 `test-driven-development/SKILL.md` |
| `caveman:verify-and-stop` | 范围明确的收尾验证 | Caveman 包的 `verify-and-stop/SKILL.md` |
| `superpowers:verification-before-completion` | 完成声明的证据核对 | Superpowers 包的 `verification-before-completion/SKILL.md` |
| `verify` | 按项目 Make 命令验证并修复 | gstack 包的 `gstack-verify/SKILL.md` |
| `review` | 审查当前差异 | gstack 包的 `gstack-review/SKILL.md` |
| `document-generate` | 补齐用户文档 | gstack 包的 `gstack-document-generate/SKILL.md` |
| `document-release` | 核对文档与实现一致 | gstack 包的 `gstack-document-release/SKILL.md` |
| `ship` | 遵循 git.md 的验证/提交/PR 交付 | gstack 包的 `gstack-ship/SKILL.md` |
| `land-and-deploy` | 获授权后合并和部署 | gstack 包的 `gstack-land-and-deploy/SKILL.md` |
| `careful` | 破坏性操作保护 | gstack 包的 `gstack-careful/SKILL.md` |
| `browse` | 网页读取与交互 | gstack 包的 `gstack-browse/SKILL.md` |

## 使用边界

用户指定技能时遵从其要求；否则选择一个适合任务范围的主流程，专项技能按需补充，避免重复跑同类完整流程。提供目标、范围、验收、Make 命令及资料目录，不复制技能正文。

技能缺失时说明情况，按项目规范完成可执行部分。gstack 仍是本项目已有必需工具，缺失时依 workflows 处理。技能默认升版、自动 commit、推送或部署均不得覆盖 [Git 门槛](.agents/git.md) 与 [授权边界](.agents/constraints.md)。物理测试确认前不因技能创建计划或检查点 commit。

可配置的规格/实施计划放 `.agents/docs/specs/`，计划与规格分文件并互相引用；评审/决策按对应目录归档。工具任务状态文件保持工具支持的位置与格式，项目阶段记录只保存长期结论与证据入口。
