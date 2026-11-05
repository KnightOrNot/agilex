# Changelog

All notable changes are recorded here in Keep a Changelog format. This project has no published release yet; version 0.2.0 remains under development.

## [Unreleased]

### Added

- HABITS-based project routing, a single TESTING checkpoint, preserved investigation records and ADRs.
- Paired English/Chinese documentation, root Make targets and a hardware-free GitHub verification workflow.
- Documentation checks for required files, bilingual examples, relative links and stage routing.

### Changed

- Updated project metadata to version 0.2.0 and described both CLI and browser RGB-D collection workflows.
- Project rules now live under `.agents/`; `AGENTS.md` is the index and `CLAUDE.md` is its one-line bridge.
- User documentation moved to `docs/en/` and `docs/zh/`; detailed usage is retained outside the landing pages.

## 0.1.0 development baseline — 2026-11-05 (not released)

### Added

- Parallel CLI and browser collection entry points; browser save/discard, live state and LeLab dataset management.
- RGB, depth, side-by-side and WebGL point-cloud previews, with distinct preview/sample/capture FPS.
- Private Unix IPC adapters and native RGB/Z16 inputs with calibration and timing audit.
- Camera mode selection that probes 640×360@90 and falls back through 60/30 FPS.

### Changed

- Published Python 3.12/uv environments on main across the root and five submodules; merged dev branches were removed.
- Moved all five submodules under `third-party/`; renamed the camera checkout to `camera-submodule-d455f` and its remote to `camera-realsense-d455f`, preserving imports and CLI names.
- Consolidated application settings in `config/default.toml`; the browser uses `[collection]`.
- Set browser positioning acceptance to 1.1 degrees after operator investigation; the CLI positioning default remains 1.0 degree.
- Pinned the available remote-main dependencies, including PyPI DynamixelSDK 4.0.5 and the `agilex_gello_software` namespace.
- Reduced collection UI clutter while preserving preview statistics, metadata and disabled controls for unavailable features.

### Fixed

- GELLO simulation/full Pinocchio binary compatibility through urdfdom/tinyxml2 constraints.
- Local dataset picker refresh after deletion, startup camera counter resets and worker error reporting.
- Lossless PNG encoding throughput while retaining per-file fsync and native depth values.

## 0.0.0 initial development — 2026-09 to 2026-10 (not released)

### Added

- CLI configuration, physical GELLO reading, SDK status, JS positioning, following, raw recording and offline conversion.
- Raw v1/v2 sessions, RGB/Z16 images, per-stream timestamps, calibration and manifests.
- Separate converter environment and regression coverage for RPC failures, interruption and partial writes.
