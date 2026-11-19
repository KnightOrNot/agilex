# AgileX Project Guide

Teleoperation and RGB-D capture for PiPER-X, GELLO, and D455F through CLI and browser applications.

Start with [HABITS.md](HABITS.md), then read [.ai-stage](.ai-stage). Current stage: `TESTING`.
Use [.agents/](.agents/) to load only the documents relevant to the task.

| When | Read |
| --- | --- |
| Understand the project, scope, and module boundaries | [Project overview](.agents/project.md) |
| Work on code, dependencies, tooling, or documentation | [Engineering conventions](.agents/conventions.md) |
| Select and load a skill | [Skill index](SKILLS.md) |
| Start work, verify changes, or update the project stage | [Workflows](.agents/workflows.md) |
| Work with hardware, data, external services, or releases | [Authorization and constraints](.agents/constraints.md) |
| Work with branches, versions, commits, merges, or submodules | [Git workflow](.agents/git.md) |
| Check current acceptance status, evidence, and open work | [Testing](.agents/docs/stages/testing.md) |
| Work on the HAL design or phased migration | [Architecture baseline v3.3 (Chinese source)](.agents/docs/specs/architecture-v3.3.md) |
| Run P0 baseline measurements on the lab machine | [P0 lab runbook (Chinese)](.agents/docs/specs/p0-baseline-runbook.md) |
| Run P3 HAL acceptance and minimal motion checks | [P3 lab runbook (Chinese)](.agents/docs/specs/p3-hardware-runbook.md) |
| Trace baseline, document layout, or historical decisions | [Validation baseline](.agents/docs/decisions/0001-baseline-and-validation.md) / [Document layout](.agents/docs/decisions/0002-habits-document-layout.md) |
| Work on force estimation and precision assembly research | [Force estimation draft (Chinese)](.agents/docs/specs/force-estimation.md) |
| Trace earlier investigations | [October 2026 history (Chinese)](.agents/docs/reviews/history-2026-10.md) |
| Install, operate, configure, or troubleshoot the application | [English docs](docs/en/index.md) / [简体中文](docs/zh/index.md) |

When the stage changes, update `.ai-stage` and the stage reference here. Maintain rules in their source documents.
