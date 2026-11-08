# TESTING：当前测试计划与检查点

更新日期：2026-11-08（Asia/Shanghai）。当前阶段由根 `.ai-stage` 指定。

## 范围与证据口径

当前目标是验证 Python 3.12/uv 基线下的 CLI、浏览器采集、GELLO、PiPER-X 和 D455F。第 1–4 项已有结果，接下来先完成远程图形访问与预览验证，再由操作员确认后进行第 5/6 项。末端力估计仍为后续研究，不能混入当前通过项。

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

目标主机：`robot@10.192.206.166`（RON），项目：`~/hezijue/agilex-controller/`。此前安装为 uv 0.13.6、uv 管理的 CPython 3.12.16、六个独立 `.venv`。密码、token 和私钥不写入本文。

## 六项计划及验收

| 项 | 范围 | 验收 | 当前结果 |
| --- | --- | --- | --- |
| 1 | 环境准备 | 六环境 frozen 依赖可用，CLI 帮助/关键二进制导入正常，普通终端可找到 uv，用户串口权限有效 | 已完成；最初专用 PATH/临时串口组的缺口后续已修复 |
| 2 | 软件回归 | 根与五个子模块测试、现有 lint、SDK/camera Pyright、逐个 Shell 语法及帮助、lock/build/wheel 导入 | 此前远端 279 项通过；本轮规范化检查见下文，不用旧计数冒充新运行 |
| 3 | 模拟采集 | 独立端口/数据根，启动、采样、保存、丢弃、停止，四预览及真实 LeRobot 回读，无硬件访问 | 已完成；仅合成低分辨率验证 |
| 4 | 真机只读 | 主从设备身份、主手编码器/标定核对、CAN/从臂反馈、相机 profile/标定，不使能/运动/开流 | 已完成；夹爪端点等已知限制仍保留 |
| 5 | 最小运动 | 操作员确认后先无相机回零、对齐、小范围跟随、退出；分别按入口实际容差验收 | 待正式验收；用户运行片段不能代替完整记录 |
| 6 | 短时真机采集 | CLI 相机录制及浏览器各先约 10 秒，保存/丢弃、关节/RGB/Z16 回读、质量报告与清理正常 | 待执行/验收；不能从只读或模拟推断 |

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

- GELLO by-id `FTBM4Z46`，57600 baud，1–7 号响应；严格探针发送 7 PING、105 READ，读取前后七轴扭矩均为 0。没有以 `agilex-controller read` 冒充严格只读。
- 主手映射六轴约 `[0.176, 0.088, -0.967, -18.369, -4.834, -2.549]°`。夹爪原始约 203.115°，配置 159–201°，未截断为 1.05036、输出被截到 1；完整端点待现场复核。
- D455F SDK 序列号 `341522300932`、USB 描述符序列号 `250343061381`、固件 5.17.0.10、USB 3.2；640×480@30 和 640×360@90 的 RGB8/Z16、内外参和约 0.001 m 单位有效。该阶段没有开流或测速。
- USB-CAN 最初未枚举；换线后 candleLight `1d50:606f`、序列号 `002C00374759530920353131` 出现并生成 can0。用户单独授权运行 `config_can.sh can0 1000000 100`，接口保持 UP、1 Mbit/s、队列 100。
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
| P0 | Windows 实际连接 RON 与桌面状态 | 用户确认能进入桌面；锁屏/黑屏则收集 RDP 日志，按授权排查，不擅自解锁或修改现有会话 |
| P0 | 桌面相机预览 | 在明确显示会话中先用合成图像测试 Tk 预览；物理开流需对应授权。SSH 直接运行保留 `--no-camera-preview` |
| P0 | 第 5 项最小运动 | 获对应授权和现场确认后，记录入口/命令、六轴目标/起止反馈/残差、容差、方向、异常与退出；先不带相机 |
| P0 | GELLO 夹爪端点与方向 | 由操作员检查完整行程及从臂开合对应，保留原值直到确认，不自动标定或调整 offset |
| P1 | 第 6 项短采集 | CLI 与浏览器分别保存/丢弃约 10 秒，回读 RGB/深度/关节、时间审计和退出结果；留存 session 路径 |
| P1 | 预览故障诊断改进 | 目前父进程只显示通用错误，原子进程异常未结构化传播。考虑在运动前验证预览启动，并保留真正错误；本轮未改运行时代码 |
| P1 | 只读 CLI 语义 | `read` 实际关闭 GELLO 扭矩，文档已纠正；是否新增严格只读入口待决定，不把它视为已有能力 |
| P1 | 持续性能与时序 | 实体 D455F 全分辨率预览/录制、磁盘、USB、多标签、时间戳质量与 CAN 丢包趋势；短模拟不替代 |
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
