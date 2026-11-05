# 历史调查与实现证据（2026-10 至 2026-11）

此文从原 CLAUDE 迁移，保留用户已有工作，属于历史证据，不是当前规则或当前授权。旧分支、路径、解释器、配置范围和测试计数可能已被 main 基线替代。当前事实与待办以 [testing](../stages/testing.md) 和 [project](../../project.md) 为准。



### 11.1 2026-11-05 布局、分支与 Python 迁移

- 五个子模块移到 `third-party/`；相机目录改名 `camera-submodule-d455f`，发行/CLI 仍为 `camera-realsense`，导入仍为 `camera_realsense`。
- `main` 先发布结构迁移，`dev` 从该基线创建并做 Python 3.12 迁移。
- 根/GELLO `>=3.12,<3.13`；controller/GELLO/SDK/camera 全部 3.12；`.gitmodules` 在 `dev` 跟踪子模块 `dev`。
- 旧文档中把 `agilex-sdk-python/`、`agilex-adapters/`、`camera-realsense/` 等直接放在根目录的路径说明已废弃。

### 11.2 2026-10-29 远端 main 基线

- 用户授权把五个子模块迁到可获取的远端 main，因为旧 gitlink 无法 fetch；先发布测试过的子仓库，再更新父 gitlink。
- 当时 GELLO main 使用 `agilex_gello_software` 命名空间和 PyPI DynamixelSDK 4.0.5；不要嵌套 SDK 或 `gello.*`。物理 `DynamixelRobot(real=True)` 拒绝 fake fallback。
- 当时基线验证：controller 122、adapters/application 12、camera 59、SDK 59、GELLO 12、converter 12；lint、camera/SDK Pyright、六个发行构建和 wheel 外部导入通过。系统 FFmpeg 和 libusb 由用户安装。ROS 2 远端工作流在 GELLO `04c6e1a` 通过（run `40887299012`，16m39s），post-step 用 `push: never` 修复。新 clone 检出五个 pinned commit 并通过离线 lock 一致性检查。
- 这些计数是 2026-10-29 快照；`dev` 迁移后以最新测试输出为准。
- 随后的相机/配置验证：298 tests 通过（controller 91、camera 64、SDK 65、GELLO 29、converter 28、adapters 21）；camera/SDK Pyright、各仓库 lint、GELLO 离线 upstream audit 和发行构建通过；五个 wheel 在 checkout 外解压并加载了与仓库一致的物化默认 TOML。该次没有相机采集、CAN 运动或远端推送。

### 11.3 2026-10-20 物理启动调查

- session `20261020_121045_811fe47f` 通过 CAN/相机初始化，但 J3 在启动和清理时停在 +1.032 度，超过当时的 1 度容差。只读诊断：六轴使能、反馈约 3.6 ms、无电机/臂故障、CAN 1 Mbit/s 无总线错误。
- session `20261020_153551_6f98d01b` 再次失败，J3 +1.015 度。SDK `limits` 显示 J3 范围 -170..0 度，零位是上限；静止时输出侧 +1.015 度、电机侧 +0.516 度、保持力矩 -7.6 N·m、无故障位。约 0.5 度差来自限位处的输出侧柔顺/回差。
- 用户随后明确把 `position_tolerance_deg` 提到 **1.1 度**，取代 1 度。仍不得减 offset、改运动模式或自动重校准。
- 应用定位日志记录 stage、六轴启动/最终反馈、残差、观测范围和成功命令数；worker 分开报告主错误和清理错误，浏览器优先显示结构化诊断。
- session `20261020_121535_49fee27a` 通过启动零位（J3 残差 0.921 度）、GELLO 对齐和退出零位；首个保存 episode 513 帧 @30 FPS。操作员明确说按了 Ctrl+C；不要仅凭心跳超时推断保存时 GIL 停顿。1.032 度残差的可重复性仍未验证。
- 当时检查：108 root、22 adapter/app；Ruff 和根构建通过。测试 flock 隔离到 pytest 临时目录。改动当时未提交。

### 11.4 2026-10-20 采集 UI 优化

