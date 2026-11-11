"""Start a synthetic HAL; this module never loads physical device drivers."""

import argparse
import json
import math
import signal

from agilex_contract import to_wire

from .devices import SimDevice
from .server import HalServer
from .transport import HalClient


def _positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hardware-free AgileX HAL simulation")
    sub = parser.add_subparsers(dest="action", required=True)
    serve = sub.add_parser("serve", help="run one synthetic device in this process")
    serve.add_argument(
        "--kind", choices=("leader", "follower", "camera", "wrench"), required=True
    )
    serve.add_argument("--device-id", required=True)
    serve.add_argument("--endpoint-dir", required=True)
    serve.add_argument("--axes", type=int, default=6)
    serve.add_argument("--hz", type=_positive)
    serve.add_argument("--command-timeout-s", type=_positive, default=0.25)
    serve.add_argument("--lease-timeout-s", type=_positive, default=5.0)
    inspect = sub.add_parser(
        "inspect", help="read a running simulated device descriptor"
    )
    inspect.add_argument("--endpoint-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "inspect":
            with HalClient(args.endpoint_dir) as client:
                print(json.dumps(to_wire(client.request("hello")), indent=2))
            return 0
        device = SimDevice(args.kind, args.device_id, axes=args.axes, hz=args.hz)
        server = HalServer(
            device,
            args.endpoint_dir,
            command_timeout_ns=int(args.command_timeout_s * 1e9),
            lease_timeout_ns=int(args.lease_timeout_s * 1e9),
        )

        def stop(_signum, _frame):
            server.stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        server.run()
    except (ValueError, TimeoutError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
