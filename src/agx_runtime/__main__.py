"""Unified runtime CLI; legacy controller/Web entrypoints remain separate."""

import argparse
import json
import signal
import sys
import time

from agilex_contract import to_wire

from .config import load_config, positive
from .raw import inspect_episode, replay_commands, replay_episode
from .service import RuntimeClient, RuntimeService
from .session import Session


def _positive(value):
    try:
        number = float(value)
        positive(number, "seconds")
        return number
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _until(session, predicate, timeout):
    deadline = time.monotonic() + timeout
    while True:
        state = session.status()
        if state["error"]:
            raise ValueError(state["error"])
        if predicate(state):
            return state
        if time.monotonic() >= deadline:
            raise TimeoutError("runtime operation timed out")
        time.sleep(0.005)


def run(config, seconds, confirmation=None):
    physical = config.physical_follower
    if physical and (confirmation is not None or not sys.stdin.isatty()):
        raise ValueError("physical PiPER-X motion requires interactive confirmation")
    session = Session(config)
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in previous:
        signal.signal(sig, lambda *_: session.stop("interrupted by operator"))
    try:
        session.prepare()
        state = _until(
            session,
            lambda s: s["phase"] in ("READY", "CONFIRM"),
            config.startup_timeout_s * 2 + 1,
        )
        if state["phase"] == "CONFIRM":
            if confirmation is None:
                key = (
                    "hardware_motion_target" if physical else "simulated_motion_target"
                )
                print(json.dumps({key: state["target"]}), flush=True)
                motion = (
                    "physical PiPER-X motion" if physical else "simulated following"
                )
                confirmation = input(f"Type yes to authorize {motion}: ")
            if confirmation != "yes":
                raise ValueError("motion was not confirmed")
            session.confirm(True)
            _until(
                session,
                lambda s: s["phase"] == "FOLLOWING",
                config.motion.alignment_timeout_s + 1,
            )
        session.record()
        _until(
            session,
            lambda s: s["episode"]["phase"] == "RECORDING",
            config.record.boundary_timeout_s + config.record.drain_timeout_s + 1,
        )
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if session.status()["error"]:
                raise ValueError(session.status()["error"])
            time.sleep(0.005)
        session.save()
        _until(
            session,
            lambda s: s["episode"]["phase"] == "COMPLETE",
            config.record.boundary_timeout_s + config.record.drain_timeout_s + 1,
        )
    finally:
        session.stop()
        session.wait(config.startup_timeout_s + config.motion.alignment_timeout_s + 2)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    report = session.status()
    if report["error"]:
        raise ValueError(report["error"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="AgileX runtime with simulated or isolated physical HALs"
    )
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("run", "serve"):
        command = sub.add_parser(action)
        command.add_argument("--config", required=True)
        command.add_argument("--mode", choices=("full", "sampled"))
        command.add_argument("--data-root")
        command.add_argument("--lock-path")
        if action == "run":
            command.add_argument("--seconds", type=_positive, default=1.0)
            command.add_argument("--confirm", choices=("yes",), help="simulation only")
        else:
            command.add_argument("--endpoint-dir", required=True)
    request = sub.add_parser("request")
    request.add_argument("--endpoint-dir", required=True)
    request.add_argument("--client-id", required=True)
    request.add_argument("method")
    request.add_argument("--arguments", default="{}", help="JSON object")
    for action in ("check", "replay"):
        command = sub.add_parser(action)
        command.add_argument("path")
        if action == "replay":
            command.add_argument("--commands", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action in ("run", "serve"):
            overrides = {"runtime": {}, "record": {}}
            for name in ("data_root", "lock_path"):
                if getattr(args, name) is not None:
                    overrides["runtime"][name] = getattr(args, name)
            if args.mode:
                overrides["record"]["mode"] = args.mode
            config = load_config(args.config, overrides)
            if args.action == "run":
                print(json.dumps(run(config, args.seconds, args.confirm)))
            else:
                service = RuntimeService(config, args.endpoint_dir)
                for sig in (signal.SIGINT, signal.SIGTERM):
                    signal.signal(sig, lambda *_: service.stop())
                service.run()
        elif args.action == "request":
            arguments = json.loads(args.arguments)
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be a JSON object")
            print(
                json.dumps(
                    RuntimeClient(args.endpoint_dir, args.client_id).request(
                        args.method, **arguments
                    )
                )
            )
        elif args.action == "check":
            print(json.dumps(inspect_episode(args.path)))
        else:
            for item in (
                replay_commands(args.path)
                if args.commands
                else replay_episode(args.path)
            ):
                wire = to_wire(item)
                data = wire.get("payload", {}).pop("data", None)
                if data is not None:
                    wire["payload"]["byte_count"] = len(data)
                print(json.dumps(wire))
    except (OSError, ValueError, TimeoutError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
