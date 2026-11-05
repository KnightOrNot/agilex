# RGB-D capture and timestamp alignment

English | [简体中文](../zh/cameras.md)

## Runtime ownership

The camera library owns device/profile selection, per-stream SDK timestamps, RGB/Z16 frames and calibration. The controller composes devices, records raw and owns cleanup. The converter owns target-time matching and LeRobot output; this workflow does not replace SDK/GELLO hardware layers.

```bash
./scripts/setup.sh --skip-system --skip-submodules
./scripts/start_camera_follow.sh
./scripts/start_camera_record.sh
```

Camera follow checks RGB-D and shows RGB without saving images; camera record adds joint/image sampling. R/S/D operate on a combined episode. Defaults are one device and RGB/depth each at 640×480@30; verify support with `info --profiles`. Specify serial when multiple cameras are present.

Q/Esc/window close ends preview only; terminal Ctrl+C stops following. Use `--no-camera-preview` on SSH/headless hosts and `--no-camera-depth` for RGB only. Legacy wrappers keep camera disabled. Direct CLI uses `follow --camera --camera-preview` or the record equivalent.

## Two timing layers

Preserve `sdk_timestamp_ms` and `sdk_timestamp_domain`. Global/system SDK time relates to the host wall clock. Sampling `monotonic → time_ns → monotonic` estimates the epoch offset and maps SDK milliseconds into host `time.monotonic_ns`. Never compare unconverted hardware-clock numbers with robot timestamps. See the [RealSense timestamp definitions](https://realsenseai.github.io/librealsense/doxygen/rs__frame_8h_source.html).

Each stream warms up into a global/system domain and validates increasing time. Guards require at most a 5 ms host sampling window/adjacent offset jump, and mapped time no later than receipt +50 ms or earlier than receipt -1 s. These are sanity bounds, not synchronization accuracy guarantees; firmware estimates and USB latency still matter.

The converter starts at the first joint `observation_time_ns` and constructs the dataset timeline at `recording.dataset_fps`. Whole joint rows, RGB and depth independently select the nearest timestamp, preferring the earlier frame on ties. Action/observation stay paired. Each image's default maximum target skew is the manifest's 50 ms; exceeding it rejects conversion. Reports include errors, source frames, reuse and SDK frame-number gaps.

Joint timestamps approximate client feedback receipt rather than hardware sampling. Timestamp matching is not exposure-trigger synchronization; physical synchronization requires separate hardware/latency calibration.

## Raw storage and save integrity

Camera sessions use raw v2 with the same joint rows as v1:

```text
SESSION/
├── manifest.json
├── episodes/episode_000000.jsonl
└── cameras/
    ├── front/episode_000000/frames.jsonl
    ├── front/episode_000000/frames/000000.png
    ├── front_depth/episode_000000/frames.jsonl
    └── front_depth/episode_000000/frames/000000.png
```

The manifest stores device/profile, clock metadata, storage type, intrinsics, depth scale and depth-to-color extrinsics. RGB is uint8 RGB PNG; depth is native-view uint16 Z16 PNG, with zero invalid. Distance is `raw_value * depth_units_m`, not an assumed fixed millimeter scale.

PNG uses a fixed None row filter and default compression level 0, preserving RGB and all depth bits while reducing CPU cost. Each file is fsynced; saving also syncs the index. `png_compress_level` / `--camera-png-compress-level 0..9` can trade CPU for disk. Dual 640×480@30 produces roughly 46 MB/s, or 2.8 GB/minute, before practical overhead.

Each stream index records sequential frame_index, relative path, SDK counter, mapped/received timestamps, original SDK time/domain, epoch offset and sampling span. Unsaved directories have `.partial`. Bounded writer errors/overflow fail visibly, never silently drop persisted samples. Unreceived SDK frames cannot be reconstructed; counter gaps remain auditable.

S flushes/fsyncs every writer, publishes camera directories and then final joint JSONL as the completion marker. Orphan image directories do not convert independently. Interrupt cleanup zeros through JS, stops the owned SDK and flushes partials. Do not rename partial data to pretend completion.

## LeRobot readback

RGB becomes MP4 under `observation.images.front`. Depth is `observation.images.front_depth`: float32 single-channel image with `is_depth_map=true, depth_unit=m`, losslessly embedded as TIFF in Parquet. Zero and valid Z16 values are preserved subject to meter float32 rounding; original Z16 remains in raw.

```python
from lerobot.datasets.lerobot_dataset import LeRobotDataset

dataset = LeRobotDataset("local/demo", root="data/lerobot/DATASET", depth_output_unit="m")
rgb = dataset[0]["observation.images.front"]       # (3, H, W), 0..1
z_m = dataset[0]["observation.images.front_depth"] # (1, H_depth, W_depth), m
```

The locked LeRobot version defaults to mm on readback, so specify `depth_output_unit="m"`. Native depth is not projected into RGB coordinates, even for equal image dimensions. Registration must use preserved intrinsics/extrinsics.

Offline tests exercise real state-only, RGB and RGB-D datasets, including depth 0/65535, an independent 1 ms depth offset and unchanged raw input. They do not validate physical cameras, USB throughput or arm motion. Start physical capture with a short saved dataset and inspect images, units and quality_report before longer runs.
