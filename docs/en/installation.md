# Installation and environments

English | [简体中文](../zh/installation.md)

## Requirements

Use Linux with SocketCAN, the PiPER-X/AGX gripper, USB-CAN and GELLO leader. Required tools include Git, uv, iproute2, FFmpeg, build tools and lsof. Dataset conversion dependencies belong to the converter environment, not the control environment.

All projects use Python 3.12; the root and GELLO constrain `>=3.12,<3.13`.

## Installer

```bash
git clone --branch main git@github.com:KnightOrNot/agilex.git
cd agilex
./scripts/setup.sh
```

The script resolves its own project root, initializes the pinned children, installs Python through uv and synchronizes separate frozen environments. The dev test candidate adds `agilex-contract` as a sixth child, installed into the root environment as a pure library. See the [HAL simulation guide](hal-simulation.md) for obtaining dev on another computer. The script installs Ubuntu packages, uv when needed and the serial group membership. It does not open CAN/serial or send motion. Current GELLO uses PyPI DynamixelSDK 4.0.5; the installer also supports historical nested-SDK layouts.

Install the separate browser application before its first use:

```bash
uv run agilex-data-collection setup
```

This synchronizes `third-party/agilex-adapters/.venv`, installs LeRobot 0.6.0, pinned LeLab and web dependencies, and builds the frontend. Network and Node are required. The default interpreter is uv-managed Python 3.12; `setup --python /path/to/python3.12` selects a complete existing interpreter. The root environment does not acquire the application dependencies.

| Option | Purpose |
| --- | --- |
| `--skip-system` | Skip apt and user-group changes when system dependencies are prepared |
| `--skip-submodules` | Preserve local child work without checking out pinned revisions |
| `--check-only` | Inspect existing environments/entry points |
| `--gello-extra NAME` | Install optional camera/simulation/robots/full in the independent GELLO environment |
| `--with-simulation-assets` | Explicitly download optional MuJoCo Menagerie assets |

Control needs only GELLO base dependencies; RealSense uses the independent camera library. Models are not downloaded by default. GELLO simulation/full constrains urdfdom 4 and tinyxml2 10 for the Pinocchio 3.7 ABI; installation alone does not verify native imports.

## Manual synchronization

After installing uv:

```bash
git submodule sync --recursive
git submodule update --init
uv python install 3.12
uv sync --project third-party/agilex-sdk-python --frozen --managed-python --python 3.12
uv sync --project third-party/agilex-gello-software --frozen --managed-python --python 3.12
uv sync --project third-party/lerobot-converter --frozen --extra dataset --managed-python --python 3.12
uv sync --project third-party/camera-realsense-d455f --frozen --managed-python --python 3.12
uv sync --frozen --managed-python --python 3.12
uv sync --project third-party/agilex-adapters --frozen --extra app --managed-python --python 3.12
mkdir -p data/raw data/lerobot
```

The adapters `app` extra includes LeRobot, LeLab, FastAPI and uvicorn. It is separate from the controller. GELLO and camera are root editable sources; an independent child CLI uses its own environment. Do not combine environments through PYTHONPATH.

Use the `agilex_gello_software` namespace and pinned DynamixelSDK 4.0.5. For ordinary updates, use pinned gitlinks. Explicit upgrades use `git submodule update --init --remote` and require testing before committing new references; the original five children track main, while the new contract candidate tracks dev. Ordinary initialization always checks out the pinned commit.

Before moving checkouts, back up old child `.venv` directories outside the repository and recreate them at the new paths:

```bash
git pull --ff-only
git submodule sync --recursive
git submodule update --init
./scripts/setup.sh --skip-system --skip-submodules
uv run agilex-data-collection setup
```

All children live under `third-party/`. The camera remote is `git@github.com:KnightOrNot/camera-realsense-d455f.git`, its directory is `camera-realsense-d455f`, and its package/CLI name remains `camera-realsense`. Old console scripts can retain absolute shebangs; recreate environments rather than editing them. Preserve local changes before updating. Optional Menagerie assets remain opt-in.

Install stable main for normal use. Development integrates on dev; make changes on a dedicated dev-<task> branch and follow the contribution gates.

## Verify installation

```bash
./scripts/setup.sh --check-only
uv run --frozen agilex-controller --help
uv run --frozen agilex-controller config
uv run agilex-data-collection --help
uv run --frozen pytest
```

Browser help checks only the root bootstrap, not the separate application runtime. The installer checks CLI imports, FFmpeg and converter TorchCodec. With its environment present, run `uv run --frozen pytest -m integration` for actual conversion/readback.

## Serial and CAN

```bash
sudo usermod -aG dialout "$USER"
```

Log in again to activate membership; inspect `/dev/serial/by-id/` and match port/calibration to the actual leader. Do not reuse calibration solely because a device path matches.

```bash
./third-party/agilex-sdk-python/scripts/config_can.sh can0 1000000 100
uv run agilex-controller read --json
uv run agilex-controller status
```

`read` disables leader torque during driver initialization, so it is not strictly read-only. A strict audit must use only Dynamixel PING/READ and preserve torque state. `status` reads the arm through the SDK and requires CAN readiness. Only proceed to motion after validating feedback and the documented operator confirmation.

## RealSense permissions

Follow the child [camera installation guide](../../third-party/camera-realsense-d455f/docs/installation.md) for Linux udev rules, then reconnect the device. Setup does not install those rules automatically. Prefer a USB 3 data connection without competing capture programs.

```bash
uv run --project third-party/camera-realsense-d455f camera-realsense info --profiles
```

Choose supported application profiles in the controller `[camera]` table. A standalone experiment TOML does not replace application configuration. Verify a short saved dataset before long capture. Headless CLI use needs `--no-camera-preview` because wrappers explicitly enable preview, overriding TOML.

## Normal terminals and remote operation

Use a fresh normal terminal to verify uv, rather than relying on a deployment-only PATH:

```bash
command -v uv
uv --version
id -nG
```

If uv was installed under a private tools directory, add that directory to your shell PATH or install it in the standard user bin directory. Activating a project virtual environment does not itself install uv.

After adding your user to dialout, reconnect SSH or start a new group shell:

```bash
newgrp dialout
```

A plain SSH session usually has no GUI display. Camera wrappers explicitly enable a Tk window, so TOML preview=false alone does not override them:

```bash
./scripts/start_camera_follow.sh --no-camera-preview
```

This disables only the native window, not configured RGB-D capture. To view browser preview remotely, keep HTTP bound to loopback and forward it through SSH:

```bash
ssh -L 8000:127.0.0.1:8000 robot@RON
```

Start the collection server on RON and open localhost:8000 on the client. Server startup in physical mode prepares CAN, and starting a physical session still needs motion confirmation. Alternatively, run the CLI inside a properly configured remote graphical desktop, with a usable DISPLAY. Remote desktop services require their own certificate, credentials and network configuration; keep secrets out of project files. A TCP/RDP handshake alone does not verify an actual desktop login or camera preview.
