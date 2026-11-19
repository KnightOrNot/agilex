# TESTING

Updated 2026-11-19 (Asia/Shanghai). The active stage is set by the root `.ai-stage`.

| Work | Current status |
| --- | --- |
| P0 baseline | Complete. Preserve the frozen 0.2.2 inputs, criteria, and measured evidence. Use the approved [1.5° arrival baseline](../decisions/0005-position-tolerance-baseline.md) for new acceptance; do not schedule a separate tolerance experiment. |
| P2 runtime | Simulation acceptance complete. See the [P2 review](../reviews/architecture-p2-review-20261118.md). |
| P3 physical HALs | Offline verification complete for 0.2.4; physical acceptance remains NOT_RUN. See the [P3 review](../reviews/architecture-p3-review-20261119.md) and [lab runbook (Chinese)](../specs/p3-hardware-runbook.md). PiPER-X behavior after command loss remains unverified and gates the associated fault injection. |
| Documentation migration | Active project guidance now defaults to English under [HABITS.md](../../../HABITS.md). See the [layout decision](../decisions/0002-habits-document-layout.md). The original Chinese records below remain available as evidence. |

## 范围与证据口径

当前目标是验证 Python 3.12/uv 基线下的 CLI、浏览器采集、GELLO、PiPER-X 和 D455F。P0 的 B2/B3/B4 两入口已通过；Web 已补齐超过 10 秒的保存/丢弃窗口并全量回读。任务名差异已记录，用户同意继续；B5 核心矩阵/离线路径与 B6 真实输入双端回放已核验，完整 B4 黄金备份已回传；用户已明确授权完成 B7 最终验收，P0 COMPLETE。P2 统一 runtime 仿真验收、P3 设备包装离线验证均已完成，证据见文末。P3 真机验收、CLI 桌面预览和末端力估计各自单列。

证据分为：本轮本地实际检查、此前工具执行结果、软件/模拟、真机只读、用户自行运行的日志、待验证。迁移记录不是重新运行；没有 Windows 桌面截图、真机完整 episode 或持续吞吐数据时不写“全部通过”。

## 当前版本与环境

| 仓库 | 2026-11-05 已发布 main 基线 |
| --- | --- |
| 根 controller | `926e513ce583b2f6931814822c071fc56566a9e7` |
| adapters | `93492d35bdc1b6dc6b27d35f07694f1b49b2a1cb` |
| GELLO | `dd44a6f1d28d994b5185b0efd63faec102fdecde` |
| SDK | `24cac28cdd296607f93defd89158aed70d91e11c` |
| camera | `ba47e2669e1ea5b4ecf2a14f168b1d91d7a5123f` |
| converter | `976b9385ee388802b542c70b058f93d0fb92d657` |

表中是此前已验证本地、GitHub 和 RON 一致的历史基线；本次 0.2.0 元数据与规范化提交的检查见文末。RON 尚未同步此次改动，不能宣称三处当前源码完全相同。main/dev 决策见 [ADR 0001](../decisions/0001-baseline-and-validation.md)。

P0 在 RON 的独立实验副本中执行，固定基线 640aad8（0.2.2）。P0 环境为 uv 0.13.6、CPython 3.12.16；独立环境、锁文件和机器身份见本地证据。主机地址、登录信息和凭据不写入本文。

## 六项计划及验收

| 项 | 范围 | 验收 | 当前结果 |
| --- | --- | --- | --- |
| 1 | 环境准备 | 六环境 frozen 依赖可用，CLI 帮助/关键二进制导入正常，普通终端可找到 uv，用户串口权限有效 | 已完成；最初专用 PATH/临时串口组的缺口后续已修复 |
| 2 | 软件回归 | 根与五个子模块测试、现有 lint、SDK/camera Pyright、逐个 Shell 语法及帮助、lock/build/wheel 导入 | 此前远端 279 项通过；本轮规范化检查见下文，不用旧计数冒充新运行 |
| 3 | 模拟采集 | 独立端口/数据根，启动、采样、保存、丢弃、停止，四预览及真实 LeRobot 回读，无硬件访问 | 已完成；仅合成低分辨率验证 |
| 4 | 真机只读 | 主从设备身份、主手编码器/标定核对、CAN/从臂反馈、相机 profile/标定，不使能/运动/开流 | 已完成；夹爪端点等已知限制仍保留 |
| 5 | 最小运动 | 操作员确认后先无相机回零、对齐、小范围跟随、退出；分别按入口实际容差验收 | P0 B3 CLI/Web 已通过；完整定位日志及现场确认见文末 |
| 6 | 短时真机采集 | CLI 相机录制及浏览器各先约 10 秒，保存/丢弃、关节/RGB/Z16 回读、质量报告与清理正常 | B4 CLI/Web 已完成；保存/丢弃时长、退出及全量回读均已核验 |

阶段 5 的 CLI 默认 `move_js` 容差为 1.0°；浏览器 `[collection].position_tolerance_deg=1.1`。参数不在本轮修改。持续全分辨率吞吐和长时间稳定性不包含在短片段通过结论中。

## 已完成：此前实际证据

### 软件与模拟

- 远端 279 tests：root 125、SDK 59、camera 59、GELLO 12、converter 12、adapters/app 12；真实 IPC、数值/RGB/RGB-D 数据集读回包含在既有结果中。
- 现有 lint、SDK/camera Pyright、五个 Shell 文件逐一语法、四个 wrapper 帮助、六个离线 lock 检查、六个 sdist/wheel 构建及 checkout 外导入通过。GELLO 缺失构建缓存补传后原命令通过。
- `serve --simulate` 在独立端口 18086 完成 API 与 Chromium 页面测试：保存 16 帧和 455 帧，各一个 episode；丢弃不增加集数，原始审计输入保留。
- 四种预览使用 64×48 合成输入、RGB-D 128×48、点云 192 点；观测约 30 FPS。包含真实 LeRobot 读回、7 维 action、uint16 Z16、1 米深度和单调时序。
- 发布前补跑 37 项定向根测试、Ruff、六锁检查及 RON `--check-only`。复用了之前完整软件/模拟证据，未在合并任务运行运动或物理采集。
- 限制：LeLab 远端复用同提交的已构建 wheel，未独立验证其远端前端构建；无全分辨率/持续吞吐验收，中文字体缺失时没有中文布局视觉验收。

### 真机只读

- GELLO 使用稳定 by-id 路径，57600 baud，1–7 号响应；严格探针发送 7 PING、105 READ，读取前后七轴扭矩均为 0。没有以 `agilex-controller read` 冒充严格只读。
- 主手映射六轴约 `[0.176, 0.088, -0.967, -18.369, -4.834, -2.549]°`。夹爪原始约 203.115°，配置 159–201°，未截断为 1.05036、输出被截到 1；完整端点待现场复核。
- D455F 的 SDK 与 USB 描述符序列号见本地设备证据。固件 5.17.0.10、USB 3.2；640×480@30 和 640×360@90 的 RGB8/Z16、内外参和约 0.001 m 单位有效。该阶段没有开流或测速。
- USB-CAN 最初未枚举；换线后 candleLight `1d50:606f` 出现并生成 can0，序列号见本地设备证据。用户单独授权运行 `config_can.sh can0 1000000 100`，接口保持 UP、1 Mbit/s、队列 100。
- SDK 共享锁内三次只读采样及 `uv run --frozen agilex-controller status` 通过；固件 `H-V1.2-1`/`S-V1.8-2`，六轴约 `[2.293, -2.468, 2.479, 36.324, 1.446, -4.026]°`，无报告故障，时间戳推进。
- 状态反馈约 200 Hz；SDK 2840–2860 FPS 是聚合 CAN 报文频率，不是控制/数据集频率。历史 dropped 58446→58477 后稳定，不能声明零丢帧或持续可靠性通过。

### 普通终端与远程桌面补齐

| 问题 | 已执行修复与验证 | 剩余边界 |
| --- | --- | --- |
| `exec: uv: not found` | 原安装只在 `~/hezijue/.tools/`；将同版本 uv 放到 `~/.local/bin`，备份 `.bashrc` 后加入 PATH。新普通交互 shell 识别 0.13.6，四 wrapper `--help` 和 `setup --check-only` 通过 | 已打开终端需刷新 PATH；此检查不启动硬件 |
| GELLO serial missing/inaccessible | 设备存在、root:dialout 660；用户明确授权后执行 `sudo usermod -aG dialout robot`。新 SSH 登录确认组生效，`os.access` 可读写 | 原终端需 `newgrp dialout` 或重新登录；验证未打开串口 |
| `camera preview failed` | 用户确认从 SSH 运行；SSH 无 DISPLAY，Tk 导入成功，单独创建窗口复现无显示错误。解析验证 `--no-camera-preview` 只关闭弹窗，RGB-D 配置保持启用 | 没有重新运行机器人跟随或物理相机流；桌面实际预览尚未验证 |
| Windows RDP 0x204 | RDP 原先 disabled、无凭据/证书/监听。用户明确授权后配置用户私有 TLS、登录凭据和键鼠控制，启用 GNOME Remote Desktop。3389 监听、跨主机 RDP 协商及 TLS 1.3 握手通过，指纹匹配 | Windows 实际登录与 GUI 预览待用户确认；此前桌面 LockedHint=yes；不在文档保存凭据 |

用户提供的运行日志含 `[安全退出]` 和 `PiPER-X JS target reached`，随后报告 preview failed。它说明该次日志记录了退出目标到达，不证明全部启动、方向、持续跟随或采集通过；不把该次用户运行记为代理完成第 5 项。

## 缺陷与下一步

| 优先级 | 待办 | 验收/处理 |
| --- | --- | --- |
| 扩展验证 | Windows 远程桌面 | 尚未验收；SSH 已恢复，不能据此认定 RDP 通过。按 P0 手册不作为核心完成门槛 |
| 扩展验证 | CLI 桌面相机预览 | 本轮显式关闭预览，无弹窗为预期；下次核对显示环境及开关后验证，不预判为代码缺陷 |
| 已完成 | 第 5 项最小运动 | B3 两入口通过，后续仅在基线/行为变化影响结论时安排相应复验 |
| 范围说明 | GELLO 夹爪端点与方向 | 现场允许范围内已由操作员确认；全行程机械标定未扩展，不自动调整 offset |
| 已完成 | 第 6 项短采集 | CLI/Web 均已完成；任务标签差异保留为备注，数据未重命名或修改 |
| P1 | 预览故障诊断改进 | 目前父进程只显示通用错误，原子进程异常未结构化传播。考虑在运动前验证预览启动，并保留真正错误；本轮未改运行时代码 |
| P1 | 只读 CLI 语义 | `read` 实际关闭 GELLO 扭矩，文档已纠正；是否新增严格只读入口待决定，不把它视为已有能力 |
| 已完成 | P0 测量、回放与最终验收 | CLI-A/B、Web-B/C、离线路径及 B6 双端回放完成；Web-A 接受两对；B7 已获用户最终验收，保留报告限制 |
| P2 | 项目级许可证 | 原 LICENSE 仅说明尚未选定；需用户决定授权条款，本轮保留原文，不代填许可证 |
| P2 | 力估计 Phase 0 | 控制接口、i/τ 单位/符号/采样位置/频率、kt、负载、温漂；先 fake/回放估计与 effort schema，再考虑受监督标定 |

## 执行边界与复用命令

已有 CAN 准备、dialout 和 RDP 配置授权仅对应此前明确操作；不代表持续运动、标定或任意网络配置授权。第 5/6 项仍需对应现场操作确认。每次只运行一个控制入口，不覆盖已有服务/数据，不自动放宽容差。

安全的本地软件检查：

```bash
make docs
make lint
make test
make verify
```

根集成测试在独立 converter 环境已安装时运行，缺失则 pytest 明示 skip。完整六仓复验需逐仓环境和相应 README 命令，不能只用 `make verify` 代替六仓与硬件验收。

## 证据位置

- 原检查点归档：[2026-11-05 原始验证摘要](../reviews/ron-validation-20261105.md)，旧事件不构成新的操作授权。
- 本地忽略报告：`.gstack/release-reports/main-20261105/{report.md,github-and-local-verified.json,ron-result.json}`；只读硬件 `.gstack/qa-reports/ron-phase4-20261105/`。
- 远端：`~/hezijue/test-results/20261105-phase123/`、`20261105-phase4/`、`20261105-main-sync/`、`20261105-uv-path/`、`20261105-rdp-setup/`。配置备份留在主机，不把秘钥/密码带入仓库。
- 历史 J3/UI/LeLab 结果：[复盘](../reviews/history-2026-10.md)。未来规格：[力估计草案](../specs/force-estimation.md)。

