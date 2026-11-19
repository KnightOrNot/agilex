"""Owner-private local command/status API with a controller heartbeat."""

import os
import stat
import threading
import time

import zmq

from agx_transport import MAX_METADATA_BYTES, pack, unpack, verify_endpoint

from .session import Session


def control_endpoint(directory):
    directory = verify_endpoint(directory)
    path = directory / "control.sock"
    if len(os.fsencode(path)) >= 100 or path.is_symlink():
        raise PermissionError("invalid command endpoint path")
    if path.exists():
        info = path.stat()
        if (
            not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise PermissionError("command endpoint must be owner-private (0600)")
    return path


class RuntimeClient:
    def __init__(self, directory, client_id, *, timeout_ms=1000):
        self.directory, self.client_id, self.timeout_ms = (
            directory,
            client_id,
            timeout_ms,
        )

    def request(self, method, **arguments):
        path = control_endpoint(self.directory)
        with zmq.Context() as context:
            with context.socket(zmq.REQ) as socket:
                socket.setsockopt(zmq.LINGER, 0)
                socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
                socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
                socket.setsockopt(zmq.MAXMSGSIZE, MAX_METADATA_BYTES)
                socket.connect(f"ipc://{path}")
                try:
                    socket.send(
                        pack(
                            {
                                "schema_version": 1,
                                "client_id": self.client_id,
                                "method": method,
                                "arguments": arguments,
                            }
                        )
                    )
                    reply = unpack(socket.recv())
                except zmq.Again as exc:
                    raise TimeoutError("runtime command timed out") from exc
        if reply.get("schema_version") != 1 or reply.get("ok") is not True:
            raise ValueError(reply.get("error", "invalid runtime response"))
        return reply["result"]


class RuntimeService:
    def __init__(self, config, directory):
        if config.physical_follower:
            raise ValueError(
                "physical PiPER-X motion requires interactive confirmation"
            )
        self.config = config
        directory = verify_endpoint(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = control_endpoint(directory)
        if self.path.exists():
            raise ValueError("command endpoint already exists; refusing to replace it")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.MAXMSGSIZE, MAX_METADATA_BYTES)
        self.socket.setsockopt(zmq.SNDTIMEO, 50)
        try:
            self.socket.bind(f"ipc://{self.path}")
            self.path.chmod(0o600)
        except Exception:
            self.socket.close()
            self.context.term()
            raise
        self.session = None
        self.owner = None
        self.heartbeat_at = 0
        self.stopping = threading.Event()

    def stop(self):
        if self.session:
            self.session.stop()
        self.stopping.set()

    def _handle(self, request):
        if (
            set(request) != {"schema_version", "client_id", "method", "arguments"}
            or type(request["schema_version"]) is not int
            or request["schema_version"] != 1
        ):
            raise ValueError("invalid command schema")
        client, method, args = (
            request["client_id"],
            request["method"],
            request["arguments"],
        )
        if (
            not isinstance(client, str)
            or not 1 <= len(client) <= 128
            or not isinstance(method, str)
            or not isinstance(args, dict)
        ):
            raise ValueError("invalid command identity or arguments")
        required = {"confirmed"} if method == "confirm" else set()
        if set(args) != required:
            raise ValueError("unexpected command arguments")
        if method == "status":
            return (
                {"phase": "IDLE", "error": None}
                if self.session is None
                else self.session.status()
            )
        if method == "acquire":
            if self.owner is not None and self.owner != client:
                raise ValueError("another client owns the session")
            self.owner = client
            self.heartbeat_at = time.monotonic()
            return {"client_id": client}
        if self.owner != client:
            raise ValueError("client does not own the session")
        if method not in {
            "prepare",
            "confirm",
            "record",
            "save",
            "discard",
            "stop",
            "preview",
            "heartbeat",
            "shutdown",
        }:
            raise ValueError("unknown runtime command")
        if method not in {"preview"}:
            self.heartbeat_at = time.monotonic()
        if method == "heartbeat":
            return {"accepted": True}
        if method == "shutdown":
            self.stop()
            return {"accepted": True}
        if method == "prepare":
            if self.session is not None and not self.session.wait(0):
                raise ValueError("session is already running")
            self.session = Session(self.config)
            return self.session.prepare()
        if self.session is None:
            raise ValueError("prepare a session first")
        return getattr(self.session, method)(**args)

    def run(self):
        try:
            while not self.stopping.is_set():
                if (
                    self.session
                    and self.owner
                    and time.monotonic() - self.heartbeat_at >= self.config.watchdog_s
                ):
                    self.session.stop("client watchdog expired")
                if not self.socket.poll(20):
                    continue
                try:
                    parts = self.socket.recv_multipart()
                    if len(parts) != 1:
                        raise ValueError("command must have one frame")
                    result = self._handle(unpack(parts[0]))
                    reply = {"ok": True, "result": result}
                except (ValueError, TypeError, TimeoutError, KeyError) as exc:
                    reply = {"ok": False, "error": str(exc)[:512]}
                try:
                    self.socket.send(pack({"schema_version": 1, **reply}))
                except zmq.Again:
                    self.stop()
        finally:
            self.stop()
            if self.session:
                self.session.wait(
                    self.config.startup_timeout_s + self.config.rpc_timeout_s * 4 + 1
                )
            self.socket.close()
            self.context.term()
            self.path.unlink(missing_ok=True)
