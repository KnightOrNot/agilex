"""Explicit HAL startup; help never imports a hardware driver."""

import argparse
import importlib
import json
import signal
from pathlib import Path

from .config import POLICIES, validate_settings
from .server import HalServer


def main(backend, argv=None):
    parser = argparse.ArgumentParser(
        description=f"{backend} HAL service (physical hardware)"
    )
    parser.add_argument("action", choices=("serve",))
    parser.add_argument("--settings-json", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--endpoint-dir", required=True)
    parser.add_argument("--hz", type=float, default=50.0)
    parser.add_argument("--command-timeout-s", type=float, default=0.25)
    parser.add_argument("--lease-timeout-s", type=float, default=3.0)
    parser.add_argument(
        "--exit-policy", choices=POLICIES[backend], default=POLICIES[backend][0]
    )
    args = parser.parse_args(argv)
    try:
        settings = validate_settings(
            backend, json.loads(Path(args.settings_json).read_text())
        )
        settings.update(device_id=args.device_id, exit_policy=args.exit_policy)
        if backend != "realsense":
            settings["hz"] = args.hz
        if args.hz <= 0 or args.command_timeout_s <= 0 or args.lease_timeout_s <= 0:
            raise ValueError("rates and timeouts must be positive")
        module = importlib.import_module(f"agx_hal_{backend}.device")
        cls = getattr(
            module,
            {
                "piperx": "PiperXDevice",
                "gello": "GelloDevice",
                "realsense": "RealSenseDevice",
            }[backend],
        )
        device = cls(settings)
        server = HalServer(
            device,
            args.endpoint_dir,
            command_timeout_ns=round(args.command_timeout_s * 1e9),
            lease_timeout_ns=round(args.lease_timeout_s * 1e9),
        )
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: server.stop())
        server.run()
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    return 0