## 本轮 HABITS 规范化验证

规范化检查点完成时工作区保留未提交；该次检查没有推送、远端同步、设备读取或运动。随后用户已授权本文末的 0.2.0 提交与推送。本轮结果不改变第 5/6 项的待验收状态。

| 实际检查 | 结果与范围 |
| --- | --- |
| `make verify` | 通过：Ruff lint、32 文件 format 检查、逐个 Shell 语法、文档检查及 133 项 root pytest |
| `tests/test_docs.py` | 8 项通过：正常资料、缺译文、TOML 示例漂移、坏文件链接/锚点、缺语言链接、阶段资料/路由缺失、CLAUDE 桥接错误 |
| 根集成回读 | 三项 converter 集成测试实际通过，本次没有因缺 converter 环境跳过 |
| `uv build` | 根 sdist/wheel 成功；现有 uv 0.13.6 与 build_system.requires 范围的 warning 仍输出，未为压制 warning 改依赖或锁 |
| GitHub workflow | YAML 本地解析、只读权限和 Make 调用核对通过；尚未发布/触发，不声明远端 CI 通过。私有子模块可能需配置 SUBMODULES_READ_TOKEN |
| 工作区与完整性 | HABITS SHA-256 保持 `a454e005d228d855821cdebbd2b35c986589d72ff592fa243dae0d959634e39b`；AGENTS 22 行；CLAUDE 仅一行桥接；当前阶段只有 testing.md；共享资料未被忽略 |
| 范围核对 | `src/`、config、pyproject、uv.lock、gitlink、子模块、.claude 钩子与 LICENSE 均无改动；`git diff --check` 通过 |

本轮新增的检查脚本首次出现一条 Ruff 行长度失败，已修正；新测试的临时夹具最初遗漏 LICENSE，导致 1 failed / 132 passed，补齐夹具后完整重跑为 133 passed（37.00 s）。未削弱断言或跳过检查。

文档检查覆盖本地链接/锚点、双语页面/语言入口及可执行示例；不联网验证外部 URL，不自动保证译文语义完全等价。SDK/camera Pyright、其他五个子模块全套测试、Windows 实际 RDP 登录与全部硬件验证未在本轮重跑。根 mypy、覆盖率门槛、pre-commit 尚未配置，不记为通过。

下一次会话从 HABITS → AGENTS → 本文件进入；先确认远程桌面实际登录及预览状态，再按上述授权边界推进最小运动和短采集。不要再次把测试清单追加到 CLAUDE。


## 0.2.0 元数据与提交前验证（2026-11-05）

用户明确要求更新根 pyproject.toml 的 version/description 并 commit & push，覆盖上一轮保留未提交的 HABITS 规范化工作。此授权不修改子模块版本，也不包含 RON 工作副本同步、真机操作或包索引发布。

- 根项目版本为 0.2.0；description 为 `PiPER-X/GELLO teleoperation and RGB-D data collection through CLI and browser workflows`。
- 通过 `uv lock --offline` 同步根包版本；uv.lock 只变更主项目 0.1.0→0.2.0，其他依赖及五个 gitlink 不变。英文 CHANGELOG 已同步版本说明。
- origin/main 获取后与本地 HEAD 的提交差异为 0/0；使用普通 main 提交与推送，不强制覆盖远端。
- `make verify` 实际通过，133 tests passed（36.62 s），包含三项真实 converter 集成回读及八项文档检查回归；Ruff、逐个 Shell 语法、双语文档/链接检查通过。
- `uv lock --check --offline` 通过；`uv build` 生成 0.2.0 sdist/wheel。直接读取 wheel METADATA 确认 Version=0.2.0 且 Summary 与新 description 一致。
- 现有 uv/backend 范围 warning 仍存在；未修改构建依赖以压制。HABITS 原文哈希不变，运行时代码、设备配置、子模块、Claude 钩子与 LICENSE 均未修改。
- 本节记录提交前已执行的验证，不预填推送或 GitHub CI 成功。最终提交/同步状态以 Git 日志和 origin/main 引用核对；远端 CI 实际运行结果尚未核验。

当前仍为 TESTING，第 5/6 项、Windows 实际图形登录和相机持续吞吐仍按前文待办推进。


## 新版 HABITS 迁移检查点（2026-11-08，0.2.1）

用户替换 HABITS 并明确授权本次最后一次直接 commit/push main，后续将保护 main。此范围的一次性例外见 [ADR 0003](../decisions/0003-habits-branch-gates.md)；没有执行或声称通过实物测试，不能据此解除下一轮提交前的用户实测门槛。

- 完成：SKILLS 实际技能索引及 AGENTS 路由；分支/版本/实测确认约定；保留阶段资料与技能产物规则；双语贡献指南及 PR 模板；CI main/dev/dev-* 覆盖；仓库改名后的克隆 URL。
- 版本：按末段 +1 为 0.2.1，简介重新概括 CLI/浏览器遥操作与 RealSense RGB-D 数据集能力。uv 离线更新 lock 仅改变根版本，无依赖升级。
- 本轮实际 `make verify`：134 passed（46.97 s），包括三项真实 converter 回读、九项文档检查回归；Ruff、32 文件 format、逐个 Shell 语法、双语示例及本地链接检查通过。
- `uv lock --check --offline` 通过，`uv build` 生成 0.2.1 sdist/wheel。现有 uv/backend 范围 warning 保留，未压制或变更依赖。
- CI YAML 本地解析确认开发分支覆盖；未核验本轮远端 Actions 结果。新版 HABITS 原文 SHA-256 为 `f593937162df4db467f3f3696edc2ffa9beffa99de0dd838a8ca46ff5214c953`，用户内容未改动。
- 交付目标：main 普通推送后，由同一提交初始化本地/远端 dev，结束后停留 dev；不修改五个子模块 gitlink/分支，不修改 GitHub 保护策略，不同步 RON 工作副本。
- 未验证：本轮不访问设备，不运行第 5/6 项；Windows 实际桌面登录、相机 GUI 与持续吞吐仍保持前文待确认状态。

上述记录是发布前已完成的检查及交付目标；实际推送和分支状态须以 Git 引用核对，不预填成功。后续每次修改在 dev-<任务名> 进行，自动化和用户实测均通过后才能 commit/合并 dev；main 发布流程细节待确认。


## main/dev 同步前的 CI 修复检查点（2026-11-08，0.2.1）

用户要求本地、远程 main 与远程 dev 完全一致。同步前本地/远程 dev 为 bb0c266，main 为 01bf012；两个提交只改了 .gitignore，版本沿用本次维护的 0.2.1。