- 步骤 1–4：1) `serve` 在现有锁下用 SDK 脚本和硬件 TOML 配置 CAN；模拟和 setup 跳过；失败阻止启动。2) 删除未使用的本地数据集列表链接。3) `/dataset-browser` 包装官方 `/edit-dataset` 并提供永久返回链接。4) UI 紧凑化，保留运动确认；原始状态放进可展开 details。
- 步骤 5：预览支持 `rgb|depth|rgbd|cloud` 四种 WebSocket 模式；显示浏览器呈现 FPS、观测/目标采样 FPS、启动探测的捕获 FPS 和模式对应的分辨率；`pointcloud.js` 原生 WebGL，支持 orbit/zoom/双击复位，无 CDN；同源检查、两 viewer 上限、断线释放、固定 deadline、旧显示帧丢弃。原生 Z16、标定和时间戳不变。
- 预览实现不变量：编码和点云计算在控制线程外，不能阻塞控制或录制；viewer slot 在 `accept` 前占用，避免并发握手超过上限；会话 generation/sequence 防止跨会话缓存帧；FPS 时钟在首帧解码后开始，避免 WebGL 初始化压低首次读数；原 JPEG 端点保持兼容。
- 验证：root 118、adapter/app 32 通过；Ruff 和两个构建通过；`pointcloud.js` 进入 root wheel 并以 JS MIME 提供；headless Firefox 在 64x48 模拟下四种模式约 30 FPS，点云 192 点，拖拽/缩放/双击生效。只读保存元数据确认 D455F USB 3.2、640x360@90、rectified depth intrinsics 和原生单位。不是真机或全分辨率验证。
- 待办：真机全分辨率吞吐/时序、CAN/sudo 行为、操作员显示器响应式布局和长时间多标签行为。

### 11.5 2026-10-20 LeLab 合并、上传、删除

- `/datasets/merge`、`/upload-dataset`、`/dataset-info`、`/hf-auth/login` 代理官方路由；merge 写 `data/lerobot/app/local/<name>`，不改源；upload 走 LeLab `push_to_hub`，需要操作员 HF 认证；`/jobs` 和 `/jobs/hub` 故意保持 404。motion、SO101 标定、training/inference 和 Hub 删除故意不提供。
- `/dataset-browser` 携带 LeLab 支持的 `?api=` 覆盖，让 localhost/127.0.0.1 和自定义端口无需 CORS 补丁。未实现 SPA 路径（`/recording`、`/teleoperation`、`/training`、`/training/{id}`、`/inference`、`/calibration`）服务端重定向到 `/dataset-browser`。
- `/delete-dataset` 是应用自有路由，只允许本地删除；`delete_from_hub` 返回结构化 400；未知数据集 404；活动 session 409。官方 handler 在配置根内执行受保护的 `rmtree`。
- LeRobot 在 import 时冻结 `HF_LEROBOT_HOME`；`create_app` 同时重绑 `lerobot.datasets.dataset_metadata.HF_LEROBOT_HOME`，让上传/删除/dataset-info 指向本地数据根。
- `/dataset-browser` 用 MutationObserver 向同源 iframe 注入策略：禁用 Back/Back to Home、Skip Upload、Record more、Create new dataset、tour、Hub 删除复选框；保留 Merge/Upload/Delete、选择、回放和上传表单。`pushState`/`replaceState` 把未实现路由改写到 `/edit-dataset`；`fetch` 包装在删除成功后重载 picker。
- 验证：118 root、41 adapter/app；Ruff 和构建通过；Node fake DOM 验证策略；headless Firefox 验证禁用项、删除、merge 模态和上传摘要。没有真实 HF 上传；upload 用 monkeypatch `push_to_hub`；merge/delete 用合成 probe 数据集。

### 11.6 2026-10-20 UI 信息清理

- 移除首页原始状态 JSON（“会话详情”、`<pre id="status">`）；上传页隐藏 Repository ID 和 About HuggingFace Hub Upload 块，保留摘要、tags、private 和 Upload；merge 对话框隐藏内部 “Saved locally as local/<name>” 提示。
- 保留：预览 FPS/分辨率/捕获统计、LeLab 数据集元数据、禁用控件/Jobs 侧栏/tour、上传 tags/private。
- 验证：118 root、41 adapter/app；Ruff 和构建通过；headless Firefox 验证四个页面。改动当时未提交。

### 11.7 2026-10-20 文档与配置合并

- 用户把 `agilex-controller` 和 `agilex-data-collection` 定为两个并列、同等常用的入口，不是主项目加扩展。
- `README.md` 覆盖两个入口；删除 `docs/data-collection.md` 和 `docs/data-collection-quickstart.md`，内容并入 README、`docs/index.md`、`docs/installation.md`、`docs/reference/{config,cli,errors}.md` 和 `docs/reference/submodule-config.md`。
- `CHANGELOG.md` 精简为按版本摘要。`config/data_collection.toml` 删除，collection 设置进入 `config/default.toml` 的 `[collection]`。
- `AppConfig.load` 支持 `[collection]` 和独立扁平 TOML；legacy loader 保留但忽略 `[collection]`。默认配置路径改为 `config/default.toml`。
- 当时没有代码路径、硬件行为或数据集格式变化；改动当时未提交。
