"""One actor owns the control/data sockets; RPC and disk have separate workers."""

import math
import queue
import threading
import time
import uuid
from dataclasses import replace

from agilex_contract import Ack, Command, JointState, Sample, to_wire

from agx_transport import HalClient

from .recording import Recorder
from .safety import JointMapping, SafetyFault, StreamMonitor, checked_positions, fresh
from .supervisor import Supervisor


class Session:
    def __init__(self, config):
        self.config = config
        self.id = uuid.uuid4().hex
        self.supervisor = Supervisor(config, self.id)
        self.recorder = Recorder(config.data_root, config.record)
        self.episode = None
        self.phase = "IDLE"
        self.error = None
        self.warnings = []
        self.target = None
        self.exit_actions = {}
        self._motion_authorized = False
        self.clients = {}
        self.monitor = None
        self.mapping = None
        self._stop = threading.Event()
        self._done = threading.Event()
        self._requests = queue.Queue(16)
        self._events = queue.Queue()
        self._thread = None
        self._seq = 0
        self._last_ack_ns = None
        self._last_submitted = -1
        self._last_sent = -1
        self._record_tick = 0
        self._renew_stop = threading.Event()
        self._snapshot = {"phase": "IDLE", "error": None, "session_id": self.id}

    def prepare(self):
        if self._thread is not None:
            raise ValueError("session is already prepared; create a new session")
        self.phase = "PREPARING"
        self._publish()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self.status()

    def status(self):
        return self._snapshot.copy()

    def _publish(self):
        episode = self.episode
        self._snapshot = {
            "session_id": self.id,
            "phase": self.phase,
            "error": self.error,
            "warnings": self.warnings[:32],
            "target": self.target,
            "cleanup_errors": list(self.supervisor.cleanup_errors),
            "episode": None
            if episode is None
            else {
                "id": episode.id,
                "path": str(episode.path),
                "phase": episode.phase,
                "error": episode.error,
                "start_mono_ns": episode.start_ns,
                "end_mono_ns": episode.end_ns,
            },
            "hal_pids": {name: p.pid for name, p in self.supervisor.processes.items()},
            "commands_sent": self._last_sent + 1,
            "exit_actions": dict(self.exit_actions),
        }

    def _call(self, action, **arguments):
        if (
            self.phase in ("IDLE", "PREPARING", "STOPPING", "CLEANUP", "FAILED")
            or self._done.is_set()
        ):
            raise ValueError(f"{action} is unavailable in {self.phase}")
        response = queue.Queue(1)
        try:
            self._requests.put_nowait((action, arguments, response))
        except queue.Full as exc:
            raise ValueError("session request queue is full") from exc
        try:
            result = response.get(timeout=self.config.rpc_timeout_s)
        except queue.Empty as exc:
            # A client cannot safely assume a timed-out mutation was not applied.
            self.stop("session command acknowledgement timed out")
            raise TimeoutError("session command timed out; session stopping") from exc
        if isinstance(result, Exception):
            raise result
        return result

    def confirm(self, confirmed):
        return self._call("confirm", confirmed=confirmed)

    def record(self):
        return self._call("record")

    def save(self):
        return self._call("save")

    def discard(self):
        return self._call("discard")

    def preview(self):
        return self._call("preview")

    def stop(self, reason=None):
        if reason and not self.error:
            self.error = str(reason)
        self._stop.set()
        return {"accepted": True}

    def wait(self, timeout=None):
        return self._done.wait(timeout)

    def _validate(self):
        descriptors = self.supervisor.descriptors
        self.monitor = StreamMonitor(descriptors.values(), self.config.streams)
        described = {
            f"{d.device_id}/{s.name}" for d in descriptors.values() for s in d.streams
        }
        if set(self.monitor.policies) != described:
            raise ValueError("every described stream needs an explicit policy")
        if self.config.leader:
            self.mapping = JointMapping(
                descriptors[self.config.leader],
                descriptors[self.config.follower],
                self.config.mapping,
            )
            for name in (self.config.leader, self.config.follower):
                for stream in ("joints", "gripper"):
                    policy = self.monitor.policies.get(f"{name}/{stream}")
                    if policy is None or policy.role != "control_required":
                        raise ValueError(
                            "all consumed control streams need control_required policy"
                        )

    def _renew(self, name):
        # Each device renews independently; never waits on the recording queue.
        period = self.config.lease_timeout_s / 3
        while not self._renew_stop.wait(period):
            try:
                self.supervisor.rpc(name, "renew", owned=True)
            except Exception as exc:
                if not self._renew_stop.is_set():
                    self._events.put((name, str(exc)))
                return

    def _receive(self):
        for name, client in self.clients.items():
            for _ in range(128):
                event = client.receive()
                if event is None:
                    break
                if isinstance(event, Sample):
                    if event.header.device_id != name:
                        raise SafetyFault("HAL published another device's sample")
                    self.monitor.update(event)
                    if self.episode is not None:
                        self.episode.offer(event)
                elif isinstance(event, Ack) and name == self.config.follower:
                    owner = self.supervisor.owners[name]
                    if (
                        event.session_id != owner["session_id"]
                        or event.lease != owner["lease"]
                    ):
                        continue
                    if event.status == "rejected":
                        raise SafetyFault(f"command rejected: {event.reason}")
                    if (
                        event.status == "submitted"
                        and self._last_submitted < event.cmd_seq <= self._last_sent
                    ):
                        self._last_submitted = event.cmd_seq
                        self._last_ack_ns = time.monotonic_ns()

    def _check(self, phase):
        self.warnings = self.monitor.quality(
            phase,
            time.monotonic_ns(),
            self.config.record.max_skew_ms,
            f"{self.config.leader}/joints" if self.config.leader else None,
        )
        for name in self.clients:
            try:
                self.supervisor.check_process(name)
            except RuntimeError as exc:
                if any(
                    p.device_id == name
                    and p.role != "optional"
                    and phase in p.monitor_when
                    for p in self.config.streams
                ):
                    raise SafetyFault(str(exc)) from exc
                self.warnings.append(str(exc))
        while not self._events.empty():
            name, error = self._events.get_nowait()
            if any(
                p.device_id == name and p.role != "optional"
                for p in self.config.streams
            ):
                raise SafetyFault(f"{name}: lease renewal failed: {error}")
            self.warnings.append(f"{name}: {error}")

    def _observations(self):
        return tuple(
            self.monitor.latest[f"{name}/{stream}"]
            for name in (self.config.leader, self.config.follower)
            for stream in ("joints", "gripper")
        )

    def _target(self, positions=None, step=None):
        observations = self._observations()
        leader, gripper, feedback, gripper_feedback = observations
        descriptor = self.supervisor.descriptors[self.config.follower]
        now = time.monotonic_ns()
        positions = self.mapping.target(leader) if positions is None else positions
        checked = checked_positions(descriptor, feedback, positions, now, max_step=step)
        for sample in (gripper, gripper_feedback):
            spec = self.monitor.specs[f"{sample.header.device_id}/gripper"]
            fresh(sample, spec, now)
            if (
                spec.unit != "m"
                or not isinstance(sample.payload, JointState)
                or sample.payload.names != ("gripper",)
            ):
                raise SafetyFault("invalid gripper feedback")
        width = gripper.payload.positions[0]
        limits = descriptor.gripper_range_m
        if limits is None or not limits[0] <= width <= limits[1]:
            raise SafetyFault("gripper target outside limits")
        command = Command(
            **self.supervisor.owners[self.config.follower],
            cmd_seq=self._seq,
            issued_mono_ns=now,
            expires_mono_ns=now + int(self.config.command_timeout_s * 1e9),
            joint_names=descriptor.joint_names,
            positions=checked,
            gripper_m=width,
        )
        self._seq += 1
        return command, observations

    def _requests_once(self):
        try:
            action, arguments, response = self._requests.get_nowait()
        except queue.Empty:
            return
        try:
            result = {"accepted": True}
            if action == "confirm":
                if self.phase != "CONFIRM" or arguments["confirmed"] is not True:
                    raise ValueError("motion requires explicit confirmation in CONFIRM")
                self.phase = "AUTHORIZE"
            elif action == "record":
                if self.phase not in ("READY", "FOLLOWING"):
                    raise ValueError("record requires READY/FOLLOWING")
                self._check("RECORDING")
                self.episode = self.recorder.start(
                    self.supervisor.descriptors.values(),
                    self.config.streams,
                    self.supervisor.boundary_clients(),
                    {
                        "session_id": self.id,
                        "leader": self.config.leader,
                        "follower": self.config.follower,
                        "mapping": self.config.mapping,
                        "max_command_step_rad": self.config.motion.max_command_step_rad,
                        "hal_metadata": dict(self.supervisor.metadata),
                    },
                )
                self.phase = "RECORDING"
                self._record_tick = self.episode.start_ns
            elif action == "save":
                if self.phase != "RECORDING":
                    raise ValueError("save requires RECORDING")
                self.episode.finish(time.monotonic_ns())
                self.phase = "FINISHING"
            elif action == "discard":
                if self.phase != "RECORDING":
                    raise ValueError("discard requires RECORDING")
                self.episode.discard()
                self.phase = "FINISHING"
            elif action == "preview":
                result = {}
                for key, sample in self.monitor.latest.items():
                    wire = to_wire(sample)
                    data = wire["payload"].pop("data", None)
                    if data is not None:
                        wire["payload"]["byte_count"] = len(data)
                    result[key] = wire
            self._publish()
            response.put_nowait(result)
        except Exception as exc:
            response.put_nowait(exc)
            if isinstance(exc, SafetyFault):
                self.stop(str(exc))

    def _align(self):
        if self._stop.is_set():
            return
        self._check("READY")
        follower = self.config.follower
        self.supervisor.rpc(follower, "authorize", owned=True)
        self._motion_authorized = True
        self.supervisor.rpc(follower, "align_begin", owned=True)
        self.phase = "ALIGN"
        self._publish()
        deadline = time.monotonic() + self.config.motion.alignment_timeout_s
        first = True
        zero_first = (
            self.supervisor.descriptors[follower].exit_policy == "piperx_return_zero"
        )
        while not self._stop.is_set():
            self._receive()
            self._check("ALIGN")
            command, observations = self._target(
                positions=(0.0,) * len(self.mapping.target_names)
                if zero_first
                else None,
                step=self.config.motion.transition_step_rad,
            )
            if zero_first:
                command = replace(command, gripper_m=None)
            desired = (
                (0.0,) * len(command.positions)
                if zero_first
                else self.mapping.target(observations[0])
            )
            error = max(
                abs(a - b)
                for a, b in zip(desired, observations[2].payload.positions, strict=True)
            )
            if (
                first
                and not zero_first
                and error > self.config.motion.max_start_error_rad
            ):
                raise SafetyFault("starting position error exceeds limit")
            if self._stop.is_set():
                return
            if not first and error <= math.radians(
                self.config.motion.position_tolerance_deg
            ):
                if zero_first:
                    zero_first, first = False, True
                    continue
                self.supervisor.rpc(follower, "activate", owned=True)
                self._receive()
                self._last_ack_ns = time.monotonic_ns()
                self.phase = "FOLLOWING"
                return
            ack = self.supervisor.rpc(follower, "align_step", command=command)
            if ack.status != "submitted":
                raise SafetyFault(f"alignment rejected: {ack.reason}")
            first = False
            if time.monotonic() >= deadline:
                raise SafetyFault("alignment timed out")
            self._stop.wait(1 / self.config.control_hz)

    def _tick(self, now):
        if self._stop.is_set():
            return
        phase = self.phase
        self._check(
            "RECORDING"
            if phase == "FINISHING"
            else "READY"
            if phase == "CONFIRM"
            else phase
        )
        if phase in ("FOLLOWING", "RECORDING", "FINISHING") and self.mapping:
            if now - self._last_ack_ns >= self.config.ack_timeout_s * 1e9:
                raise SafetyFault("command acknowledgement timed out")
            command, observations = self._target(
                step=self.config.motion.max_command_step_rad
            )
            if not self._stop.is_set() and self.clients[self.config.follower].send(
                command
            ):
                self._last_sent = command.cmd_seq
                if self.episode:
                    self.episode.command(command, observations)
        if (
            phase == "RECORDING"
            and self.config.record.mode == "sampled"
            and now >= self._record_tick
        ):
            samples = [
                self.monitor.latest[key]
                for key in self.monitor.policies
                if key in self.monitor.latest
            ]
            # The first grid point waits until every required stream belongs to
            # this episode. No pre-roll observations are smuggled into raw.
            required = [
                s
                for s in samples
                if self.monitor.policies[f"{s.header.device_id}/{s.header.stream}"].role
                != "optional"
            ]
            if required and all(
                s.header.t_sample_ns >= self.episode.start_ns for s in required
            ):
                samples = [
                    s
                    for s in samples
                    if s.header.t_sample_ns is not None
                    and s.header.t_sample_ns >= self.episode.start_ns
                ]
                self.episode.selection(now, samples)
                self._record_tick = now + int(1e9 / self.config.record.dataset_fps)
        if self.episode and self.episode.done:
            if self.episode.error:
                raise SafetyFault(self.episode.error)
            if phase == "FINISHING":
                self.phase = "FOLLOWING" if self.mapping else "READY"
        self._publish()

    def _exit_motion(self):
        name = self.config.follower
        if not name or not self._motion_authorized:
            return
        descriptor = self.supervisor.descriptors[name]
        if descriptor.exit_policy not in ("simulated_zero", "piperx_return_zero"):
            return
        result = {"result": "refused", "steps": 0}
        self.exit_actions[name] = result
        cleanup_owned = False
        physical = descriptor.exit_policy == "piperx_return_zero"
        try:
            self._receive()
            feedback = self.monitor.latest[f"{name}/joints"]
            zero = (0.0,) * len(descriptor.joint_names)
            checked_positions(
                descriptor,
                feedback,
                zero,
                time.monotonic_ns(),
                max_step=self.config.motion.transition_step_rad,
            )
            # The original following lease has already been revoked. A fresh
            # synthetic cleanup authority cannot revive its pending commands.
            cleanup_id = self.id if physical else uuid.uuid4().hex
            previous_lease = self.supervisor.owners[name]["lease"]
            lease = self.supervisor.rpc(name, "acquire", session_id=cleanup_id)["lease"]
            if lease == previous_lease:
                raise SafetyFault("original lease has not been revoked")
            self.supervisor.owners[name] = {"session_id": cleanup_id, "lease": lease}
            cleanup_owned = True
            method = "authorize_cleanup" if physical else "authorize"
            self.supervisor.rpc(name, method, owned=True)
            self.supervisor.rpc(name, "align_begin", owned=True)
            deadline = time.monotonic() + min(
                self.config.motion.alignment_timeout_s, self.config.lease_timeout_s / 2
            )
            while time.monotonic() < deadline:
                self._receive()
                feedback = self.monitor.latest[f"{name}/joints"]
                now = time.monotonic_ns()
                positions = checked_positions(
                    descriptor,
                    feedback,
                    zero,
                    now,
                    max_step=self.config.motion.transition_step_rad,
                )
                if max(abs(p) for p in feedback.payload.positions) <= math.radians(
                    self.config.motion.position_tolerance_deg
                ):
                    result.update(
                        result="completed", positions=list(feedback.payload.positions)
                    )
                    return
                command = Command(
                    **self.supervisor.owners[name],
                    cmd_seq=result["steps"],
                    issued_mono_ns=now,
                    expires_mono_ns=now + int(self.config.command_timeout_s * 1e9),
                    joint_names=descriptor.joint_names,
                    positions=positions,
                )
                ack = self.supervisor.rpc(name, "align_step", command=command)
                if ack.status != "submitted":
                    raise SafetyFault(f"zero command refused: {ack.reason}")
                result["steps"] += 1
                time.sleep(1 / self.config.control_hz)
            raise SafetyFault("return to zero timed out")
        except Exception as exc:
            result["reason"] = str(exc)
            self.supervisor.cleanup_errors.append(
                f"{name}: return to zero refused: {exc}"
            )
        finally:
            if cleanup_owned:
                try:
                    self.supervisor.rpc(name, "release", owned=True)
                except Exception as exc:
                    self.supervisor.cleanup_errors.append(
                        f"{name}: cleanup release: {exc}"
                    )

    def _run(self):
        try:
            self.supervisor.launch()
            self.supervisor.discover(self._stop)
            if self._stop.is_set():
                return
            self._validate()
            self.clients = {
                name: HalClient(directory)
                for name, directory in self.supervisor.directories.items()
            }
            for name in self.clients:
                threading.Thread(target=self._renew, args=(name,), daemon=True).start()
            deadline = time.monotonic() + self.config.startup_timeout_s
            while not self._stop.is_set():
                self._receive()
                try:
                    self._check("READY")
                    break
                except SafetyFault:
                    if time.monotonic() >= deadline:
                        raise
                    self._stop.wait(0.002)
            self.phase = "CONFIRM" if self.mapping else "READY"
            if self.mapping:
                command, _ = self._target()
                self.target = {
                    "joint_names": list(command.joint_names),
                    "positions": list(command.positions),
                    "gripper_m": command.gripper_m,
                }
            self._publish()
            next_tick = 0
            while not self._stop.is_set():
                self._receive()
                self._requests_once()
                if self._stop.is_set():
                    break
                if self.phase == "AUTHORIZE":
                    self._align()
                now = time.monotonic_ns()
                if now >= next_tick:
                    self._tick(now)
                    next_tick = now + int(1e9 / self.config.control_hz)
                self._stop.wait(0.001)
        except Exception as exc:
            self.error = self.error or str(exc)
        finally:
            self.phase = "STOPPING"
            self._renew_stop.set()
            self.recorder.close()
            self._publish()
            self.supervisor.release()
            self._exit_motion()
            self.phase = "CLEANUP"
            for client in self.clients.values():
                client.close()
            try:
                self.supervisor.close()
            except Exception as exc:
                self.supervisor.cleanup_errors.append(str(exc))
            self.phase = "FAILED" if self.error else "IDLE"
            self._publish()
            self._done.set()