- 远端 protect-main 已生效：main 必须通过 PR 和 GitHub Actions 的 software 检查，禁止删除/强推。本次读取时 bypass 列表为空；没有修改或绕过规则。
- 现有 [PR #1](https://github.com/KnightOrNot/agilex/pull/1) 被 [CI 运行 42462906959](https://github.com/KnightOrNot/agilex/actions/runs/42462906959) 阻塞：129 passed、2 failed、3 skipped。两个工作流单元测试意外依赖本机 SDK/converter 的 .venv，尚未到达目标断言就抛出 FileNotFoundError。
- 在仅同步根 uv 环境、没有任何子模块 .venv 的临时源码副本中，先重现同样的两个失败。修复让测试在 pytest 临时目录提供解释器路径占位，并显式配置 SDK/converter 项目路径；原有清理顺序、错误传播和 CAN 前端口占用保护断言均保留，占位文件不会执行。
- 修复后的干净副本定向测试：2 passed；完整 make verify：131 passed、3 skipped（6.87 s），跳过的是缺独立 converter 环境的既有集成回读。
- 本机完整 make verify：134 passed（54.03 s），包含三项真实 converter 回读；Ruff、Shell 语法和文档检查通过。
- 改动限于单元测试、英文 CHANGELOG 与本检查点；运行时代码、硬件配置、依赖/版本、子模块 gitlink 和 CI 规则均未改变。未访问硬件，不将软件结果记为实物验收。
- 交付目标：推送测试修复，等待 PR 的远端 software 成功后通过普通 merge 合入 main，再将同一合并提交快进同步至本地 main/dev 和远端 dev；最终提交与 CI 结果以 PR 和分支引用为准。


## 相机子模块目录统一（2026-11-10，版本保持 0.2.1）

用户确认目标名称为 camera-realsense-d455f，并明确要求不增加版本号、直接完成远程 main/dev 同步。本次仅迁移目录与引用，不增加硬件测试或设备访问授权。

- 将 `third-party/camera-submodule-d455f` 通过 git mv 迁移到 `third-party/camera-realsense-d455f`；远程仓库仍为 `git@github.com:KnightOrNot/camera-realsense-d455f.git`，固定提交保持 ba47e2669e1ea5b4ecf2a14f168b1d91d7a5123f。
- 同步 .gitmodules、根 pyproject 的 editable 路径、安装脚本及其测试夹具、中英文安装/使用/配置链接和项目路由资料。uv lock --offline 只改变锁文件两处相机路径，包版本与依赖解析保持不变；历史变更记录保留当时名称。
- 旧根/相机环境备份到本地忽略的 `.gstack/venv-backups/camera-path.HV2352/`，以 uv/Python 3.12 frozen lock 重建两个环境。确认根解释器从新路径导入 camera_realsense，活动环境的 editable 元数据无旧路径。
- 根 make verify：134 passed（45.54 s），包括三项真实 converter 回读；Ruff、Shell 语法、双语文档与链接检查通过。
- 相机新目录：pyright 为 0 errors、0 warnings；离线 unittest 为 59 passed；CLI --help 通过。未连接或操作物理相机、机械臂。
- uv lock --check --offline 通过；setup.sh --check-only 首次因本地缺少 data/raw 和 data/lerobot 退出，补齐忽略的数据目录后通过。knight 缺 dialout 组的既有提示保留，未改变系统权限。
- 子模块源码、其他四个 gitlink、相机 CLI/导入名、设备配置与运行时代码保持不变。既有 uv/build backend 版本范围 warning 保留。
- 交付目标：工作分支提交后同步 dev，经 PR 的必需 software 检查合入 main，再快进同步本地 main/dev 与远程 dev；不绕过 main 规则。最终 SHA 与远端 CI 结果以 PR/分支核对为准，不将软件验证当作第 5/6 项真机验收。


## 架构 P1：契约与扩展仿真（2026-11-11，0.2.2 待测）

用户授权清理无用 dev 分支并按架构文档开始实现。本轮按 [ADR 0004](../decisions/0004-hal-service-architecture.md) 与 [P1 计划](../specs/architecture-p1-plan.md) 实施，仅为软件/仿真证据，P0 真机基线及第 5/6 项仍未完成。

- 分支：确认三个旧本地分支相对 dev 没有独有提交后，用普通删除移除 dev-camera-path、dev-ci-isolation、dev-gitignore。当前工作分支改名为 dev-architecture-p1；main/dev、远端引用和原五个 gitlink 未改。
- 实现：独立 agilex-contract 包提供设备/流描述、类型载荷、时间与来源、命令/确认、episode 边界与严格 wire 校验；根 agx-sim 提供 leader/follower/camera/wrench 的独立进程、私有 IPC、租约/权限/对齐状态、非阻塞命令及本地看门狗。两台相机、假六维力和非六轴 follower 均有测试。
- 迁移范围：旧 CLI/Web 真机路径保留，未连接 CAN、串口或物理相机。新 runtime、录制、raw v3 文件布局/回放及真实 HAL 归后续 P2/P3+；不能把边界类型存在视为录制完成。
- 仓库限制：third-party/agilex-contract 已初始化为独立本地 Git 仓库，但没有首次提交、远端或父 gitlink。当前工作副本可运行，单独克隆父仓尚无法获得新依赖；提交门槛满足后按子仓发布→父仓 gitlink→完整新克隆验证推进。
- 依赖：uv 仅更新根版本 0.2.1→0.2.2，并新增 agilex-contract 0.1.0 与 msgpack 1.2.4，根既有依赖版本不变。两个包的 sdist/wheel 构建成功；原 uv/backend 范围 warning 仍存在。契约包有独立开发工具声明与 uv 锁，不以父仓测试环境替代独立安装入口。
- 基线：受限沙箱先在既有 ZMQ bind 测试中中止；允许本机测试 socket 后 make verify 为 134 passed。这是沙箱权限问题，没有改动或跳过旧测试。
- 首轮集成：165 passed、1 failed。新测试错误地假定异步 PUSH 已连接；改为在激活前等待可写，并用样本确认 PUB 订阅已就绪，生产代码 send() 仍保持非阻塞且可返回 False。
- 独立评审确认三项重要问题：深层嵌套消息可触发递归崩溃、批次积压提交中间旧目标、固定 5ms 等待无法支持声明的高频采样。三项均补测试先复现失败，再修复为深度上限、积压时延后提交及按采样期限轮询；真实 IPC 坏消息在两个通道上均被拒绝且后续握手正常。
- 最终完整 make verify：**170 passed（38.58 s）**，含原 134 项、契约 22 项、控制 7 项、真实子进程 IPC 5 项和服务循环 2 项；Ruff、format、Shell 语法及双语文档检查通过，没有 skip。契约 stdlib-only 导入通过；wheel 核对包含新模块，版本分别为 0.2.2/0.1.0。
- 收尾独立验证：契约仓库用自己的 frozen uv 环境运行 22 项测试、Ruff 与 format 全部通过，sdist/wheel 重新构建成功。补充 dev 工具后用 uv 同步父锁的 requires-dev 元数据；根既有依赖版本不变，两个 uv lock --check --offline 与根 frozen sync 均通过。文档/计划补全后 make lint docs 与 git diff --check 再次通过。
- 没有提交、合并、推送或远端 CI 结论；HABITS SHA-256 仍为 f593937162df4db467f3f3696edc2ffa9beffa99de0dd838a8ca46ff5214c953。执行账本及完整测试输出保留于本地忽略目录 .superpowers/sdd/architecture-p1-plan/，不会将其当作已提交历史。

操作说明见 [仿真指南](../../../docs/zh/hal-simulation.md)。请用户在当前工作副本按指南启动/查询/读取合成相机并退出，确认本轮待测结果；该步骤不要求运行真机。项目提交前仍遵循 git.md 的用户确认门槛，P0 运动和短采集验收需要原有现场授权及证据。


## P1 dev 异机分发与契约改名（2026-11-11）

用户在上一检查点后明确授权先提交待测版本到 dev 并推送 GitHub，供另一台真机实验计算机拉取。此次例外见 [git.md](../../git.md)；不将其记为硬件验收通过，不更新 main 或发布标签。

- 用户指定契约仓库为 git@github.com:KnightOrNot/agilex-contract.git；目录/包名/uv source 为 agilex-contract，Python 导入为 agilex_contract。根版本仍为本次迭代 0.2.2，契约版本仍为首次开发快照 0.1.0。
- 契约仓库首次提交及其改名提交位于 dev，父仓通过第六个子模块固定它。原五个 gitlink 不变。旧契约环境与构建产物备份在本地忽略的 .gstack/venv-backups/ 下，以 uv 重建新路径环境；不改旧 shebang，不把缓存、备份、环境或数据加入 Git。
- 本轮改名前完整 make verify 为 170 passed（48.70 s）；改名后契约独立测试 22 passed，Ruff/format、frozen lock 与构建通过，根新导入路径核对通过且旧导入不存在。名称变化不改变消息 schema 或设备行为。
- 双语指南补齐 dev 克隆、已有工作副本更新和全部子模块初始化；P1 make sync 只准备根仿真环境，真机 CLI/Web 仍需安装指南中的独立 SDK/相机/converter/浏览器环境。
- 改名后完整 make verify 为 **170 passed（42.13 s）**，无 skip；两个包构建和锁文件一致性检查通过。契约 dev 已推送 3bc6bcf3a108a2477338bb46fabe6ab8536aa817，[独立 GitHub CI](https://github.com/KnightOrNot/agilex-contract/actions/runs/42986900251) 已成功。父仓新克隆验证与远端分支结果在提交后核对；本节记录提交前证据，不预填父仓 CI 或真机成功。

### GitHub 分发后的核验

- 主仓实现提交 dff310dd8cd0fed893ecc99cb87d5404c4aedab1 已通过普通快进推送到 dev，[主仓 GitHub CI](https://github.com/KnightOrNot/agilex/actions/runs/42987308164) 成功；契约 dev 固定为 3bc6bcf3a108a2477338bb46fabe6ab8536aa817，独立 CI 已成功。main 仍为 8bef8fab71b2516d97c82369ec4b155a41a119a2。
- 在 /tmp/agilex-p1-github.cAmYR3 从 GitHub 获取主仓和六个一级子模块，用全新 .venv 执行 make sync / make verify：**167 passed、3 skipped（7.13 s）**，agx-sim --help 成功，副本工作区干净。三项 skip 是未安装独立 converter 环境的既有集成测试；本机完整环境对应三项已经通过，不把新克隆结果写成 170 全通过或完整真机安装验收。
- 首次使用递归子模块命令意外开始获取 GELLO 的可选 MuJoCo Menagerie。已停止本轮临时克隆的下载，取消该可选初始化并恢复中断的一级检出后完成以上验证。双语指南修正为 git clone 后 git submodule update --init，不使用 --recursive 下载可选资源；原工作区和采集数据未受影响。
- 收尾文档检查与九项文档回归通过；后续仅提交该拉取说明和本记录，版本保持 0.2.2。GitHub CI 与新副本证据只代表软件分发可用，P0、第 5/6 项、PiPER-X 断令行为及真机验收仍按前文待办推进。


## P0 实验机执行手册（2026-11-12，尚未执行真机）

用户要求提供可复制到实验机器、由当地 Codex 执行并回传结果的 P0 文档。新增 [P0 基线与测量手册](../specs/p0-baseline-runbook.md)，以已分发的 640aad8（0.2.2）及固定六个子模块为建议基线；仅编写测试协议，不据此修改第 5/6 项或 P0 的未完成状态。

- 覆盖版本/环境冻结、软件检查、两入口最小运动与 RGB-D 黄金数据、控制周期和序列化/复制/写盘测量、GELLO 有状态输入序列回放、特征化测试、证据归档与回传报告模板。
- 核对旧实现差异：CLI 原生 control_period_ns 与 Web 采样时刻不能混用；Web raw 不是 CLI converter 输入；CLI 1.0°/Web 1.1° 沿用现状；完整回零与对齐路径按源码记录。缺少的观测工具由实验机按手册实现、自检并随证据交回，不冒充当前已有命令。
- 本次文档检查和九项文档回归通过；12 个 Bash 代码块通过语法检查，4 个 controller 执行示例通过纯参数解析，未执行硬件命令。首次 uv 检查受沙箱缓存只读限制，允许现有缓存访问后通过，未改依赖或削弱检查。
- 当前处于 dev-p0-baseline-doc 工作分支，未提交/推送；仅修改文档和资料入口，版本、运行时代码、锁文件、子模块及 HABITS 未改。P0 是否完成须以实验机实际结果、可复核证据和用户实测确认为准；PiPER-X 断令行为仍为 unverified。


## P0 B2–B4 实验准备与 GELLO 排版补丁（2026-11-12）

用户在现场授权 B2–B4，并明确同意修复阻塞软件检查的 GELLO 纯排版问题，随后要求本地同步保留以便后续合并。本节为准备时检查点；后续 B3/B4 实测进展见文末现场结果补记，不能仅据本节声明运动或 P0 通过。

- 主仓基线：640aad8ea896b37257c5c7fe8de46220f61cac84（0.2.2）；GELLO 基线：dd44a6f1d28d994b5185b0efd63faec102fdecde。主仓 gitlink、配置、标定和依赖锁未改。
- 远端与本地 GELLO 均在独立分支 `dev-p0-format-check`，保留未提交修改；未 commit、push 或合并。改动仅为 `src/agilex_gello_software/cli.py`、`paths.py` 和 `tests/test_raw_episode_recorder.py` 的换行/导入排版，三个文件的 Python AST 修改前后一致。
- 可合并补丁：[GELLO 排版补丁](../reviews/p0-gello-format-20261112.patch)，SHA256 `2a7c56c79bbe2d64a0d65df68730b1e5d480458730dab0d3ed50692c68316e5a`；本地 diff 与远端实际应用的 diff 字节一致。后续按子仓验证、用户实测确认、提交/推送子仓、更新父 gitlink 的既有顺序集成。
- 软件回归：远端根 make verify 170 passed；SDK 59、camera 59、GELLO 12、converter 12、adapters 12、contract 22 通过（contract 22 已包含在根 170 中，不重复计总数）。SDK/camera Pyright 首次因 nodeenv 无法解析 Node alpha 版本失败；仅在检查进程 PATH 中复用现有 Node 22.22.0 后，均为 0 errors/0 warnings。
- GELLO 原版 Ruff 为 13 项 E501、1 项 I001；保留首次失败日志，应用排版补丁后本地和远端 Ruff 及 12 项测试通过。
- B2 已读到 PiPER-X 反馈及 S-V1.8-2 固件、D455F 身份及 USB 3.2；CAN can0 UP/1 Mbit/s。人工确认和读设备结果不代替 B3/B4 验收。
- 两端证据、任务账本和回传副本均位于各自实验工作区的 `data/p0/p0-20261112T091106Z/`（忽略目录）。

## P0 B2–B4 现场结果与暂存事项（2026-11-17 补记）

本节补充 2026-11-12 实验及后续现场反馈；测试发生时间以各运行日志为准。用户最新要求“先记录以上现象，下次再修改”，本轮到此暂停，不继续运动测试或修改相机行为。基线仍为 640aad8（0.2.2）及上述 GELLO 排版补丁，与本地并行的 P2 工作分开。

- **最新现场反馈**：用户明确表示“CLI 记录和丢弃都尝试了 10s”，同时观察到 CLI 没有相机视角弹窗。此项按操作员反馈记录；最新补测的运行编号、实际时间戳、保存/丢弃日志及退出码尚未核对，不能填为日志验收通过。
- **CLI 无弹窗的已知原因**：本轮 `run-b4-cli.sh` 与 `run-b4-cli-discard.sh` 均显式传入 `--no-camera-preview`，配置副本为 `[camera].preview=false`，同时保留 `--camera --camera-depth`。因此在这些命令下没有预览弹窗是预期配置行为，不代表相机未采集或预览实现已损坏。CLI 本机 GUI 预览仍为未验收；下次在本机桌面会话中核对启动入口与预览开关，再按实际结果决定是否修改。
- **B3 已核验通过**：两入口启动、六轴方向、夹爪与允许范围内端点、正常退出均得到操作员确认。CLI 启动回零/对齐/退出的最大绝对残差为 0.929°/0.966797°/0.971°（原容差 1.0°）；Web 为 0.901°/0.997734°/1.024°（原容差 1.1°）。既有服务已在会话完成后关闭，锁释放已核验；不将当时的清理结果延伸为最新补测的状态。
- **B4 已核验的 CLI 数据**：`session_20261112_173004` 保存 14.417 秒、719 条数值样本、433 帧数据集；首轮漏测丢弃，原记录保留。`session_20261112_173310` 保存 3.234 秒、98 帧，另一次丢弃的终端事件间隔约 5.957 秒，日志确认丢弃后正式集数仍为 1，正常退出及自动转换均返回 0。两份保存数据均已在 converter 环境全量回读通过，数值/深度对照最大误差为 0，raw 前后 SHA256 清单一致。
- **B4 已核验的 Web 数据**：`20261112_173515_bd3df761` 保存 202 帧（6.698 秒）、丢弃 98 帧（3.229 秒），最终 1 个正式 episode，会话正常完成；用户确认 RGB、深度、RGB-D、点云预览和停止回零均正常。相机实际为 640×360@90，数据集 30 FPS；在 adapters 环境全量回读通过，数值/深度最大误差为 0，raw 前后 SHA256 一致。CLI 实际相机配置为 640×480@30，不将两入口 profile 混同。
- **证据范围**：上述回读报告在远端 `data/p0/p0-20261112T091106Z/reports/`，包括 `b3-cli.json`、`b3-web.json`、`b3-accepted.json`、`cli-golden-quality.json`、`cli-golden-complete-quality.json`、`web-golden-quality.json`；Web raw 位于远端 `data/raw/app/20261112_173515_bd3df761/`。本地任务账本为 `data/p0/p0-20261112T091106Z/`，目前仅部分报告已回传，不能声称本地已归档全部证据或黄金数据。此前最新补测 SSH 核对被自动审批额度不足中止，命令未执行；没有绕过审批。
- **保留待办**：下次核对最新 CLI 约 10 秒补测日志、退出和数据；补齐 Web 约 10 秒保存/丢弃窗口；验证 CLI 桌面预览；回传完整报告、配置、工具及数据索引/哈希。B4 完整计划和证据交接尚未闭环，B5/B6 未执行，P0 仍为 INCOMPLETE。已保存的 GELLO 纯排版补丁继续保留，本轮不提交、推送或修改生产逻辑。

## P0 当前进度与下一轮测试（2026-11-17 核对）

**P0 COMPLETE，B7 已获用户最终验收。B2/B3/B4 已通过；CLI-A、CLI-B 各三次原版基线完成；Web-A 按用户决定以两对有效 light/detailed 测量收尾（原计划三对），不再补测。** 六份 Web-A 保存数据全量回读通过；detailed-1 退出超时单独保留，不纳入正常对照。Web-B 三次 RGB-D/固定 RGB 预览与 Web-C 三次无预览均已完成并全量回读；B5 离线路径和 CLI RPC 补充已完成；B6 真实输入双端回放通过，完整 B4 黄金备份已回传。B7 报告、索引、完整黄金备份与验收回执均已完成；用户明确回复“直接完成最后的验收吧”。现场运动由用户操作并确认，代理完成证据核验与归档。

### 当前基线与新核验

- 当时已使用更新后的入口成功登录 RON，SSH 主机密钥与之前一致。地址和实验副本位置见本地证据。
- 远端主仓仍为 `640aad8ea896b37257c5c7fe8de46220f61cac84`，六个 gitlink 未变。GELLO 未提交排版 diff 的 SHA256 仍为 `2a7c56c79bbe2d64a0d65df68730b1e5d480458730dab0d3ed50692c68316e5a`，与已保留的本地补丁一致；不以本地 P2 工作区替代远端 P0 基线。
- 找到最新 CLI 补测：`logs/b4-cli-ftyukR/`，对应 `session_20261112_173849`。保存段实际 **24.673660 秒、1,228 条数值样本、741 帧数据集**；第二段从“开始”到“已丢弃”的终端时间间隔 **20.728144 秒**（输出事件近似时长，丢弃段 raw 按原行为移除）。仅保留 1 个正式 episode，无 partial；三次定位均记录目标到达，退出及自动转换为 0。因此前文“最新 CLI 补测尚未核对”的待办已解除，无须再为时长重复 CLI 硬件测试。
- 2026-11-17 在 converter 独立环境对上述 741 帧再次执行完整只读验证：**PASS**；7D 数值和深度对照最大绝对误差均为 0；1,486 个 raw 文件、1,140,324,685 字节，检查前后 SHA256 清单一致。RGB 为有损视频，像素 MAE 均值为 1.842/255，仅报告测量值，不虚设通过阈值。
- 最新报告 `reports/cli-golden-latest-quality-20261117.json`、前后哈希清单、既有各入口报告和最新 CLI 终端/回读日志已回传本地 `data/p0/p0-20261112T091106Z/`。黄金原始数据及数据集仍在实验机，尚未完成完整归档交接。

### 状态表

| 项目 | 当前结论 | 剩余事项 |
| --- | --- | --- |
| B0 基线/环境/配置 | 原 640aad8 基线未漂移；新增 B5/B6 工具独立冻结哈希 | 下一轮仍核对原目标、配置与现场条件 |
| B1 软件回归/工具自检 | PASS；新增 B6 本地 7 项、远端 75+2 项与 no-device 预检通过 | 真实 fixture 不能用合成测试代替 |
| B2 设备与现场条件 | 2026-11-12 实测 PASS | 下一轮真机执行前确认当时的现场与设备状态 |
| B3 两入口最小运动 | CLI/Web PASS，保留各自 1.0°/1.1° 容差 | 已覆盖现场允许的小范围方向/端点；未扩展为全工作空间或完整机械标定 |
| B4 CLI RGB-D | PASS：保存、丢弃、退出、转换、全量回读已闭环 | CLI Tk 桌面预览可单独验收；当前关闭预览不阻塞采集结论 |
| B4 Web RGB-D | PASS：补测保存 27.900 秒/838 帧、丢弃 30.106 秒/904 帧；退出和全量回读通过；沿用四预览现场验收 | 实际任务标签为默认值，用户确认不阻塞；保留原数据与标签差异记录 |
| B5 性能与数据路径 | 核心矩阵/离线三轮及 B6 同次 CLI RPC 补充完成；Web-A 接受 2 对 | 保留单次 RPC 补充、观测开销与短测限制，不重复已完成组 |
| B6 GELLO 黄金序列/回放 | PASS：9995 条真实事件，远端/本地冻结源码回放误差均 0 | 末 5 秒仍运动的节奏偏差已记录；覆盖完整，无需重采 |
| B7 汇总/归档/验收 | PASS；报告/索引/验收回执完成；B4 完整 raw/dataset 5892 文件及 B6 夹具已回传校验 | 用户已验收；B5 大型测量载荷按索引保留 RON，既有范围限制保留 |

### 当前剩余步骤

1. **无需再操作机械臂**：B2–B6 所需实测和离线验证已完成；B6 静止/变化/反向/夹爪均有真实覆盖，末段未静止只作为操作节奏偏差记录。
2. **B7 已完成，无本轮必做剩余项**：`data/p0/p0-20261112T091106Z/reports/P0_REPORT.md`、`artifacts.json` 和 `p0-final-acceptance-20261117.json` 记录完整结果、限制、保管位置与用户授权。验收补充包接续原冻结证据；不自动提交、合并或发布。
3. **可选后续**：CLI Tk 预览按用户要求以后单独处理。长稳、高 profile、RDP、通信/停发故障注入仍 unverified，不伪称本轮覆盖。Web-A 两对结果决定不变。

### Web B4 时长补测闭环（2026-11-17）

- 会话 `20261117_122555_62ac6ab7`，终端记录 `logs/b4-web-cZ6WvS/`。用户确认超过 10 秒的跟随采集分别保存/丢弃，使用中无问题。保存 **27.899877 秒 / 838 帧**，丢弃 **30.106048 秒 / 904 帧**；仅 1 个正式 episode，丢弃段保留 raw 审计且 `dataset_episode=null`。
- 状态 `completed`、`error=null`，worker 已退出，共享硬件锁可获取，6001 无监听。首次核对时网页服务仍监听 18086；用户随后关闭服务，复核服务退出码为 0，6001/18086 均无监听，硬件锁可获取。代理未结束用户进程。
- 启动回零、GELLO 对齐、退出回零的最大绝对残差分别 **1.049° / 0.973141° / 1.049°**，均在原 Web **1.1°** 容差内。CAN 接口核对时显示错误/丢弃计数为 0；不将该快照冒充 B5 运行前后差值。
- adapters 独立环境全量回读 **PASS**：保存段 838 帧 LeRobot v3.0，30 FPS；保存与丢弃段原始图像全部解码。7D 数值、深度对照最大绝对误差均为 0；RGB 有损视频 MAE 均值 **1.995/255**。相机实际 640×360@90，数据集选取后的相机帧号间隔不等同于生产端丢帧；两段均无重复/逆序，时间匹配最大 **24.738 ms**，低于配置 50 ms。
- **3,489 个 raw 文件 / 2,009,203,524 字节**，检查前后 SHA256 清单一致。启动期间出现深度帧计数复位，驱动重做 warmup 后继续；保留原警告，不将它隐去或算作录制中的逆序。
- **任务标签备注**：用户称本次为 `test: WEB B4`，但状态、`meta/tasks.parquet` 和全量回读均为默认 `PiPER-X GELLO teleoperation`。当前实现仅在启动跟随时提交任务描述；用户不记得编辑时机，明确认为不阻塞并要求进入下一测试。原因未确认，未修改 raw/dataset 或重新贴标。
- 小型证据已回传本地 `data/p0/p0-20261112T091106Z/`：`reports/b4-web-20261117-capture.json`、`b4-web-20261117-verification.json`、`web-golden-latest-quality-20261117.json` 及前后哈希、worker/终端/回读日志；回传报告哈希已核对。黄金 raw 仍在实验机 `data/raw/app/20261117_122555_62ac6ab7/`，数据集在本轮 `web-lerobot/20261117_122555_62ac6ab7/`。完整归档交接由 B7 完成。

### 下一测试已准备：B5 CLI-A 原生周期基线（2026-11-17）

用户要求直接进入下一测试。先执行无观测插桩的 CLI-A，作为后续探针开销对照；不把原生时间戳统计当作完整 B5 详细观测。

- 工具位于本地与远端本轮 `b5-tools/`：`run-b5-cli-a.sh`、`native_cycles.py`、`test_native_cycles.py`、`tool-manifest.json`。使用原版 `agilex-controller record`，关闭相机/预览；未修改控制源码、标定、安全参数、依赖或既有数据。每次新建 `measurements/cli-a-native-XXXXXX/`，保留终端时序、退出码、配置、基线/工具哈希、CAN 前后快照和独立 raw/dataset。
- 操作员手动确认目标，进入跟随后 R，建议录至少 **36 秒**，S，等保存完成后 Ctrl+C 并等待回零/自动转换。每次原生命令时间戳前 5 秒作稳定期、随后 30 秒作统计窗口；分三次独立运行。助手没有启动真实运行。
- 工具在硬件退出/转换完成后离线运行，核对序号、有限 7D 数值、单调时钟及 `control_period_ns` 与相邻命令时间戳，报告各窗口周期/有符号与绝对抖动/超期分桶/最长连续超期/有效 Hz，并核对 raw 前后 SHA256。时长不足标 INCOMPLETE；异常周期不丢弃，无自创性能通过阈值。
- 本地和远端 **7 项纯合成测试通过**，覆盖固定 50 Hz、超期保留、短窗口拒绝、错误时间戳/非有限值/partial 拒绝，以及完整命令报告与 raw 不变。Ruff、Shell 语法、远端 CLI 参数解析和工具/配置哈希通过。首次预检因用户 Web 服务仍监听而拒绝，原记录保留；用户关闭后再次预检 PASS（基线、配置、工具、锁和端口），没有打开设备。
- **边界**：这是 CLI-A 原版对照组；`command_to_observation` 含调度等待及 RPC，不能当纯 RPC 延迟；保存文件不覆盖未录制阶段的周期。队列/写盘细分、Web 50 Hz 全周期探针、GELLO 构造前输入观测与 B6 回放仍待补。CAN 前后快照覆盖完整生命周期，不冒充 30 秒稳态增量。B5/B6 尚未通过。
- 工具/配置哈希见 `b5-tools/tool-manifest.json`；本地与远端自检及预检日志已回传本轮 `logs/b5-*.log`。生产代码没有修改，无提交/推送。

### B5 CLI-A 四次运行核验（2026-11-17）

**CLI-A 原版周期对照组三次有效基线已完成，B5 整体仍为 INCOMPLETE。** 用户报告共运行四次，第三次角度超过限制而回零，并明确允许排除第三次正常基线数据。按时间顺序核对，采用第 1/2/4 次；第 3 次标 `FAILED_EXCLUDED`，保留全部原始数据、partial、错误日志和退出码，没有把失败计为通过或删除它。

| 次序 / attempt | 录制跨度（命令时钟） | raw 样本 / 转换帧 | 有效控制 Hz | 周期 p99 / max（ms） | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 / `cli-a-native-J52GFp` | 45.779152 s | 2283 / 1374 | 49.848472 | 21.281578 / 24.158808 | 纳入 |
| 2 / `cli-a-native-We5y6f` | 39.158363 s | 1952 / 1175 | 49.820240 | 20.919960 / 25.475072 | 纳入 |
| 3 / `cli-a-native-txXYiS` | partial 7.463043 s | 373 / 未转换 | 不纳入 | 不纳入 | SDK 拒绝 J4 越界目标，回零到位，退出 1 |
| 4 / `cli-a-native-DXJH8S` | 39.973617 s | 1992 / 1200 | 49.800226 | 23.932492 / 31.572328 | 纳入 |

- 正常三次各自从首条命令时间起排除前 5 秒，再取固定 30 秒窗口，分别包含 1495/1494/1494 个命令（周期数 1494/1493/1493）；不把三次混池。离散命令首末跨度为约 29.97 秒，录制本身均完整覆盖窗口终点。NumPy `linear` 分位数，配置 50 Hz/20 ms；第 4 次有 3 个周期大于 30 ms，最长 31.572328 ms，三次均无大于 40 ms 的稳态周期。保留所有超期数据，不以事后阈值把抖动改为失败或隐藏。
- 第三次原始错误：`joint 4 target 1.659568rad is outside [-1.640610, 1.640610]rad`，即目标约 **95.086°**，SDK 当时允许上限约 **94.000°**。这是软件对指令目标的边界拒绝；随后应用执行正常退出回零，日志记录 `PiPER-X JS target reached`，未完成片段保留为 `.partial`，没有正式 episode 或转换数据集。不能据此宣称实物机械限位、急停、断令/watchdog 或完整故障安全已验收；没有放宽限制或复现越界运动。
- 第 1/2/4 次保存、退出、自动转换、原生周期检查均返回 0，每次三处定位日志均记录到达。converter 独立环境逐帧回读 **1374/1175/1200 帧**，7D action/state/velocity/位姿对照最大绝对误差均为 0，任务字段正确；原始文件与录制后清单一致，回读前后 SHA256 不变。无相机，因此不声称本轮验证 RGB/深度。
- 四次 CAN 前后同一 ifindex 的错误、丢弃、bus-off 等计数增量均为 0；统计范围是整个启动/录制/退出/转换过程，不能称为单独稳态窗口。核对时 6001/18086 无监听，共享硬件锁可获取。
- 首次复用 B4 RGB-D 检查器时，第一份无相机 raw v1 因没有 `cameras` 字段触发工具 `KeyError`；保留 `readback-20261117.json/.log/.exit` 原始失败。新增离线适配器 `b5-tools/check_cli_numeric.py`，仅在内存向原有严格数值校验函数传入空相机映射；没有修改 raw、原检查器或运行时源码。修正后的三份 `numeric-readback-20261117.json` 均 PASS；适配器 SHA256 `ccdddac6f9b597c4b12fe74e82773cc1406f3d427222608593f1363fd5594c18`，Ruff 通过。
- **完整本地副本已核验**：本轮 `measurements/` 下上述四个目录含 raw、LeRobot、metadata、日志、配置与报告，包括第三次 partial。`reports/b5-cli-a-artifacts-20261117.json` 记录 98 个文件、5,241,438 字节；回传文件逐个大小/SHA256 与远端一致。汇总见 `reports/b5-cli-a-native-summary-20261117.json`。这完成本组小型证据保管，不代表此前 RGB-D 大数据的 B7 交接完成。
- 下一步仍需准备详细观测工具，继续 CLI-B（RGB-D 无预览）和 Web-A/B/C，并补原版/观测开销对照及 B6 构造前输入序列；本次没有启动下一组或代替操作员发送运动确认。

### 下一测试已准备：B5 CLI-B 原版 RGB-D 周期基线（2026-11-17）

- 用户要求给出下一组操作，已准备远端与本地本轮 `b5-tools/cli-b/run-b5-cli-b.sh`。保持原版入口，开启 RGB-D、关闭 Tk 预览，沿用已验收的 CLI 配置 640×480@30；robot/gello/safety 三段与 CLI-A 完全相同。每次新建 `measurements/cli-b-native-XXXXXX/`，不会覆盖 CLI-A 或 B4 数据。
- 三次独立启动，每次由操作员手动确认目标与 `yes`，等待相机预热、回零/对齐及跟随就绪；R 后录至少 36 秒，S 保存，随后 Ctrl+C 并等待回零、转换、原生统计完成，再开始下一次。前 5 秒作为稳定期，随后固定 30 秒为统计窗。本组不做丢弃或预览切换；继续在已确认的小范围运动，避免再次触发 J4 越界拒绝。
- CLI-A 工具及哈希清单保持原样。CLI-B 使用独立冻结的 raw-v2 周期工具 `b5-tools/cli-b/native_cycles.py`，承接相同时间戳/序号/有限值/partial/窗口检查，保留实际 RGB 与深度 profile，明确 `camera_pixels_validated=false`；图像/深度/转换数据仍由已有完整 RGB-D checker 在采集结束后回读，原生统计 PASS 不代表像素已验收。
- 本地和远端 **9 项合成离线自检通过**（复用原七项时序合同，增加 RGB-D 元数据与缺少深度的拒绝）；Ruff、Shell 语法、CLI 参数解析、工具/配置哈希、原 CLI-A 工具保持一致均通过。远端只读预检 PASS：基线 640aad8、锁与 6001/18086 空闲、串口节点权限可用；检查时磁盘余量 962,324,316,160 字节，每次启动要求至少 10 GiB 余量。没有打开硬件或启动真实运行。
- 证据：`reports/b5-cli-b-preparation-20261117.json`、`logs/b5-cli-b-selftest*.log`、`logs/b5-cli-b-preflight.log`，哈希见 `b5-tools/cli-b/tool-manifest.json`；CLI-B helper SHA256 `e5b6cab3c770161346e248722d6ba1b92f1bb34adf6293000229de1616f60810`。新增的是实验记录目录内的运行/离线工具，未修改生产源码、标定、限值或依赖。
- 准备时状态为等待操作员；现已完成三次，见下节核验结果。本组仍为无插桩对照数据；RPC/队列/写盘详细观测、Web 组和 B6 尚未完成，不提前将 B5 标为通过。


### B5 CLI-B 三次运行核验（2026-11-17）

**CLI-B 原版 RGB-D/无预览对照组三次有效基线已完成；完整 B5 仍为 INCOMPLETE。** 用户报告三次测试完成，三次均保存、正常退出回零并完成自动转换，原生周期及完整 RGB-D 回读均通过。没有重复运动或修改生产源码。

| 次序 / attempt | 录制跨度（命令时钟） | raw 样本 / 转换帧 | 有效控制 Hz | 周期 p99 / max（ms） | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 / `cli-b-native-FfC3Mv` | 43.061510 s | 2146 / 1292 | 49.810973 | 22.371867 / 26.752643 | 纳入 |
| 2 / `cli-b-native-es6F6R` | 39.432773 s | 1965 / 1184 | 49.798644 | 22.195656 / 24.348094 | 纳入 |
| 3 / `cli-b-native-aO2M0g` | 40.955120 s | 2040 / 1229 | 49.772307 | 22.775278 / 27.856827 | 纳入 |

- 每次排除前 5 秒，再取固定 30 秒窗口，分别包含 1495/1494/1493 条命令，周期数 1494/1493/1492；原录制均覆盖窗口终点。配置 50 Hz/20 ms，NumPy `linear` 分位数；稳态均无超过 30 ms 的周期。大于 20 ms 的周期分别为 946/943/914，完整超期比例、连续次数及抖动见原始报告；没有把轻微超期隐藏或设置事后性能门槛。
- 相机实际为 **640×480@30 RGB8 + 原生 Z16**，深度比例约 0.001 m，逐会话标定保留。converter 环境全量回读 **1292/1184/1229 帧**，7D 数值和深度对照最大误差均为 0；RGB 有损视频 MAE 均值分别 **2.033/2.057/2.041（0–255）**，仅报告实测值。任务字段均为 `P0 B5 CLI-B native baseline`。
- 录制帧索引的重复、逆序、缺号，以及主机/设备时间倒退均为 0；时间匹配最大分别 **16.675/26.564/16.698 ms**，均低于原配置 50 ms。转换时最近邻复用相机帧不等同于采集缺帧；没有生产端完整计数，因此不宣称硬件绝对零丢帧。
- 三次均在启动预热时记录深度帧号从 6 回到 1，驱动重新预热后继续；原警告和时间戳完整保留。它发生在录制前，不能当作录制帧号逆序，也不将日志描述为没有警告。
- 保存、退出、转换、周期分析、完整回读均返回 0；每次启动回零、对齐和退出回零都记录 `PiPER-X JS target reached`，本组未额外探测定位残差。CAN 同 ifindex 前后错误、丢弃、bus-off 等增量均为 0，范围是完整生命周期。核对时硬件锁可获取，6001/18086 无监听。
- **7,426 个 raw 文件 / 5,704,855,707 字节**，与录制后 native 清单及完整回读前后清单一致。全文件索引 `reports/b5-cli-b-artifacts-20261117.json` 包含三组数据、日志与汇总共 7,511 文件；本地回传 91 个小型证据文件 / 10,673,651 字节并逐个大小/SHA256 通过，另回传索引文件。图像、视频与含深度的大型 Parquet 留在实验机；本地 raw/dataset 子目录仅为部分副本，不能直接当成完整数据集。完整 B7 尚未完成。
- 证据位于本地及远端本轮 `measurements/cli-b-native-*/` 的 `native-cycles.json`、`rgbd-readback-20261117.json`、前后清单、终端/时序/转换报告；汇总为 `reports/b5-cli-b-native-summary-20261117.json`，本地副本校验为 `reports/b5-cli-b-local-copy-20261117.json`。远端会话分别为 `session_20261117_125611`、`session_20261117_125824`、`session_20261117_130019`，原始数据未改动。
- 下一组 **Web-A 无相机录制**之前须准备并离线验证每个 50 Hz 控制周期的轻量/详细观测，不能把 Web 30 FPS raw 样本当控制周期。后续仍有 Web-B/C、观测开销对照、RPC/队列/序列化/写盘细分，以及 B6 构造前 GELLO 输入采集与回放；本轮未启动下一组。无提交、推送或阶段变更。


### Web-A 观测工具自检及人工交接（2026-11-17）

用户要求先验证，再告知需要人工执行的步骤。**准备阶段的 Web-A 工具与无硬件自检已通过；之后的实测结果见下一节。** 基线仍为 640aad8；本地 P2 工作区未同步到实验机，运行时源码与标定、限值、原有运动确认均保持不变。

- 独立工具位于本地与远端本轮 `b5-tools/web/`：`web_probe.py`、`run_web.py`、`analyze_web.py`、`test_web_probe.py`、`run-b5-web-a.sh`、`tool-manifest.json`。启动包装先按原入口配置 CAN，再使用原 adapters app 环境运行 Web；硬件 worker 仍由原 Session 创建。只有操作员点击启动并确认后才进入真实会话。
- 在当前进程的原 `Session._control` 中，于现成 `command_finished` 后插入一次周期记录，保存每个控制周期的原始开始/完成时间，而非仅 30 FPS 采样。`light` 记录周期与 phase；`detailed` 另包装实际 Bridge RPC、样本队列入/出队和 Full、`_append` 与 dataset add/save/clear/finalize 总耗时。包装转发原返回值和异常，不额外访问串口/CAN/相机；RPC 总耗时不称为纯序列化耗时。
- 控制、队列生产/消费及 writer 使用各自单写线程的有界内存；周期容量 100,000，超出记录 `probe_dropped`，统计拒绝将其作为完整基线。控制线程不逐周期输出、序列化或写盘，原 Session 完成控制退出、worker 清理回零和数据集 finalize 后才导出。保留连续所有 phase；稳态按每段开始录制后 5 秒稳定期＋30 秒窗口提取，短窗口或不连续数据标 INCOMPLETE，不丢异常周期。
- 本地 **11 项当前检查均有通过证据**，远端原环境 **11 项全部通过（10.77 s）**：off 不替换方法；正常/故障下 off/light/detailed 的设备调用、结果与清理一致；100 次控制与约 60 次采样区分；缓冲溢出与队列异常；完整窗口统计与溢出拒绝；RPC 异常原样传播；两模式使用合成 worker、真实私有 IPC 和 LeRobot 完成保存/丢弃并逐帧回读；模拟服务启动包装返回 idle/simulated 后正常关闭。Ruff 和 Shell 语法通过。
- 初始本地 IPC 检查被沙箱限制拒绝，允许本机临时 socket 后通过；另一次模拟 HTTP 检查走环境代理得到 502，直接 localhost 返回 200，修正测试客户端后该节点通过。原失败日志保留；没有将其冒充硬件故障，也未因此更改产品逻辑。
- 远端无设备预检通过：源码/工具/配置哈希一致，50 Hz 控制、30 FPS 数据集、无相机、原 1.1° 定位容差，串口节点权限、空间、共享锁及 6001/18086 空闲。实际运行前 helper 再次检查，只修改本次配置副本的输出目录。一次启动创建独立 `measurements/web-a-light-XXXXXX/` 或 `web-a-detailed-XXXXXX/`，对应 raw 仍由原入口写入唯一 `data/raw/app/<session>/`。
- **人工方案**：按 `light → detailed` 顺序交替做 3 对、共 6 次；每次独立启动，先填任务名并手动确认，进入 following 后开始采样，从 recording 起至少 36 秒，保存，等待已保存 1 段和 following，再停止并等待 completed；最后终端 Ctrl+C，等待离线统计结束再运行下一次。每次一个保存段，不增加预览或故障注入。详细/轻量对照用于评估附加观测负载，无法精确推断无探针 Web 的绝对零开销。
- 工具 manifest SHA256：`6f519a5f51b88414893649cf126b31e006cb7388024f4c525fde6ec1f89abdfe`。准备报告 `reports/b5-web-a-preparation-20261117.json`、自检/预检日志已回传；内存插入差异 `reports/b5-web-control-observer-20261117.patch` 的 SHA256 为 `56389237fb6dd1e169159492cea3e022ed02182b13fda46a962a8d583d64aa8b`，仅作审计，不能单独应用到生产源码。工具与差异均有本地副本，未提交/推送。
- 准备阶段边界：当时尚无真实 Web-A 周期结果；后续本组实测和回读已完成，见下一节。B6 的构造前 GELLO driver 原始输入捕获/确定性回放，以及离线序列化、NPY/PNG/写盘细分尚未包含；B5/B6/P0 保持 INCOMPLETE。


### B5 Web-A 六次核验与两对结果收尾（2026-11-17）

**结论：按用户明确要求，使用第 2、3 对有效 light/detailed 数据出结果，不再补测；重复覆盖为原计划 3 对中的 2 对。** 这足以报告本次实测周期、数据完整性与两对差异，不扩展为长期稳定性、精确零观测开销或完整 P0 通过。light-1 单独保留为补充；detailed-1 保存数据有效，但退出超时，不混入正常对照。

| 次序 / attempt | 录制跨度（s） | 保存帧 | 控制 Hz | 周期 p99 / max（ms） | 使用范围 |
| --- | --- | --- | --- | --- | --- |
| web-a-light-KNUPXe | 42.708005 | 1283 | 49.862890 | 20.988833 / 22.130958 | 补充正常运行，未成对 |
| web-a-detailed-UMOQAO | 48.922017 | 1469 | 49.862960 | 20.944699 / 23.546736 | 退出 error；保存数据 PASS |
| web-a-light-3GlPno | 44.505998 | 1336 | 49.853079 | 20.983904 / 23.425135 | 纳入第 2 对 |
| web-a-detailed-Fzq1Yj | 41.310415 | 1240 | 49.857215 | 20.894331 / 25.112838 | 纳入第 2 对 |
| web-a-light-EwpCKD | 39.136868 | 1175 | 49.845613 | 21.106201 / 22.250683 | 纳入第 3 对 |
| web-a-detailed-b01q6h | 47.690127 | 1431 | 49.837549 | 20.936471 / 34.002254 | 纳入第 3 对 |

- 六次都覆盖 5 秒稳定期＋固定 30 秒窗口；控制周期完整连续，raw 的命令起止时间均能匹配逐周期探针，所有 probe_dropped 为 0。配置仍为控制 50 Hz、数据集 30 FPS、无相机、1.1° 定位容差。第 2、3 对共有 **5,182 帧**；独立 adapters 环境对六次共 **7,934 帧**完整 LeRobot 回读通过：7D action/state 最大数值误差 0，主机时间戳误差 0，索引、任务标签和时间网格一致，raw 与 dataset 检查前后哈希不变。
- 两对分别比较，详细减轻量的平均周期差为 **−0.001664 ms / +0.003246 ms**，p99 差为 **−0.089573 ms / −0.169730 ms**；未看到一致的周期变慢，不能将小样本差异解释为因果加速或精确零开销。详细第 3 次保留 **1 个 >30 ms 周期，max 34.002254 ms**；其他录制稳态均无 >30 ms，六次均无 >40 ms，不隐藏长尾或设置事后阈值。
- 正常 detailed-2/3 稳态各 900 次 sample append，成功 enqueue/dequeue/add_frame 的全会话次数分别等于各自 1,240/1,431 个保存帧；无 Full，队列观测峰值 1/容量 90。桥接 command 平均约 19.583 ms，action 0.161/0.174 ms，observation 0.317/0.333 ms；append 0.076/0.080 ms，save_episode 356.111/418.445 ms。队列 get 包含等待，RPC 包含 IPC/worker/设备，append 包含子调用；这些总耗时不可相加或冒充纯序列化/写盘细分。细分统计见汇总 JSON。
- **detailed-1 事件**：实际任务名仍为 `PiPER-X GELLO teleoperation`，不重写标签。保存 1,469 帧成功，约 62.246 秒后开始的 command RPC 在 1,001.102 ms 后超时，最终 phase=error；整份终端日志没有 POST stop，记录了 Ctrl+C。用户回应“是，可能直接按了 Ctrl+C”。终端时序与活动跟随期间 Ctrl+C 后约 1 秒超时相符，推断为退出顺序相关，但未捕获信号投递，根因尚未严格证明。该次数据/保存窗口回读 PASS，退出回零日志达到 0.997° 残差。它不是任务命名导致的数据损坏，也不算正常退出通过；没有做真机故障复现或修复。
- 六次启动回零、对齐、退出回零均有 reached 日志，最大残差 1.09525°，在原 1.1° 内。CAN 前后同 ifindex，错误/丢弃/bus-off 等增量均 0，范围为完整生命周期。收尾只读预检通过：原源码/工具/配置哈希不变，共享锁及 6001/18086 空闲；没有打开硬件。
- **本地完整副本**：六次 attempt、对应 `data/raw/app/<session>/` 和 `data/logs/<session>.log` 共 180 个采集证据文件、11,465,674 字节已回传并逐项大小/SHA256 验证；包括异常运行。新增回读报告、汇总、事件记录与离线脚本另纳入 `reports/b5-web-a-artifacts-20261117.json` 并校验两端副本。此组无图像数据，不能代替此前 RGB-D 大文件的 B7 完整交接。
- 证据根目录：`data/p0/p0-20261112T091106Z/`。汇总 `reports/b5-web-a-summary-20261117.json`（MEASURED_REDUCED_REPETITIONS），异常 `reports/b5-web-a-detailed-1-incident-20261117.json`，各 attempt 的 `analysis.json` 和 `numeric-readback-20261117.json`。新增只读数值入口复用冻结 B4 comparator，不改原检查器或采集文件；Ruff 通过。生产源码、标定、限值、依赖与基线未改，无提交/推送。
- 下一步为 Web-B/C 准备与实测、离线数据路径细分、B6 回放及 B7 总交接；**Web-A 复测要求已由用户撤销，不再以补测阻塞后续**。整轮 B5/B6/P0 仍为 INCOMPLETE。


### B5 Web-B 固定 RGB 预览组已准备（2026-11-17）

用户请求下一组操作。Web-B 启动脚本已放到实验机，**准备时只完成软件与合成验证，之后的三次真实测量见下一节**。Web-A 已接受两对收尾，不再安排其补测。

- 入口：实验副本内 `bash data/p0/p0-20261112T091106Z/b5-tools/web-b/run-b5-web-b.sh`。默认使用 detailed，复用冻结的 Web-A probe/runtime wrapper/analyzer，独立创建 `measurements/web-b-detailed-*/`。RGB-D 配置沿用 `configs/web-rgbd.toml`，只改本次输出目录；robot/gello/safety 与 Web-A 完全一致，原 1.1° 容差不变。相机仍为 auto，实际 profile 按本轮元数据记录。
- 人工方案：独立启动 **3 次，每次录制约 40 秒（至少 36 秒）并保存**。仅一个浏览器标签页，录制全程可见且固定 RGB 预览；启动前设置 `P0 Web-B 1/2/3` 并手动确认，following 后开始采样，保存后等 saved=1/following，再停止跟随、等 completed/回零，最后终端 Ctrl+C 并等待统计退出。每次重跑同一命令；不增加丢弃操作或额外 light/detailed 配对。
- 新合成验证 **1 项通过，4.22 s**：真实模拟 worker、单个 ASGI RGB WebSocket 连续 40 帧 JPEG、RGB-D 保存、数值和原生深度的逐帧 LeRobot 回读、探针/raw 时间对应、正常关闭。模拟尺寸 64×48，不代表真实相机或性能通过。4 条上游 FastAPI/LeLab 弃用警告保留。原 11 项共享探针自检与源码哈希仍适用，本轮没有重复整套或访问硬件。
- Shell 语法、Ruff 和远端 `--check-only` 通过；共享工具、源码、新 helper、RGB-D 配置哈希一致，节点权限/磁盘/共享锁/6001 与 18086 预检通过。新 manifest SHA256 `b3b5b112b804319b2012ca31cf68007b2c16d0d3759aca2d71bd51bb6ef41721`，helper SHA256 `e59715c071961e5520262fbc49bfc2bb03a74ea48d855dbe4c05bc571006cc60`。
- 准备报告 `reports/b5-web-b-preparation-20261117.json`；工具及 `logs/b5-web-b-rgbd-proof-20261117.*`、`logs/b5-web-b-preflight-20261117.log` 已在两端保留。RGB-D 真实数据回读、camera profile/匹配与稳态结果待现场运行；Web-A 的无相机开销对照不能替代 RGB-D 负载下独立开销隔离，保留此限制。B5/B6/P0 未标完成，生产源码未改，无提交/推送。


### B5 Web-B 三次完整核验（2026-11-17）

**Web-B 三次记录、保存、正常退出及完整 RGB-D 回读通过。** 用户报告完成；每次日志只有一个 `mode=rgb` WebSocket 接受记录，并有 record/save/stop 各一次及 stop 之后的终端 Ctrl+C。未独立记录浏览器可见性或渲染 FPS，不把连接日志当作显示帧率。

| attempt | 录制跨度（s） | 保存帧 | 控制 Hz | 周期 p99 / max（ms） |
| --- | --- | --- | --- | --- |
| web-b-detailed-FawQcA | 44.380409 | 1332 | 49.861035 | 22.064510 / 28.454903 |
| web-b-detailed-nAbfZI | 45.873733 | 1377 | 49.855646 | 22.075270 / 26.191963 |
| web-b-detailed-qBUqAy | 50.851548 | 1527 | 49.860502 | 22.519782 / 27.849428 |

- 三次均覆盖 5 秒稳定期＋固定 30 秒窗口；原生分析/退出/完整回读均返回 0，控制连续、raw 与逐周期时间对应、probe_dropped 全为 0。稳态无 >30 ms 周期；>20 ms 次数 828/831/867，完整抖动及连续超期统计保留，不将普通轻微超期隐藏或设新阈值。
- 相机实际 **640×360@90 RGB8＋原生 Z16**，auto 未回退；数据集仍为 30 FPS。逐帧回读 **1,332/1,377/1,527，共 4,236 帧**，数值与深度最大误差 0，主机时间误差 0；任务名 `P0 Web-B 1/2/3` 均一致。RGB 有损 MAE 均值 1.964/1.954/1.736（0–255），仅报告实测值。
- 最大颜色/深度匹配差分别为 21.654/21.655、21.677/21.678、21.870/26.961 ms，均小于原 50 ms；保留帧无重复、逆序或时钟倒退。90 Hz 源选取为 30 FPS，帧号间隔不能直接称为硬件丢帧。三次在启动时出现深度 frame counter reset，原入口重新预热后继续；警告完整保留，录制阶段没有该倒退。
- 队列成功入/出及 dataset add_frame 数等于保存帧，Full=0、观测峰值 1/容量 90。save_episode 为 16.585/15.619/16.962 s，单独列为保存阶段，不混入稳态控制。三处定位均 reached，最大残差 1.097° 在原 1.1° 内；CAN 整个生命周期错误/丢弃/bus-off 增量 0。
- raw 共 **4,885,737,650 字节**，与录制后的原分析哈希及回读前后清单一致；数据集前后也一致。完整索引 `reports/b5-web-b-artifacts-20261117.json` 含 **8,580 文件 / 5,577,261,179 字节**；其中 **102 个小型证据文件 / 13,730,484 字节**已回传且 SHA256/大小一致，索引另存。RGB/深度原始数组、视频及大型数据 Parquet 保留 RON；本地 raw/dataset 为部分副本，不能直接全量加载，B7 仍未完成。
- 汇总 `reports/b5-web-b-summary-20261117.json`；各 attempt 的 `rgbd-readback-20261117.json`、前后清单及日志；本地校验 `reports/b5-web-b-local-copy-20261117.json`。独立 `b5-tools/check_web_rgbd_saved.py` 仅在离线内存中将冻结 B4 的“保存＋丢弃”协议门槛适配为本组“单段保存”，数值/RGB/深度/时序内容检查不变；原 B4 checker、raw、源码均未修改。Ruff 通过。
- Web-B 通过后，按用户“全部满足就开始下一项”的要求准备 Web-C。未为验证重复运动，未作新的硬件故障注入；完整 B5/B6/P0 尚未通过。

### B5 Web-C 无预览组已准备（2026-11-17）

- 保持 Web-B 的 RGB-D auto 配置、控制 50 Hz/数据集 30 FPS 和 detailed 探针，独立 `web-c-detailed-*` 目录。服务命令 `bash data/p0/p0-20261112T091106Z/b5-tools/web-c/run-b5-web-c.sh`；原网页仍由操作员设置任务名、勾选确认并启动跟随，所有原后端 guard 不变。
- 进入 following 后关闭所有采集网页；在第二个 robot 终端执行 `uv run --frozen --no-sync python data/p0/p0-20261112T091106Z/b5-tools/web-c/capture_no_preview.py`。助手核对当前新会话与本次输出目录，等待浏览器 TCP 连接消失后，自动录制约 40 秒、保存、等待保存完成、停止并等待 completed；最后操作员在服务终端 Ctrl+C 并等待统计完成。共三次独立运行，不做丢弃。
- 助手**没有启动硬件或自动确认接口**，只向已人工启动且身份匹配的当前会话发送 record/save/stop；状态以原网页相同的名义 1 Hz 轮询。处理中断或异常时尝试原停止路径，保留失败报告和数据，不自动重试、丢弃或控制其他会话。记录开始/结束、命令时间与窗口前后 TCP 快照；这些是两个快照，不能声称连续监控。
- 最终版本合成验证 **3 项通过（6.06 s，4 条上游弃用警告）**：真实模拟 RGB-D worker 完整录制保存停止、拒绝其他 attempt、中断后停止且不保存/重启。Shell/Ruff、远端原源码/工具/配置/锁端口预检及 ss 解析检查通过，没有真实设备访问。助手最初 0.5 s 轮询版本也通过，核对原页面实际为 1 s 后统一到 1 s，并以最终版本重跑三个用例；两次日志保留。
- 证据：`b5-tools/web-c/` 和 `reports/b5-web-c-preparation-20261117.json`；最终 manifest SHA256 `85b6f7d1d14625fbae97ea82710f26bf515fa1b2240638e1c835791dff26882d`。`logs/b5-web-c-proof-final-20261117.*` 与 `logs/b5-web-c-preflight-20261117.log` 已回传。真实相机 profile 和无预览稳态结果等待现场运行；既有 Web-A 两对缩减决定不变。未改生产源码/依赖/标定/限值，无提交或推送。


### B5 Web-C 三次完整核验（2026-11-17）

**Web-C 三次保存、正常停止、服务退出及 RGB-D 全量回读通过。** 用户报告三次完成；第三次到达 completed 后服务仍在运行，用户依提示在终端 1 Ctrl+C 并确认统计完成，退出与分析均为 0。没有由代理发送运动或采集控制命令。

| attempt | 录制跨度（s） | 保存帧 | 控制 Hz | 周期 p99 / max（ms） |
| --- | --- | --- | --- | --- |
| web-c-detailed-5zYJE6 | 40.534417 | 1217 | 49.862149 | 22.098319 / 27.703482 |
| web-c-detailed-OluGhp | 40.535108 | 1216 | 49.857334 | 22.031554 / 26.753985 |
| web-c-detailed-k4lz70 | 40.553663 | 1216 | 49.855572 | 21.991160 / 25.548154 |

- 三次均覆盖 5 秒稳定期＋固定 30 秒窗口，逐周期 raw 交叉核对通过、探针丢弃为 0。稳态 >20 ms 次数为 821/838/846、最长连续 3/4/4，>30 ms 与 >40 ms 均为 0；完整 phase/RPC 统计保留，不能将稳态结论扩大到整个生命周期。
- 无预览证据：每次助手录制前与窗口后 TCP 连接快照为空，服务日志在 record 后没有新 WebSocket 接受记录；原网页启动前的 RGB 连接保留。此为快照与服务日志，不声称连续监控。第一次助手因 Firefox 页未关闭而拒绝，失败报告 events 为空，未发 record/save/stop；关页后同一会话完成正式录制，较长的录制前 following 与稳态分开统计。
- 相机身份/profile 与 Web-B 一致：**640×360@90 RGB8＋原生 Z16**，数据集 30 FPS。**3,649 帧**完整回读，数值/深度/主机时间最大误差均 0，任务名 `P0 Web-C 1/2/3` 正确；RGB 有损 MAE 均值 1.759/1.720/1.715（0–255），不另设任意阈值。
- 三次相机匹配差最大 21.515114/21.304988/21.528811 ms，均小于原 50 ms；保存帧没有重复、逆序或时间倒退。90 Hz 到 30 FPS 的帧号间隔不算作已证明硬件丢帧。启动时深度计数器复位后原入口重新预热的警告完整保留。
- 入队/出队/add_frame 成功数与帧数一致，Full=0、队列观测峰值 1/容量 90；空队列等待单独保留。save_episode 为 15.029/14.503/13.318 s，不并入稳态控制。三处定位均 reached，最大残差 1.081° 在原 1.1° 内；CAN 同 ifindex 全生命周期错误/丢弃/bus-off 增量为 0。收尾 check-only 核对源码/工具/配置哈希、共享锁及 6001/18086 空闲，通过且未打开设备。
- Web-B 与 Web-C 的控制频率均约 49.86 Hz；本轮 p99 范围分别 22.065–22.520 / 21.991–22.098 ms，有重叠。顺序运行和不同手动动作不能严格隔离预览因果开销，也不能证明零开销；RGB-D 负载下探针开销未单独隔离。
- raw 共 **4,208,693,393 字节**，与录制分析及回读前后清单一致，数据集前后也一致。索引 **7,415 文件 / 4,825,174,191 字节**；**111 小型证据文件 / 16,200,566 字节**已回传并逐项 SHA256/大小一致。完整 RGB-D 数组、视频、大型数据 Parquet 仍在 RON；本地 raw/dataset 仅部分副本，B7 仍未闭环。
- 证据：本轮 `reports/b5-web-c-summary-20261117.json`、`b5-web-c-artifacts-20261117.json`、`b5-web-c-local-copy-20261117.json`；各 attempt 的 `analysis.json`、`no-preview-control-*.json`、`rgbd-readback-20261117.json` 与日志。索引 SHA256 为 `e68851bf977854d46cd9e88b32b39423aaaf346ee164a7eee1f5994446a28793`。新增独立离线 `summarize_web_c.py`、`archive_web_c.py`，复用冻结回读器；Ruff 通过。初次检查命令因非交互 PATH 和 checker 路径错误未启动回读，修正后通过，错误日志保留，非产品故障。
- **B5 核心运行矩阵已测完，完整 B5/P0 尚未完成**：离线序列化/复制/编码/写盘细分、B6 驱动输入黄金序列和确定性回放、最终 B7 交接仍待做。现有 Web-A 两对决定不变，不要求重复这些已验收采集。未修改生产代码、依赖、标定或安全参数，无提交/推送。

### B5 离线路径完成、B6 现场工具已准备（2026-11-17）

- 按用户“无需人工的步骤直接完成，直到需要人工再给步骤”的授权，完成独立离线计量、黄金哈希复核、B6 工具自检和阶段报告。远端仍为 `640aad8ea896b37257c5c7fe8de46220f61cac84` / 0.2.2，无生产源码、依赖、标定变更，无 commit/push；本地 P2 工作区保留。
- **B5 离线路径 PASS**：CLI/Web 分别使用既有黄金数据的 32 个真实 RGB/Z16 样本循环重放，微阶段每轮 1,000 样本、各三轮；同进程完整 writer 预热后，三轮各 30 秒、每流 900 帧。CLI 数值 50 Hz、图像 30 FPS，Web 保存采样 30 FPS；失败数均为 0。原始计量 CSV、源码/配置/输入哈希、阶段分位数与字节率完整保留。
- CLI 完整 writer 为 30.0074–30.0082 秒、44.0157–44.0169 MiB/s；Web 为 37.4752–37.9799 秒、26.3386–26.6932 MiB/s，包含单次 save_episode 7.4700–7.9718 秒。这是名义 30 FPS 输入负载，不是磁盘最大吞吐；CLI/Web profile、PNG/NPY、fsync 及 LeRobot 边界不同，不直接排名。RPC 使用原客户端和合成 peer，pickle 协议 4；不能当真机请求延迟。CLI 真机独立 RPC 计时已附在 B6 同次采集，不增加请求。
- 最终结果只取 `scratch/offline-{cli,web}-warmed-20261117/`。早期 IPC 路径过长、Web 导入路径错误、同进程 writer 暖机不足的运行及工具版本均保留。实验在独立 scratch，与 raw 同文件系统，单入口 24 GiB/900 秒边界；最终两入口各占 8,818,968,571 / 6,650,471,584 字节。没有删除旧 scratch 或改写黄金数据。
- 离线输入所在 CLI raw（1,140,324,685 字节）和 Web-C raw 全文件哈希再次一致；B4 两入口 raw 也与既有清单一致，并补齐 raw/dataset 各一份清单，共四份。`reports/b4-golden-artifacts-20261117.json` 给出关联、repo_id、大小、哈希与保管位置；清单已返回本地。完整独立大数据副本和最终保管责任仍待 B7 收尾。
- **B6 READY_FOR_OPERATOR，真实序列/回放 NOT_RUN**：`b6-tools/` 在构造前观察 driver 原始返回、嵌套调用及初始化/平滑/映射/限幅状态；不增加设备读取或扭矩写入。保留原 CLI 目标和 yes、共享锁及清理；正常对齐后 40 秒在下一次读之前触发原退出流程，待清理结束才写数值 fixture。离线 driver 按顺序消费输入，禁止硬件回退，检查所有有状态输出，预定 atol=1e-12 / rtol=0。
- 本地工具 **7 passed**；远端根/GELLO/记录/相机/清理定向测试 **75 passed**，Web 合成保存/丢弃/预览 **2 passed**（4 条既有弃用 warning）。绝对/相对合成夹具从 JSON 文件在独立进程回放，最大误差 0；覆盖偏移展开、夹爪裁剪、状态平滑、错误输出/输入耗尽拒绝、探针溢出可见、异常保持及原释放路径。三对 2,000 act 的合成开销对照平均增量 0.0215–0.0230 ms，最大 5.2635 ms 异常值保留；不等于真机 deadline 保证。
- B6 no-device check-only **PASS**，源码/配置/工具哈希、互斥锁和端口可用；manifest SHA256 `bd70cfec935ed99c74342903dba064e10bfed82c5f802bd8c9bb1182a49e0a0a`。运行命令为 `bash data/p0/p0-20261112T091106Z/b6-tools/run-b6.sh`，需用户在 robot 交互终端启动。正常 following 后静止 5 秒、小范围平滑往返/夹爪约 30 秒、静止 5 秒，自动回零并离线回放；不需要 R/S 或网页。
- 本地逐文件核验：B5 离线 **96 文件 / 16,899,397 字节**，B6 准备 **14 文件 / 391,870 字节**；相应索引 SHA256 为 `50d06189b0e6db8f9606da4c8cde2ebdbf7d88564c24d8294064349609495eb8` / `9462f44b90f68bf28ac0b8f12fab88fa4e427cb206d3462a079b9a47c1df6e91`。证据见 `reports/b5-offline-summary-20261117.json`、`b6-preparation-20261117.json`、各 local-copy 报告和 `logs/b6-*.log`。
- 已生成阶段性 `reports/P0_REPORT.md`、`artifacts.json` 和本追加片段；报告直接列出各有效 run 周期分位数、抖动、超期数及三轮微阶段/完整 writer 数据。**P0 仍 INCOMPLETE**，下一步只需一次 B6 现场采集；随后代理核验真实回放、RPC、退出/CAN 并完成 B7。Web-A 两对结果决定不变，不重复已验收组；CLI Tk 预览继续按用户要求留到以后。

### B6 真机序列、双端回放及 B7 证据收尾（2026-11-17）

- 用户报告本次运动、正常回零及结束提示均正常；因人工计时偏差，软件计时结束时仍在操作。对应 `gello/capture-o1PygD`，15:08:17–15:09:07（Asia/Shanghai），CLI 退出码 0、三次原 JS target reached；收尾 no-device 检查通过，锁和端口空闲。未为核验重启任何硬件。
- **B6 PASS，操作节奏偏差保留**：共 9,995 条调用事件、1,998 次 driver 返回、1,995 次 leader.act，其中持续跟随 1,994 次，首末跟随样本跨度 39.988192 秒。前 5 秒六轴最大跨度 0.087891°；5–35 秒六轴跨度约 18.809/8.789/8.350/16.260/18.633/15.820°，均有正反向变化，夹爪约 0–1。末 5 秒 J1 仍变化约 8.701°，不标作静止。手册 B6 所需静止、变化、反向和夹爪行为已覆盖，末段静止不完整不要求重采。
- 原采集后的回放、远端独立复算、回传后的本地冻结源码回放均 **PASS，最大绝对误差 0**（预定 atol=1e-12 / rtol=0）。调用顺序/读取数/构造状态/平滑/映射/输出完整匹配，无 fake fallback，观察错误和丢弃均为 0；采集原文件哈希前后一致。本地使用 `b6-tools/source-snapshot/`，不把 P2 工作区源码混入 P0 结论。
- 5–35 秒窗口共 1,495 次 act，49.8413 Hz；act 周期 p50/p95/p99/max 为 20.0584/20.1697/20.2354/20.5995 ms，>30/>40 ms 均为 0。这是 act 入口时间，不冒充 CLI 原生 command-start 周期。
- **B5 CLI 独立 RPC 补充完成**：同窗口 command_joint_state/get_observations 各 1,495 次，均成功；mean 分别 0.483634/0.220653 ms，p99 分别 6.132476/0.424165 ms，max 分别 6.251961/0.517131 ms。仅一次无相机、开启观察的 B6 补充，不当作三轮原生 B5 录制或硬件采样延迟。启动首次 num_dofs 有 RuntimeError、随后成功；结合原 wait_for_server 只重试超时，符合启动等待，异常原消息未记录。跟随与清理 RPC 无失败，CAN 同 ifindex 的错误/丢弃/bus-off 增量均为 0。
- 完整数值 fixture、日志、核验工具和冻结源码快照 **99 文件 / 12,049,664 字节** 已返回本地并逐项 SHA256/大小核验。索引 `reports/b6-capture-artifacts-20261117.json` SHA256 `858e03222c9f8a1744aa85ad0cc966be14276a59d37ebf23fb924997bccf8708`；原序列 SHA256 `069b40ba6ba246cd2099e53d316d9894de201d7047682893d018f6e9bfea906d`。证据为 `b6-capture-verification-20261117.json`、`b6-capture-local-copy-20261117.json`、`b6-local-frozen-replay-20261117.json`。
- **B4 完整黄金备份已补齐**：CLI/Web 两入口 raw/dataset 共 **5,892 文件 / 3,594,483,222 字节**，打包回传为 `archives/b4-golden-complete-20261117.tar.gz`（1,229,839,981 字节）。逐文件路径/大小/SHA256 全部与四份冻结清单一致；包 SHA256 `06b437ab765e2678b6c90b47ee5a7d5e71bb0de77fdd1aa8b3cb3a7c311af301`，原数据保留 RON。恢复时解压至新空目录并复核清单，不覆盖 raw；报告 `b4-golden-complete-local-copy-20261117.json`。B5 大型测量图像仍在 RON robot 账号，逐组清单/回读和小型证据在本地，与完整 B4 黄金备份分开说明。
- P0 总报告 `reports/P0_REPORT.md` 与关联索引 `artifacts.json` 已更新为 **B2–B6 验证完成、B7 等待整轮用户验收**。现有 Web-A 两对决定、启动/退出异常历史、观察开销与短测限制均保留；CLI Tk 预览按用户要求以后单独处理，未增加硬件测试。新增核验/本地回放脚本 Ruff 与格式检查通过；不修改生产逻辑/依赖/标定，不提交、不推送，阶段仍 TESTING。

### P0 最终验收完成（2026-11-17）

- 用户在最终 B7 验收请求后明确回复“直接完成最后的验收吧”。据此记录 **P0 COMPLETE、B7 PASS**，回执为 `data/p0/p0-20261112T091106Z/reports/p0-final-acceptance-20261117.json`，记录时间 2026-11-17 15:34:54（Asia/Shanghai）。无需再次确认或补采。
- 验收对应冻结基线 `640aad8ea896b37257c5c7fe8de46220f61cac84` / 0.2.2。B2–B6 结果、Web-A 两对决定、历史异常、B6 末段仍运动的节奏偏差、测量边界和待验证项全部保留。
- B4 两入口完整黄金备份已逐文件验证，B6 真实夹具在远端与本地冻结源码回放误差均为 0；B5 大型测量 RGB-D 仍由 RON robot 账号保留，完整清单、回读及小型证据在本地。上述保管安排随总报告验收。
- 总报告 `reports/P0_REPORT.md`、`artifacts.json` 和任务账本已更新。原 `archives/p0-evidence-final-20261117.tar.gz` 保持不变；验收补充包为 `archives/p0-acceptance-20261117.tar.gz`，清单及双端核验见 `reports/p0-acceptance-artifacts-20261117.json`、`reports/p0-acceptance-package-20261117.json`，接续历史包内待确认状态。
- 本轮仅完成文档与归档；未新增硬件运行、生产修改、提交或推送。CLI 桌面预览等保留为后续项，项目阶段仍为 TESTING。


### 到位基线统一为 1.5°（2026-11-17）

- 用户在复核 P0 的 Web 1.024° 残差后明确要求：机械臂误差较大，统一采用 1.5° 的误差基线，不再继续容差实验。决定见 [ADR 0005](../decisions/0005-position-tolerance-baseline.md)，取代先前统一 1.0° 的目标。
- CLI `move_js`/`movejs`、Web 默认配置及新 runtime 的默认每轴到位判据同步为 ≤1.5°；保留显式覆盖和超差报错。原始反馈、标定、限位、目标步长、新鲜度与权限保护不变。
- P0 报告、配置、黄金数据、源快照、1.0°/1.1° 原判据及实测残差保持不变，P0 COMPLETE 状态不变。软件配置变更不写成新的真机实测结果；本次无硬件运行，不安排专门容差复验，不提交、不推送。
- 软件验证：`make verify UV_RUN="uv run --frozen --no-sync"` 通过：Ruff lint/format、Shell 语法与双语文档检查通过，根与契约 **231 passed in 100.00s**，包括真实 converter 集成回读、1.4° 接受/1.6° 拒绝、仿真退出回零和独立看门狗。复用现有环境执行，未同步依赖；日志为 `/tmp/agilex-tolerance-verify.log`。
- 初次扩大回归为 114 passed / 2 failed，均为新 P2 仿真 HAL 启动时 bind 后再 chmod 的权限竞态，与容差数值无关。确定性测试先复现 socket 初始 0755，修复为 bind 时按 0600 创建，完整回归中的该测试与原失败用例均通过；客户端权限检查未放宽。P2 崩溃测试另只整理导入和长行排版。
- P0 验收索引内九个文件和 B6 真实序列 SHA256 再次核对不变；本轮不宣称 P2 已整体完成。


### P2 统一 runtime 仿真软件验收完成（2026-11-18）

范围与任务勾选见 [P2 计划](../specs/architecture-p2-plan.md)，完整评审、时序调查与验证限制见 [P2 评审记录](../reviews/architecture-p2-review-20261118.md)。P0 COMPLETE 及其冻结证据不变，项目阶段保持 TESTING；未实施或验收 P3～P7。

| 验收项 | 本轮实际结果 |
| --- | --- |
| 分层与配置 | 共用 `agx_transport`，runtime 不导入硬件；分层 TOML、每流 role/monitor_when、映射、1.5° 默认、边界/排空配置通过 |
| 录制与离线检查 | full/sampled、纯传感器/两相机+力、原生 RGB8/Z16、尾丢帧/epoch/边界、选择审计、命令实际观测重算通过 |
| 故障与归属 | 独立边界/写盘/撤权期限、失败终态不可逆、optional 隔离、外部 HAL 停止后可再录制、正常/故障退出与停止后不发新目标通过 |
| 服务与进程 | 私有 IPC owner/heartbeat、子进程看门狗、管理 REQ 独立于 PUSH/SUB 数据通道、已有 HAL 不被 kill 通过 |
| 完整项目检查 | `make verify` 通过，**250 passed in 66.91s**；Ruff、Shell 语法与双语文档/链接检查通过，包含真实 converter 回读 |
| CLI 独立进程 | sensors/full/sampled/extended 四组均采集、检查、回放、退出通过，样本数 161/136/78/287，命令数 0/26/26/26 |
| 包与锁 | `uv lock --check --offline`、`uv build --offline` 通过；新 wheel 在 checkout 外导入、HAL 采集及 70 条样本检查通过 |
| 独立评审 | 一次整体只读评审，无 Critical/Minor，五项 Important 已用 RED→GREEN 修复；额外停止保护与管理 RPC 回归通过 |

- 本轮调查中 CLI 曾出现 50ms sampled skew / 60ms leader 新鲜度保护停止，失败 raw 保留 partial。发现管理 RPC 每次额外创建 PUSH/SUB/context，修复为进程 context + 每请求独立 REQ 后，四组功能验收通过；未调大偏差或新鲜度期限，不将短测通过写为持续调度保证。正常读写测试使用正式 5s drain；丢帧/阻塞/完整性超时用例仍显式用 0.3s，故障保护未削弱。
- P0 支持保留隔离写盘线程/ZMQ，P4 须测新 raw 持续吞吐和控制周期；真实多相机 90 FPS、长时内存、LeRobot 导出期限、PiPER-X 断令及真机故障注入仍未验证。wheel 使用现有 contract/pyzmq/msgpack 环境，不称全新 PyPI 安装。既有 uv-build 范围警告非阻塞；未升级依赖。
- 最终版本为根 **0.2.3 未发布开发版**，工作分支 `dev-architecture-p2`，HEAD 仍为 `640aad8`，六个 gitlink 未变；预存 GELLO 三个排版修改保留。本轮无硬件访问，无 commit/push/merge。早期失败、RED、最终日志、CLI/wheel JSON 与 SHA256 清单保留在本地 `.superpowers/sdd/architecture-p2-plan/`，正式操作说明见 [仿真指南](../../../docs/zh/runtime-simulation.md)。
- 下一步按 P3 包装现有驱动，先明确只读握手/准备副作用/授权边界；PiPER-X 断令行为保持 unverified，相关故障注入须先取得对应证据。不改变用户已决定的 1.5° 基线，不追加容差实验。

### P3 真实 HAL 软件验证（2026-11-19）

- PiPER-X、GELLO、RealSense 独立 HAL 接入统一 runtime；旧 CLI/Web 路径保留。真实跟随须查看目标并在终端确认；退出回零需新鲜有效反馈和六轴仍使能，清理不得重新使能。
- `make verify` **294 passed in 84.24s**；SDK/GELLO/相机分别 **63/12/59**，SDK 与相机 Pyright 零错误，冻结锁、构建、三个独立解释器和 checkout 外四种模拟采集/检查/回放通过。冻结 B6 的 1,996 次 `Agent.act` 数值回放通过；实际调用频率待现场对比。评审发现、离线凭据与限制见 [P3 评审记录](../reviews/architecture-p3-review-20261119.md)。
- 软件验证时，根候选 `0.2.4` 位于 `dev-architecture-p3` 工作区，尚未提交，也未访问硬件。用户随后授权将该候选及必需子模块提交先分发到 GitHub，供实验机验收。以交接单的完整 SHA 为准；该例外不授权发布 `main` 或代替实测结论。
- 真机 **NOT_RUN**。按 [P3 真机手册](../specs/p3-hardware-runbook.md) 核对 DISCOVER 与 PREPARE、经授权最小运动、正常采集和 P0 时序。断令保持 `unverified`，对应故障注入未开始。1.5° 基线不变，不增加容差试验。
