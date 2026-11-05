# agilex-controller

English | [简体中文](README.zh-CN.md)

Teleoperate an AgileX PiPER-X with a GELLO leader and collect RealSense D455F RGB-D datasets. All six projects use uv-managed Python 3.12 and independent frozen environments.

| Entry point | Purpose | Output |
| --- | --- | --- |
| `agilex-controller` | Terminal following, episode recording, JS positioning and conversion | Raw JSONL/images, then LeRobot Dataset v3 through the converter |
| `agilex-data-collection` | Browser following, save/discard, live preview and LeLab dataset management | LeRobot Dataset v3 plus immutable RGB/Z16 inputs and timing audit |

Both are first-class workflows. They share `config/default.toml` and the hardware lock; run one hardware workflow at a time.

## Features

- Bounded control/recording queues, explicit motion confirmation and JS cleanup.
- Native Z16, calibration and monotonic timestamp provenance.
- RGB, depth, side-by-side and interactive point-cloud browser previews.
- LeLab browsing, local merge/delete and explicitly triggered Hugging Face upload.
- Five pinned submodules under `third-party/`, with separate SDK, GELLO, camera, converter and adapter responsibilities.

## Install

On Linux with Git and the required system dependencies available:

```bash
git clone --branch main git@github.com:KnightOrNot/agilex-controller.git
cd agilex-controller
./scripts/setup.sh
uv run agilex-data-collection setup
```

The installer prepares uv/Python and the pinned environments without opening devices. Browser setup installs its separate application environment. After joining `dialout`, log in again. See [installation](docs/en/installation.md) for requirements, optional dependencies and updates.

## Start without hardware

```bash
uv run --frozen agilex-controller --help
uv run agilex-data-collection serve --simulate
```

Open <http://127.0.0.1:8000>. Simulation writes synthetic data but does not access the arm, leader or camera.

Physical following requires the documented calibration, device checks and operator confirmation. In a plain SSH session, disable the native preview with `--no-camera-preview`; browser preview can be viewed over an SSH tunnel. See [usage](docs/en/usage.md) before running motion commands.

## Development

```bash
make sync
make verify
```

These targets synchronize the root environment and run real style, documentation and hardware-free root checks. Converter integration tests require its separate environment; missing coverage is reported as skipped. Full child-repository and physical validation are separate.

## Documentation

- [Documentation home and architecture](docs/en/index.md)
- [Installation](docs/en/installation.md) · [Usage](docs/en/usage.md)
- [CLI](docs/en/reference/cli.md) · [Configuration](docs/en/reference/config.md)
- [Submodule configuration](docs/en/reference/submodule-config.md)
- [RGB-D and timing](docs/en/cameras.md) · [Troubleshooting](docs/en/reference/errors.md)
- [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## License

A project-wide license for newly authored code has **not been selected**. [LICENSE](LICENSE) records this status; it does not grant additional rights. Third-party notices remain in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and each submodule retains its own license.
