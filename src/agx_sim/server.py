"""One simulated HAL per process, with bounded work on every polling turn."""

import os
import stat
import time
from pathlib import Path

import zmq
from agilex_contract import SCHEMA_VERSION, Ack, Command, from_wire, to_wire

from .control import ControlGate
from .devices import SimDevice
from .transport import MAX_METADATA_BYTES, encode_event, endpoints, pack, unpack


class HalServer:
    def __init__(self, device: SimDevice, directory: str | Path, **deadlines):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("HAL directory must be owner-private (0700)")
        self.paths = {
            name: self.directory / f"{name}.sock"
            for name in ("rpc", "commands", "events")
        }
        if any(path.exists() or path.is_symlink() for path in self.paths.values()):
            raise ValueError("HAL endpoint already exists; refusing to replace it")
        if any(len(os.fsencode(path)) >= 100 for path in self.paths.values()):
            raise ValueError("IPC endpoint path is too long")
        self.device = device
        self.gate = ControlGate(device, **deadlines)
        self.context = zmq.Context()
        self.sockets = {}
        self._bound = []
        self.protocol_errors = 0
        self.stopping = False
        try:
            for name, kind in (
                ("rpc", zmq.REP),
                ("commands", zmq.PULL),
                ("events", zmq.PUB),
            ):
                socket = self.context.socket(kind)
                self.sockets[name] = socket
                socket.setsockopt(zmq.LINGER, 0)
                socket.setsockopt(zmq.SNDHWM, 128)
                socket.setsockopt(zmq.RCVHWM, 128)
                socket.setsockopt(zmq.MAXMSGSIZE, MAX_METADATA_BYTES)
                socket.bind(endpoints(self.directory)[name])
                self._bound.append(self.paths[name])
                os.chmod(self.paths[name], 0o600)
        except Exception:
            self.close()
            raise

    def _rpc(self, request, now_ns):
        if set(request) != {"schema_version", "method", "arguments"}:
            raise ValueError("request fields do not match schema")
        if (
            type(request["schema_version"]) is not int
            or request["schema_version"] != SCHEMA_VERSION
        ):
            raise ValueError("incompatible request schema")
        method, args = request["method"], request["arguments"]
        if not isinstance(method, str) or not isinstance(args, dict):
            raise ValueError("invalid method/arguments")
        if method == "hello":
            if args:
                raise ValueError("hello takes no arguments")
            return to_wire(self.device.descriptor)
        if method == "status":
            if args:
                raise ValueError("status takes no arguments")
            return self.gate.status(now_ns) | {"protocol_errors": self.protocol_errors}
        if method == "acquire":
            if set(args) != {"session_id"}:
                raise ValueError("acquire requires session_id")
            return {"lease": self.gate.acquire(args["session_id"], now_ns)}
        if method == "align_step":
            if set(args) != {"command"}:
                raise ValueError("align_step requires command")
            command = from_wire(args["command"])
            if not isinstance(command, Command):
                raise ValueError("align_step requires a Command")
            return to_wire(self.gate.alignment_step(command, now_ns))
        handlers = {
            "prepare": self.gate.prepare,
            "authorize": self.gate.authorize,
            "align_begin": self.gate.begin_alignment,
            "activate": self.gate.activate,
            "renew": self.gate.renew,
            "release": self.gate.release,
        }
        if method not in handlers or set(args) != {"session_id", "lease"}:
            raise ValueError("unknown method or invalid owner arguments")
        handlers[method](args["session_id"], args["lease"], now_ns)
        return self.gate.status(now_ns)

    def _publish(self, value):
        try:
            self.sockets["events"].send_multipart(
                encode_event(value), flags=zmq.DONTWAIT
            )
        except zmq.Again:
            pass  # PUB is intentionally lossy; sample sequence exposes gaps.

    def run(self):
        poller = zmq.Poller()
        poller.register(self.sockets["rpc"], zmq.POLLIN)
        poller.register(self.sockets["commands"], zmq.POLLIN)
        next_sample = time.monotonic_ns()
        period = max(1, int(1e9 / self.device.hz))
        try:
            while not self.stopping:
                wait_ns = max(0, next_sample - time.monotonic_ns())
                wait_ms = min(5, (wait_ns + 999_999) // 1_000_000)
                ready = dict(poller.poll(wait_ms))
                now = time.monotonic_ns()
                self.gate.tick(now)
                if self.sockets["rpc"] in ready:
                    try:
                        parts = self.sockets["rpc"].recv_multipart(flags=zmq.DONTWAIT)
                        if len(parts) != 1:
                            raise ValueError("management request must have one frame")
                        result = self._rpc(unpack(parts[0]), now)
                        reply = {"ok": True, "result": result}
                    except (ValueError, TypeError, KeyError, OverflowError) as exc:
                        self.protocol_errors += 1
                        reply = {"ok": False, "error": str(exc)[:512]}
                    self.sockets["rpc"].send(
                        pack({"schema_version": SCHEMA_VERSION, **reply}),
                        flags=zmq.DONTWAIT,
                    )
                # Bound batches so producer traffic cannot starve deadlines.
                for _ in range(32):
                    try:
                        parts = self.sockets["commands"].recv_multipart(
                            flags=zmq.DONTWAIT
                        )
                    except zmq.Again:
                        break
                    try:
                        if len(parts) != 1:
                            raise ValueError("command must have one frame")
                        command = from_wire(unpack(parts[0]))
                        if not isinstance(command, Command):
                            raise ValueError("expected Command")
                        now = time.monotonic_ns()
                        self._publish(
                            Ack(
                                command.session_id,
                                command.lease,
                                command.cmd_seq,
                                "received",
                                now,
                            )
                        )
                        self._publish(self.gate.accept(command, now))
                    except (ValueError, TypeError, KeyError, OverflowError):
                        self.protocol_errors += 1
                now = time.monotonic_ns()
                self.gate.tick(now)
                # Keep each turn bounded, but do not submit an intermediate
                # target when newer targets are already waiting in the socket.
                if not self.sockets["commands"].poll(0, zmq.POLLIN):
                    ack = self.gate.submit_pending(now)
                    if ack is not None:
                        self._publish(ack)
                if now >= next_sample:
                    for sample in self.device.samples(now):
                        self._publish(sample)
                    next_sample = now + period
        finally:
            self.close()

    def close(self):
        for socket in self.sockets.values():
            socket.close(linger=0)
        self.sockets.clear()
        self.context.term()
        for path in self._bound:
            path.unlink(missing_ok=True)
        self._bound.clear()
