"""Lease authority is metadata-only; driver calls never hold its lock."""

import secrets
import threading

from agilex_contract import Ack, Command


class ControlGate:
    def __init__(
        self,
        device,
        *,
        command_timeout_ns=250_000_000,
        lease_timeout_ns=5_000_000_000,
        align_step_timeout_ns=1_000_000_000,
        align_total_timeout_ns=10_000_000_000,
        clock_ns=None,
    ):
        for value in (
            command_timeout_ns,
            lease_timeout_ns,
            align_step_timeout_ns,
            align_total_timeout_ns,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(
                    "control deadlines must be positive integer nanoseconds"
                )
        self.device = device
        self.command_timeout_ns, self.lease_timeout_ns = (
            command_timeout_ns,
            lease_timeout_ns,
        )
        self.align_step_timeout_ns, self.align_total_timeout_ns = (
            align_step_timeout_ns,
            align_total_timeout_ns,
        )
        self._clock_ns = clock_ns
        self._lock = threading.RLock()
        self.phase, self.reason = "DISCOVER", ""
        self.session_id = self.lease = self.pending = None
        self.lease_deadline = self.last_valid_ns = self.align_start_ns = (
            self.align_steps
        ) = self.replaced_count = 0
        self.last_seq = -1
        self._cleanup_session = None
        self._cleanup_only = False
        bind = getattr(device, "bind_authority_check", None)
        if bind is not None and clock_ns is not None:
            bind(self._require_live_lease)

    def _require_live_lease(self):
        with self._lock:
            self.tick(self._clock_ns())
            if self.lease is None:
                raise RuntimeError("motion authority is no longer live")

    def _now(self, supplied):
        return self._clock_ns() if self._clock_ns is not None else supplied

    def _revoke(self, reason, now_ns, phase="FAULTED"):
        self.phase, self.reason = phase, reason
        self.session_id = self.lease = self.pending = None
        self.align_steps = 0
        self.device.abort_episode(now_ns)
        # revoke hooks must only invalidate device-local metadata, never do I/O.
        revoke = getattr(self.device, "revoke", None)
        if revoke is not None:
            revoke(reason)

    def tick(self, now_ns):
        with self._lock:
            if self.lease is None:
                return
            if now_ns >= self.lease_deadline:
                self._revoke("lease_expired", now_ns)
            elif (
                self.phase == "ACTIVE"
                and now_ns - self.last_valid_ns >= self.command_timeout_ns
            ):
                self._revoke("command_timeout", now_ns)
            elif self.phase == "ALIGNING":
                if now_ns - self.align_start_ns >= self.align_total_timeout_ns:
                    self._revoke("alignment_total_timeout", now_ns)
                elif now_ns - self.last_valid_ns >= self.align_step_timeout_ns:
                    self._revoke("alignment_step_timeout", now_ns)

    def _owner(self, session_id, lease, now_ns):
        self.tick(now_ns)
        if self.lease is None or (session_id, lease) != (self.session_id, self.lease):
            raise ValueError("no valid control lease for this session")

    def acquire(self, session_id, now_ns):
        if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
            raise ValueError("invalid session_id")
        with self._lock:
            self.tick(now_ns)
            if self.lease is not None:
                if session_id != self.session_id:
                    raise ValueError("another session owns the device")
                return self.lease
            self.session_id, self.lease = session_id, secrets.token_hex(16)
            self.lease_deadline = now_ns + self.lease_timeout_ns
            self.last_seq, self.reason = -1, ""
            self._cleanup_only = False
            if self._cleanup_session != session_id:
                self._cleanup_session = None
            self.phase = "PREPARED" if self.device.prepared else "DISCOVER"
            return self.lease

    def renew(self, session_id, lease, now_ns):
        with self._lock:
            self._owner(session_id, lease, now_ns)
            self.lease_deadline = now_ns + self.lease_timeout_ns

    def _transition(self, session_id, lease, now_ns, phases, hook, destination):
        with self._lock:
            self._owner(session_id, lease, now_ns)
            if self.phase not in phases:
                raise ValueError(f"{hook} requires {'/'.join(phases)}")
            if hook == "authorize" and not self.device.descriptor.joint_names:
                raise ValueError("authorize requires a controllable device")
            if hook == "authorize_cleanup":
                if (
                    self._cleanup_session != session_id
                    or self.device.descriptor.exit_policy != "piperx_return_zero"
                    or not callable(getattr(self.device, hook, None))
                ):
                    raise ValueError("cleanup requires a prior authorized session")
                self._cleanup_session = None
        try:
            function = getattr(self.device, hook, None)
            if function is not None:
                function()
        except Exception:
            with self._lock:
                if (session_id, lease) == (self.session_id, self.lease):
                    self._revoke(f"{hook}_failed", self._now(now_ns))
            raise
        with self._lock:
            self._owner(session_id, lease, self._now(now_ns))
            if self.phase not in phases:
                raise ValueError("authority changed during driver operation")
            self.phase = destination
            if hook == "authorize":
                self._cleanup_session = session_id
            elif hook == "authorize_cleanup":
                self._cleanup_only = True

    def prepare(self, session_id, lease, now_ns):
        self._transition(
            session_id, lease, now_ns, ("DISCOVER", "PREPARED"), "prepare", "PREPARED"
        )

    def authorize(self, session_id, lease, now_ns):
        self._transition(
            session_id, lease, now_ns, ("PREPARED",), "authorize", "AUTHORIZED"
        )

    def authorize_cleanup(self, session_id, lease, now_ns):
        self._transition(
            session_id, lease, now_ns, ("PREPARED",), "authorize_cleanup", "AUTHORIZED"
        )

    def begin_alignment(self, session_id, lease, now_ns):
        with self._lock:
            self._owner(session_id, lease, now_ns)
            if self.phase != "AUTHORIZED":
                raise ValueError("alignment requires authorization")
            self.phase = "ALIGNING"
            self.align_start_ns = self.last_valid_ns = now_ns
            self.align_steps = 0

    def _validate(self, command, now_ns, phase):
        self._owner(command.session_id, command.lease, now_ns)
        if self._cleanup_only and command.gripper_m is not None:
            raise ValueError("cleanup does not authorize gripper commands")
        if self.phase != phase:
            raise ValueError(f"command requires {phase}")
        if not command.issued_mono_ns <= now_ns < command.expires_mono_ns:
            raise ValueError("command is future-dated or expired")
        if command.cmd_seq <= self.last_seq:
            raise ValueError("command sequence is not increasing")
        d = self.device.descriptor
        if command.joint_names != d.joint_names:
            raise ValueError("command channel order does not match descriptor")
        for value, limits in zip(command.positions, d.joint_limits, strict=True):
            if not limits[0] <= value <= limits[1]:
                raise ValueError("joint target outside limits")
        if command.gripper_m is not None:
            limits = d.gripper_range_m
            if limits is None or not limits[0] <= command.gripper_m <= limits[1]:
                raise ValueError("gripper target outside limits")

    @staticmethod
    def _ack(command, status, now_ns, reason=""):
        return Ack(
            command.session_id, command.lease, command.cmd_seq, status, now_ns, reason
        )

    def _apply(self, command, now_ns, phase):
        try:
            self.device.apply(command)
            with self._lock:
                finished = self._now(now_ns)
                self._owner(command.session_id, command.lease, finished)
                if self.phase != phase or finished >= command.expires_mono_ns:
                    raise ValueError("authority or command expired during submission")
                if phase == "ALIGNING":
                    self.align_steps += 1
                    self.last_valid_ns = finished
            return self._ack(command, "submitted", finished)
        except Exception as exc:
            with self._lock:
                if (command.session_id, command.lease) == (self.session_id, self.lease):
                    self._revoke("submission_failed", self._now(now_ns))
            return self._ack(command, "rejected", self._now(now_ns), str(exc))

    def alignment_step(self, command: Command, now_ns):
        with self._lock:
            try:
                self._validate(command, now_ns, "ALIGNING")
            except ValueError as exc:
                return self._ack(command, "rejected", now_ns, str(exc))
            self.last_seq = command.cmd_seq
        return self._apply(command, now_ns, "ALIGNING")

    def activate(self, session_id, lease, now_ns):
        with self._lock:
            self._owner(session_id, lease, now_ns)
            if self._cleanup_only or self.phase != "ALIGNING" or self.align_steps == 0:
                raise ValueError("activate requires completed alignment")
            self.phase = "ACTIVE"
            self.last_valid_ns = now_ns

    def accept(self, command: Command, now_ns):
        with self._lock:
            try:
                self._validate(command, now_ns, "ACTIVE")
            except ValueError as exc:
                return self._ack(command, "rejected", now_ns, str(exc))
            if self.pending is not None:
                self.replaced_count += 1
            self.pending = command
            self.last_seq = command.cmd_seq
            self.last_valid_ns = now_ns
            return self._ack(command, "accepted", now_ns)

    def submit_pending(self, now_ns):
        with self._lock:
            self.tick(now_ns)
            command, self.pending = self.pending, None
            if command is None:
                return None
            if now_ns >= command.expires_mono_ns:
                return self._ack(
                    command, "rejected", now_ns, "command expired before submission"
                )
            self._owner(command.session_id, command.lease, now_ns)
        return self._apply(command, now_ns, "ACTIVE")

    def release(self, session_id, lease, now_ns):
        with self._lock:
            self._owner(session_id, lease, now_ns)
            self._revoke("released", now_ns, "RELEASED")

    def status(self, now_ns):
        with self._lock:
            self.tick(now_ns)
            return dict(
                phase=self.phase,
                reason=self.reason,
                owner=self.session_id,
                pending=self.pending is not None,
                replaced_count=self.replaced_count,
                positions=list(self.device.positions),
                stream_epoch=self.device.epoch,
            )
