# Configuration reference

English | [简体中文](../../zh/reference/config.md)

Both entry points share [config/default.toml](../../../config/default.toml). Explicit `--config FILE` chooses another TOML; missing fields use built-ins, explicit CLI wins, and invalid/unknown configuration fails before hardware startup. Only the browser reads `[collection]`; the CLI loader ignores it.

## Robot and safety

```toml
[robot]
host = "127.0.0.1"
port = 6001
hz = 50.0
can_interface = "can0"
can_bitrate = 1000000

[safety]
max_start_error_rad = 0.35
transition_step_rad = 0.02
max_command_step_rad = 1.0
request_timeout_s = 2.0
startup_timeout_s = 15.0
```

Port is an integer in 1..65535. Rates, timeouts and steps must be positive and finite. Transition step is limited to 0.05 rad and running step to 1.0 rad. Changing control rate also changes the owned server's command limit, not the actual hardware feedback rate.

## GELLO

```toml
[gello]
port = "/dev/serial/by-id/usb-FTDI_USB__-__Serial_Converter_FTBM4Z46-if00-port0"
joint_ids = [1, 2, 3, 4, 5, 6]
joint_offsets = [3.141592653589793, 3.141592653589793, 3.141592653589793, 3.141592653589793, 3.141592653589793, 3.141592653589793]
joint_signs = [1, -1, -1, -1, 1, 1]
gripper_config = [7, 159, 201]
follower_signs = [1, 1, -1, -1, 1, 1]
```

These values belong to the previously calibrated installation, not an arbitrary leader. Offsets are radians. The gripper tuple contains ID and two degree endpoints; all seven IDs must be unique.

Device coordinates are `(encoder - joint_offsets) * joint_signs`; the controller separately applies `follower_signs` to six arm joints. Gripper normalization is `(angle - endpoint_0) / (endpoint_1 - endpoint_0)`, clamped to [0,1], then passed to SDK width mapping (0 closed, 1 open). Verify endpoint direction against the installation rather than swapping it during migration.

Startup selects the Dynamixel multi-turn branch before follower mapping. `PORT_CONFIG_MAP` is not the controller's calibration source: it passes `DynamixelRobotConfig`. GELLO's independent read CLI has its own configuration.

## Recording

```toml
[recording]
task = "PiPER-X GELLO teleoperation"
queue_size = 500
dataset_fps = 30
convert = true
start_recording = false
```

Task is nonempty; queue_size and dataset_fps are positive integers. Raw 50 Hz and dataset 30 FPS are different stages, with matching/resampling owned by converter. Start-recording does not automatically save.

## Paths

```toml
[paths]
sdk_project = "third-party/agilex-sdk-python"
converter_project = "third-party/lerobot-converter"
raw_data_root = "data/raw"
lerobot_data_root = "data/lerobot"
```

Relative paths resolve against the controller root, not the TOML directory or shell cwd. Absolute paths are accepted. A separate SDK working copy can use `../agilex-sdk-python`; converter is analogous. GELLO's Python source is selected through pyproject `tool.uv.sources`, not this file.

## Experiments

```bash
cp config/default.toml config/experiment.toml
uv run agilex-controller --config config/experiment.toml config
uv run agilex-controller record --config config/experiment.toml \
  --hz 50 --task "pick object" --skip-conversion
```

Check configuration and physical feedback after device changes before supervised motion. `read` disables leader torque at initialization, so it must not be used as a strictly read-only audit.

## Camera

```toml
[camera]
enabled = false
name = "front"
serial = ""
width = 640
height = 480
fps = 30
depth_enabled = true
depth_width = 640
depth_height = 480
depth_fps = 30
warmup_frames = 15
startup_timeout_s = 10.0
frame_timeout_s = 1.0
queue_size = 32
png_compress_level = 0
max_skew_ms = 50.0
preview = false
```

Empty serial permits only a single detected device. Stream profiles must be supported and can differ between RGB/depth. Names start with a letter and contain letters/digits/underscores; depth is named `<name>_depth`.

Warmup skips initial frames on each stream. Startup requires fresh host-domain frames for every enabled stream; frame timeout checks last receipt per stream. Queue overflow fails visibly. Dimensions/rates/capacities are positive integers; warmup may be zero; timeout/skew values are positive finite numbers.

PNG compression is integer 0..9, default 0, preserving RGB8/Z16 losslessly. Higher values reduce size but add CPU. CLI `--camera-png-compress-level` overrides TOML; a fixed None row filter avoids adaptive filtering. Dual 640×480@30 is about 46 MB/s or 2.8 GB/minute. Default 32-frame queues absorb about a second of transient jitter, not sustained disk underperformance.

`max_skew_ms` constrains per-stream converter target matching, not exposure accuracy. Preview can drop display frames independently of recorded data. Legacy wrappers retain raw v1 with camera disabled; camera wrappers enable camera and preview through CLI, overriding TOML. `depth_enabled=false` only removes depth.

## Collection

```toml
[collection]
hardware_config = ""
data_root = "data/lerobot/app"
control_hz = 50
dataset_fps = 30
max_skew_ms = 50.0
queue_size = 90
watchdog_s = 1.0
position_tolerance_deg = 1.1
preview_depth_max_m = 3.0
preview_cloud_stride = 4
camera_enabled = true
camera_mode = "auto"
depth_enabled = true
```

This table belongs to the browser. Empty hardware_config uses hardware sections from this shared file; an explicit alternate path is still validated by the controller loader. Data_root defaults to `data/lerobot/app`. Control/sample rates, queue size and cloud stride must be positive integers, with `dataset_fps <= control_hz`.

`max_skew_ms` bounds host-monotonic differences between RGB/depth and robot feedback. Watchdog controls heartbeat timeout. The browser's per-axis positioning acceptance is configured as 1.1° for startup zeroing, alignment and exit zeroing; CLI `move_js` independently defaults to 1.0°. Do not subtract offsets, switch motion mode or recalibrate automatically to hide errors.

Camera/depth flags control device acquisition. Mode is auto/fast/slow/manual; auto probes 640×360@90 then falls back, manual uses `[camera]`. Depth color range/cloud stride are display-only and do not change datasets or raw `.npy` files.

Minimal standalone app TOML can use flat keys; a shared file containing `[collection]` reads that table. Unknown keys fail.
