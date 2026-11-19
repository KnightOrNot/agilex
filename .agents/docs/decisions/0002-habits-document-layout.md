# ADR 0002：按 HABITS 规范组织项目资料

- 日期：2026-11-05。
- 状态：已接受；用户要求将新增 HABITS 纳入项目并按其流程规范。
- 背景：原 CLAUDE 同时存放规则、研发计划、历史证据与待办；用户文档以中文为主，缺少统一验证入口。
- 决定：HABITS 保持原文；AGENTS 只做 ≤60 行索引；CLAUDE 仅 `@AGENTS.md`；项目规则与事实拆入 `.agents/`；当前 `.ai-stage=TESTING`，只建 testing 阶段记录。
- 路径解释：用户消息中的 `.agent/` 按 HABITS 的明确目录 `.agents/` 统一，不维护两套副本。
- 用户文档：英文 README/CONTRIBUTING/CHANGELOG，中文 README/贡献指南，docs/en 与 docs/zh 对应；旧中文内容迁移而非丢弃。
- 工程入口：Make 调用已有 uv/Ruff/pytest 和实际文档检查，CI 复用相同目标；不为满足目录示意图建立空 assets、其他阶段或 Agent eval。
- 后果：新会话以 HABITS → AGENTS → 当前阶段路由；不再往 CLAUDE 追加任务状态。`.agents/` 不再被 gitignore 排除。
- 范围限制：仅根仓规范化；独立子模块的指令、代码、环境、gitlink 和 gstack 配置不改动。规范化整理时未获提交或推送授权；用户随后授权 0.2.0 元数据和规范化改动 commit & push，具体检查见 [testing](../stages/testing.md)。不包含部署或硬件操作。

后续更新：新版 HABITS 的技能索引、阶段资料保留与分支门槛见 [ADR 0003](0003-habits-branch-gates.md)，原文中的旧布局决定仅记录当时事实。

## 2026-11-19: Apply English as the default

The user updated [HABITS.md](../../../HABITS.md) to make English the default for documents without a specified language. The root agent and skill indexes, active project policies, and current testing summary use English. The paired English and Chinese user docs keep their existing paths. Historical ADRs, plans, reports, and original measurement records retain their source language. The P0/P3 lab handoffs remain in Chinese for the same operator workflow.

The reviewed Chinese v3.3 architecture source moved from the repository root to [the specs directory](../specs/architecture-v3.3.md), alongside its implementation plans. Its requirements and acceptance gates are unchanged. This documentation migration does not change the stage, application behavior, licensing status, or any publication or hardware authorization.
