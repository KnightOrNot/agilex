# Git 与多仓约定

- 根和五个子模块当前发布基线为 `main`，已合并的长期 `dev` 已删除。需要隔离时从 `main` 创建临时 `feat/`、`fix/` 或 `docs/` 分支，获授权合并后清理。
- 普通初始化：`git submodule sync --recursive`，然后 `git submodule update --init`，检出父仓固定提交；只有明确升级才使用 `--remote --merge`。五个 `.gitmodules` 的远程升级分支均为 `main`。
- 移动子模块后备份并重建 `.venv`，不修补绝对 shebang。父项目、子模块和相邻独立工作副本互不自动同步。
- 一次提交一项可验证变更；用简洁英文祈使句及 conventional prefix，说明内容与原因。行为、必要测试与对应文档组成同一个可审阅变更。
- 发布顺序：子模块测试 → 授权提交并推送子模块 → 更新父 gitlink → 验证父项目 → 授权发布父仓。不得发布远端无法取得的 gitlink。
- PR 说明具体问题和最终行为、涉及仓库/版本、实际验证、硬件状态、风险与相关 issue；模板只收集审阅需要的信息。
- 可快进时优先普通 fast-forward；分叉时先审阅差异再决定，不默认 force push。删除分支需明确授权，不动未涉及的其他分支。
- `.gitignore` 分类维护，忽略 `.venv`、缓存、构建、本地环境/凭据和数据；共享 `.agents/`、规范索引、钩子与工作流进入版本控制。

历史与当前基线证据见 [ADR](docs/decisions/0001-baseline-and-validation.md) 和 [testing](docs/stages/testing.md)。
