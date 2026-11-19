"""Own only explicitly launched synthetic HALs; management never shares data sockets."""

import fcntl
import json
import os
import stat
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from agilex_contract import DeviceDescriptor

from agx_hal.config import EFFECTS, MODULES
from agx_transport import request, verify_endpoint


class BoundaryClient:
    def __init__(self, supervisor, device_id):
        self.supervisor, self.device_id = supervisor, device_id

    def request(self, method, **arguments):
        return self.supervisor.rpc(self.device_id, method, owned=True, **arguments)


class Supervisor:
    def __init__(self, config, session_id):
        self.config, self.session_id = config, session_id
        self.processes = {}
        self.directories = {}
        self.owners = {}
        self.descriptors = {}
        self.metadata = {}
        self.cleanup_errors = []
        self._temporary = None
        self._logs = {}
        self._lock_fd = None
        self._boundary_clients = {}

    def launch(self):
        self._lock_fd = os.open(
            self.config.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        info = os.fstat(self._lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("session lock must be an owned regular file")
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("session lock is held by another controller") from exc
        self._temporary = tempfile.TemporaryDirectory(prefix="agx-p2-")
        for index, device in enumerate(self.config.devices):
            directory = (
                Path(device.endpoint)
                if device.endpoint
                else Path(self._temporary.name) / str(index)
            )
            self.directories[device.device_id] = verify_endpoint(directory)
            self._boundary_clients[device.device_id] = BoundaryClient(
                self, device.device_id
            )
            if device.endpoint:
                continue
            command = [
                device.python,
                "-m",
                MODULES[device.backend],
                "serve",
                "--device-id",
                device.device_id,
                "--endpoint-dir",
                str(directory),
                "--command-timeout-s",
                str(self.config.command_timeout_s),
                "--lease-timeout-s",
                str(self.config.lease_timeout_s),
                "--exit-policy",
                device.exit_policy,
            ]
            if device.backend == "sim":
                command += ["--kind", device.kind, "--axes", str(device.axes)]
            else:
                settings = Path(self._temporary.name) / f"settings-{index}.json"
                settings.write_text(json.dumps(device.settings, allow_nan=False))
                os.chmod(settings, 0o600)
                command += ["--settings-json", str(settings)]
            if device.hz is not None:
                command += ["--hz", str(device.hz)]
            elif device.backend in ("gello", "piperx"):
                command += ["--hz", str(self.config.control_hz)]
            log = tempfile.TemporaryFile(mode="w+b")
            self._logs[device.device_id] = log
            self.processes[device.device_id] = subprocess.Popen(
                command, stdout=log, stderr=log, start_new_session=True
            )

    def rpc(self, device_id, method, *, owned=False, **arguments):
        if owned:
            arguments = {**self.owners[device_id], **arguments}
        deployment = next(
            (d for d in self.config.devices if d.device_id == device_id), None
        )
        timeout = self.config.rpc_timeout_s
        if deployment is not None and deployment.backend != "sim":
            if method == "prepare":
                timeout = self.config.startup_timeout_s
            elif method == "authorize":
                timeout = self.config.motion.alignment_timeout_s
        return request(
            self.directories[device_id],
            method,
            timeout_ms=max(1, int(timeout * 1000)),
            **arguments,
        )

    def discover(self, stop):
        deadline = time.monotonic() + self.config.startup_timeout_s
        pending = {d.device_id: d for d in self.config.devices}
        while pending and not stop.is_set():
            for name, device in list(pending.items()):
                self.check_process(name)
                try:
                    descriptor = self.rpc(name, "hello")
                except TimeoutError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"{name}: HAL discovery timed out") from None
                    continue
                if (
                    not isinstance(descriptor, DeviceDescriptor)
                    or descriptor.device_id != name
                    or descriptor.model
                    != (
                        f"sim-{device.kind}"
                        if device.backend == "sim"
                        else device.backend
                    )
                    or descriptor.disconnect_behavior
                    != ("simulated" if device.backend == "sim" else "unverified")
                    or descriptor.exit_policy != device.exit_policy
                ):
                    raise ValueError(
                        f"{name}: HAL descriptor does not match backend/policy"
                    )
                if descriptor.prepare_effects != EFFECTS[device.backend]:
                    raise ValueError(f"{name}: unexpected prepare side effects")
                self.descriptors[name] = descriptor
                lease = self.rpc(name, "acquire", session_id=self.session_id)["lease"]
                self.owners[name] = {"session_id": self.session_id, "lease": lease}
                self.rpc(name, "prepare", owned=True)
                if device.backend != "sim":
                    final = self.rpc(name, "hello")
                    if (
                        final.device_id,
                        final.model,
                        final.exit_policy,
                        final.prepare_effects,
                    ) != (
                        descriptor.device_id,
                        descriptor.model,
                        descriptor.exit_policy,
                        descriptor.prepare_effects,
                    ):
                        raise ValueError(
                            f"{name}: device identity/policy changed during prepare"
                        )
                    self.descriptors[name] = final
                    self.metadata[name] = self.rpc(name, "metadata")
                del pending[name]
        if not self.descriptors:
            raise ValueError("a session needs at least one simulated device")

    def check_process(self, name):
        process = self.processes.get(name)
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"{name}: HAL exited with status {process.returncode}")

    def boundary_clients(self):
        return self._boundary_clients

    def release(self):
        # Independent RPC sockets and workers: a stuck boundary call cannot queue
        # ahead of authority revocation. The HAL also owns its own watchdog.
        finished = []
        for name in tuple(self.owners):
            event = threading.Event()
            finished.append(event)

            def revoke(device_id=name, done=event):
                try:
                    self.rpc(device_id, "release", owned=True)
                except Exception as exc:
                    self.cleanup_errors.append(f"{device_id}: release: {exc}")
                finally:
                    done.set()

            threading.Thread(target=revoke, daemon=True).start()
        deadline = time.monotonic() + self.config.rpc_timeout_s * 2 + 0.05
        for event in finished:
            event.wait(max(0, deadline - time.monotonic()))

    def close(self):
        for process in self.processes.values():
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 0.4
        for process in self.processes.values():
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        for log in self._logs.values():
            log.close()
        if self._temporary:
            self._temporary.cleanup()
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
