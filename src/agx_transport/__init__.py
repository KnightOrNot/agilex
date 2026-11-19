"""Local multipart protocol: msgpack metadata and separate RGB/Z16 bytes."""

import os
import stat
import time
from dataclasses import replace
from pathlib import Path

import msgpack
import zmq
from agilex_contract import SCHEMA_VERSION, Ack, Command, Sample, from_wire, to_wire

MAX_METADATA_BYTES = 1_048_576


def verify_endpoint(directory: str | Path) -> Path:
    path = Path(directory).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise PermissionError("IPC paths must not contain symlinks")
    if path.exists():
        info = path.stat()
        if (
            not path.is_dir()
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise PermissionError("IPC directory must be owner-private (0700)")
        for name in ("rpc", "commands", "events"):
            endpoint = path / f"{name}.sock"
            if endpoint.is_symlink():
                raise PermissionError("IPC endpoint must not be a symlink")
            if endpoint.exists():
                info = endpoint.stat()
                if (
                    not stat.S_ISSOCK(info.st_mode)
                    or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                ):
                    raise PermissionError("IPC socket must be owner-private (0600)")
    return path


def endpoints(directory: str | Path) -> dict[str, str]:
    path = Path(directory).resolve()
    return {
        name: f"ipc://{path / (name + '.sock')}"
        for name in ("rpc", "commands", "events")
    }


def pack(value: dict) -> bytes:
    data = msgpack.packb(value, use_bin_type=True)
    if len(data) > MAX_METADATA_BYTES:
        raise ValueError("metadata exceeds message size limit")
    return data


def unpack(data: bytes) -> dict:
    if len(data) > MAX_METADATA_BYTES:
        raise ValueError("metadata exceeds message size limit")
    try:
        value = msgpack.unpackb(
            data,
            raw=False,
            strict_map_key=True,
            max_array_len=16384,
            max_map_len=256,
            max_str_len=65536,
            max_bin_len=MAX_METADATA_BYTES,
            max_ext_len=0,
        )
    except (ValueError, TypeError, msgpack.UnpackException) as exc:
        raise ValueError("invalid msgpack metadata") from exc
    if not isinstance(value, dict):
        raise ValueError("metadata must be a map")
    return value


def encode_event(value: Sample | Ack) -> list[bytes]:
    wire = to_wire(value)
    topic = b"sample" if isinstance(value, Sample) else b"ack"
    payload = wire.get("payload", {})
    image = payload.pop("data", None)
    result = [topic, pack(wire)]
    if image is not None:
        result.append(image)
    return result


def decode_event(parts: list[bytes]) -> Sample | Ack:
    if len(parts) not in (2, 3) or parts[0] not in (b"sample", b"ack"):
        raise ValueError("invalid event frames")
    wire = unpack(parts[1])
    payload = wire.get("payload")
    is_image = isinstance(payload, dict) and payload.get("type") in (
        "ImageFrame",
        "DepthFrame",
    )
    if is_image != (len(parts) == 3):
        raise ValueError("image frame count mismatch")
    if is_image:
        if "data" in payload:
            raise ValueError("image data must use the binary frame")
        payload["data"] = parts[2]
    value = from_wire(wire)
    expected = Sample if parts[0] == b"sample" else Ack
    if not isinstance(value, expected):
        raise ValueError("event topic/type mismatch")
    if isinstance(value, Sample):
        value = replace(value, t_runtime_rx_mono_ns=time.monotonic_ns())
    return value


class HalClient:
    """Management calls are bounded; continuous targets never wait for replies."""

    def __init__(self, directory: str | Path, *, timeout_ms: int = 1000):
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        self.directory = verify_endpoint(directory)
        self.addresses = endpoints(self.directory)
        self.timeout_ms = timeout_ms
        self.context = zmq.Context()
        self.commands = self.context.socket(zmq.PUSH)
        self.commands.setsockopt(zmq.LINGER, 0)
        self.commands.setsockopt(zmq.SNDHWM, 8)
        self.commands.setsockopt(zmq.IMMEDIATE, 1)
        self.commands.connect(self.addresses["commands"])
        self.events = self.context.socket(zmq.SUB)
        self.events.setsockopt(zmq.LINGER, 0)
        self.events.setsockopt(zmq.RCVHWM, 128)
        self.events.setsockopt(zmq.MAXMSGSIZE, 64 * 1024 * 1024)
        self.events.setsockopt(zmq.SUBSCRIBE, b"sample")
        self.events.setsockopt(zmq.SUBSCRIBE, b"ack")
        self.events.connect(self.addresses["events"])

    def request(self, method: str, **arguments):
        return request(
            self.directory,
            method,
            timeout_ms=self.timeout_ms,
            context=self.context,
            **arguments,
        )

    def send(self, command: Command) -> bool:
        try:
            self.commands.send(pack(to_wire(command)), flags=zmq.DONTWAIT)
        except zmq.Again:
            return False
        return True

    def receive(self, timeout_s: float = 0.0) -> Sample | Ack | None:
        if not self.events.poll(max(0, int(timeout_s * 1000))):
            return None
        return decode_event(self.events.recv_multipart(flags=zmq.DONTWAIT))

    def close(self):
        self.commands.close()
        self.events.close()
        self.context.term()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def request(directory, method, *, timeout_ms=1000, context=None, **arguments):
    """One bounded management socket; never opens a command or data channel.

    ZMQ contexts may be shared across threads, while every request owns and
    closes its own socket. The process context avoids starting an I/O thread
    for each lease renewal or concurrent producer boundary request.
    """
    if type(timeout_ms) is not int or timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive")
    directory = verify_endpoint(directory)
    context = context if context is not None else zmq.Context.instance()
    rpc = context.socket(zmq.REQ)
    try:
        rpc.setsockopt(zmq.LINGER, 0)
        rpc.setsockopt(zmq.SNDTIMEO, timeout_ms)
        rpc.setsockopt(zmq.RCVTIMEO, timeout_ms)
        rpc.setsockopt(zmq.MAXMSGSIZE, MAX_METADATA_BYTES)
        rpc.connect(endpoints(directory)["rpc"])
        arguments = {
            key: to_wire(value) if isinstance(value, Command) else value
            for key, value in arguments.items()
        }
        rpc.send(
            pack(
                {
                    "schema_version": SCHEMA_VERSION,
                    "method": method,
                    "arguments": arguments,
                }
            )
        )
        reply = unpack(rpc.recv())
    except zmq.Again as exc:
        raise TimeoutError(f"HAL request timed out: {method}") from exc
    finally:
        rpc.close()
    if reply.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("incompatible response schema")
    if reply.get("ok") is not True:
        raise ValueError(reply.get("error", "HAL request rejected"))
    value = reply["result"]
    return from_wire(value) if isinstance(value, dict) and "type" in value else value
