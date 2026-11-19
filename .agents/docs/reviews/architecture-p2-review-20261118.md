# P2 整体评审与验收（2026-11-18）

状态：P2 仿真软件验收完成；独立评审的五项 Important 已修复，最终完整回归通过。范围为 `dev-architecture-p2` 上全部 tracked/untracked P2 工作树，基线 `640aad8`；无 commit/push/gitlink 更新或硬件访问。

## 独立评审与修复

由 fresh-context `p2_final_review`（gpt-6-astra/high）完成一次整体只读评审，无 Critical、无 Minor；按技能要求执行一次集中修复，不重复派发评审。提交门槛禁止临时 commit，因此使用完整工作树清单，原评审包在本地忽略的 `.superpowers/sdd/architecture-p2-plan/review-working-tree.md`。

| 发现 | 修复与回归 |
| --- | --- |
| 最终检查与 COMPLETE 赋值间，FAILED 可被覆盖 | 独立短时终态锁互斥转换；锁内无文件系统操作，失败后的迟到发布恢复 partial；`test_failure_at_final_publication_cannot_be_overwritten` |
| optional 缓存超差或 epoch 改变导致全局停止 | 选择层排除不可用 optional 样本，epoch 改变隔离本段并记录告警，不混合 epoch；`test_optional_camera_loss_does_not_stop_sampled_session`、`test_optional_epoch_change_is_quarantined_without_mixing` |
| existing HAL 被未保存活动段占用 | release/lease timeout/command timeout 冻结活动计数；新 owner 可开始下一段，旧 owner RPC 被拒绝；保留最近 16 个关闭段计数；`test_external_hal_can_record_after_unsaved_session_stops`、`test_revocation_closes_producer_episode_and_keeps_old_counts` |
| 短 sampled 段零数据也可完成 | 至少一个覆盖 required 流的有效选择；不足时明确失败；`test_sampled_without_a_selection_is_not_complete` |
| 检查器只核对哈希，漏验模式/描述完整性 | 无条件解析描述与策略，核对流统计、payload 类型/通道/编码、必需选择覆盖、重复引用和实际 skew；篡改后重建哈希仍拒绝；`test_checker_rejects_semantic_damage_even_with_matching_hashes`（9 类） |

上述回归初始为 15 failed/1 passed；“缺统计”原先已被引用检查拒绝，其余失败对应评审发现。额外发现并以 RED→GREEN 修复停止请求到达 actor 轮次中途后仍发送目标的问题，测试 `test_stop_during_actor_turn_does_not_send_another_target`。迟到 optional 数据进入写盘结束阶段的额外用例在修改前即通过，未据此改变生产逻辑。

## 时序调查与管理通道

第一次完整回归 248 passed / 78.72s 后，独立 CLI 出现过 sampled skew 超过 50ms、leader 超过 60ms 新鲜期限的保护停止；所有失败证据保留，不用后来的通过覆盖。诊断见本地 `/tmp/agilex-p2-{timing,extended-timing*,profile}.log`：一次接收轮次约 66ms，leader 年龄约 74ms；单次接收墙钟时间明显大于线程 CPU 时间。不能单凭这些短测把全部停顿归因于编码、机器负载或文件系统。

同时证实每个管理 RPC 额外创建 PUSH/SUB/REQ、新 context 及 I/O 线程；这与管理通道职责无关。改为进程级 ZMQ context，每次请求只创建独立 REQ socket，socket 不跨线程共享，超时仍独立。`test_management_rpc_does_not_open_command_or_sample_channels` 先失败（实际 PUSH/SUB/REQ），后通过。优化后四组 CLI 在原始保护阈值下均完成；不由一次通过推导持续调度保证。

正常读写用例改用正式 5 秒 drain 默认；此前任意 0.3/0.5 秒成功路径期限会受本机 fsync 波动影响。丢尾帧、阻塞写盘和阻塞 inventory 仍显式使用 0.3 秒注入期限，边界共享期限断言不变；未放宽生产配置、源新鲜度或偏差上限。相关 recording/review/session 测试 40 passed / 16.36s。

## 独立 CLI 验证

每组独立进程运行 0.5 秒，独立数据根和锁，session 正常退出、主错误为空、cleanup_errors 为空。检查与回放均再次通过，无物理设备。

| 组合 | 流 | raw 样本 | 命令 | 回放条数 |
| --- | --- | --- | --- | --- |
| sensors | 5 | 161 | 0 | 161 |
| teleop-full | 6 | 136 | 26 | 26 |
| teleop-sampled | 6 | 78 | 26 | 26 |
| extended | 9 | 287 | 26 | 26 |

传感器组回放样本，其余组重算并回放实际命令；完整路径/计数在本地 `.superpowers/sdd/architecture-p2-plan/cli-validation.json`。这是 8×6 假图像的功能测试，不是 P0 性能对照或真机吞吐验收。

## 验证与限制

- `make verify`：Ruff lint/format、Shell 语法、双语文档与本地链接检查通过；根与契约 **250 passed in 66.91s**。包含真实 converter 数据集回读和所有新 P2 故障/IPC 回归；根 mypy、coverage 门槛、pre-commit 未配置，不报告为通过。
- `uv lock --check --offline`：通过，0.2.3 仅同步根版本，没有依赖升级。
- `uv build --offline`：sdist/wheel 均通过。uv 0.13.6 对既有 uv-build 范围有非阻塞警告，未为此升级依赖。
- 新 wheel 解压到 checkout 以外的临时目录，`PYTHONPATH` 仅指向 wheel 内容；核实 runtime 实际导入路径、无源码默认文件时 1.5° 默认值、导入不加载 SDK/camera/GELLO/LeRobot；独立启动 HAL 采集并检查 **70 条样本** 通过。依赖复用已安装的 contract/pyzmq/msgpack，不能称全新 PyPI 安装验收。
- 最终 CLI 结果见上表；早期失败日志、RED/最终验证、CLI 和 wheel JSON、代码 SHA256 清单保留在本地忽略的 `.superpowers/sdd/architecture-p2-plan/`。长期结论与回归用例在 Git 工作树中保留。


P0 2026-11-17 的 COMPLETE、冻结 0.2.2 源码、B4 黄金数据和 B6 真实序列保持不变；GELLO 原有三个格式修改保留并排除 P2 范围。到位容差依 ADR 0005 为 1.5°，不补做容差实验。仅根版本为 0.2.3 待测开发版，六个固定 gitlink 未变。

P3 真实 HAL、PiPER-X 断令证据、P4 真机两种记录模式/吞吐/raw 迁移、P5 导出、P6 Web 切换、P7 提取/回归仍待实施或验收。写盘线程/ZMQ 的选择只由 P0 当前 profile 支持，后续须实测新 runtime；本次未宣称共享内存、独立写盘进程或更高持续频率已无必要。离线检查会完整读取 raw，长时大数据内存/吞吐仍需 P4 衡量。

## 评审暂不判断项与执行决定

- 真机动作、吞吐与断令：维持 unverified；软件仿真不能给出硬件结论，相关上线仍受 P3/P4 门槛约束。
- P0 与预存 GELLO 排版：保持独立历史证据，不将其混入本轮正确性声明；如原基线有误，本轮测试不能代替基线核验。
- 安装包：由主执行者在 checkout 之外实际验证；评审未重复执行，包装验证的独立性较低，保留命令和结果。
- 其余执行决定及代价完整保存在本地 ledger 的 `Ruling:` 行：现有工作分支保留 P0 未提交资料；沿用用户批准的 P2 不重复询问；1/5 秒只作仿真默认；按用户裁决使用 1.5°；因提交门槛改用工作树评审；据 P0 保留写盘线程/ZMQ；正常文件测试采用正式 5 秒期限。
- 无 deferred minor；无需再次整体评审。按项目门槛保留工作树，等待本版本后续实测/分发授权；本次不提交、不合并、不推送。
