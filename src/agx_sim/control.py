"""Device-local authority, independent of runtime and recording progress."""

import secrets

from agilex_contract import Ack, Command

from .devices import SimDevice


class ControlGate:
    def __init__(
        self,
        device: SimDevice,
        *,
        command_timeout_ns=250_000_000,
        lease_timeout_ns=5_000_000_000,
        align_step_timeout_ns=1_000_000_000,
        align_total_timeout_ns=10_000_000_000,
    ):
        self.device = device
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
        self.command_timeout_ns = command_timeout_ns
        self.lease_timeout_ns = lease_timeout_ns
        self.align_step_timeout_ns = align_step_timeout_ns
        self.align_total_timeout_ns = align_total_timeout_ns
        self.phase = "DISCOVER"
        self.session_id = None
        self.lease = None
        self.lease_deadline = 0
        self.pending: Command | None = None
        self.last_seq = -1
        self.last_valid_ns = 0
        self.align_start_ns = 0
        self.align_steps = 0
        self.replaced_count = 0
        self.reason = ""

    def _revoke(self, reason, phase="FAULTED"):
        self.phase = phase
        self.reason = reason
        self.lease = None
        self.session_id = None
        self.pending = None
        self.align_steps = 0

    def tick(self, now_ns):
        if self.lease is None:
            return
        if now_ns >= self.lease_deadline:
            self._revoke("lease_expired")
        elif (
            self.phase == "ACTIVE"
            and now_ns - self.last_valid_ns >= self.command_timeout_ns
        ):
            self._revoke("command_timeout")
        elif self.phase == "ALIGNING":
            if now_ns - self.align_start_ns >= self.align_total_timeout_ns:
                self._revoke("alignment_total_timeout")
            elif now_ns - self.last_valid_ns >= self.align_step_timeout_ns:
                self._revoke("alignment_step_timeout")

    def _owner(self, session_id, lease, now_ns):
        self.tick(now_ns)
        if self.lease is None or session_id != self.session_id or lease != self.lease:
            raise ValueError("no valid control lease for this session")

    def acquire(self, session_id: str, now_ns: int) -> str:
        if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
            raise ValueError("invalid session_id")
        self.tick(now_ns)
        if self.lease is not None:
            if session_id != self.session_id:
                raise ValueError("another session owns the device")
            return self.lease
        self.session_id = session_id
        self.lease = secrets.token_hex(16)
        self.lease_deadline = now_ns + self.lease_timeout_ns
        self.last_seq = -1
        self.phase = "PREPARED" if self.device.prepared else "DISCOVER"
        self.reason = ""
        return self.lease

    def renew(self, session_id, lease, now_ns):
        self._owner(session_id, lease, now_ns)
        self.lease_deadline = now_ns + self.lease_timeout_ns

    def prepare(self, session_id, lease, now_ns):
        self._owner(session_id, lease, now_ns)
        if self.phase not in ("DISCOVER", "PREPARED"):
            raise ValueError("prepare requires DISCOVER/PREPARED")
        self.device.prepare()
        self.phase = "PREPARED"

    def authorize(self, session_id, lease, now_ns):
        self._owner(session_id, lease, now_ns)
        if self.phase != "PREPARED" or not self.device.descriptor.joint_names:
            raise ValueError("authorize requires a prepared controllable device")
        self.phase = "AUTHORIZED"

    def begin_alignment(self, session_id, lease, now_ns):
        self._owner(session_id, lease, now_ns)
        if self.phase != "AUTHORIZED":
            raise ValueError("alignment requires authorization")
        self.phase = "ALIGNING"
        self.align_start_ns = self.last_valid_ns = now_ns
        self.align_steps = 0

    def _validate(self, command, now_ns, phase):
        self._owner(command.session_id, command.lease, now_ns)
        if self.phase != phase:
            raise ValueError(f"command requires {phase}")
        if not command.issued_mono_ns <= now_ns < command.expires_mono_ns:
            raise ValueError("command is future-dated or expired")
        if command.cmd_seq <= self.last_seq:
            raise ValueError("command sequence is not increasing")
        descriptor = self.device.descriptor
        if command.joint_names != descriptor.joint_names:
            raise ValueError("command channel order does not match descriptor")
        for value, limits in zip(
            command.positions, descriptor.joint_limits, strict=True
        ):
            if not limits[0] <= value <= limits[1]:
                raise ValueError("joint target outside limits")
        if command.gripper_m is not None:
            limits = descriptor.gripper_range_m
            if limits is None or not limits[0] <= command.gripper_m <= limits[1]:
                raise ValueError("gripper target outside limits")

    @staticmethod
    def _ack(command, status, now_ns, reason=""):
        return Ack(
            command.session_id, command.lease, command.cmd_seq, status, now_ns, reason
        )

    def alignment_step(self, command: Command, now_ns: int) -> Ack:
        try:
            self._validate(command, now_ns, "ALIGNING")
        except ValueError as exc:
            return self._ack(command, "rejected", now_ns, str(exc))
        self.device.apply(command)
        self.last_seq = command.cmd_seq
        self.last_valid_ns = now_ns
        self.align_steps += 1
        return self._ack(command, "submitted", now_ns)

    def activate(self, session_id, lease, now_ns):
        self._owner(session_id, lease, now_ns)
        if self.phase != "ALIGNING" or self.align_steps == 0:
            raise ValueError("activate requires completed simulated alignment")
        self.phase = "ACTIVE"
        self.last_valid_ns = now_ns

    def accept(self, command: Command, now_ns: int) -> Ack:
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

    def submit_pending(self, now_ns: int) -> Ack | None:
        self.tick(now_ns)
        command, self.pending = self.pending, None
        if command is None:
            return None
        if now_ns >= command.expires_mono_ns:
            return self._ack(
                command, "rejected", now_ns, "command expired before submission"
            )
        self.device.apply(command)
        return self._ack(command, "submitted", now_ns)

    def release(self, session_id, lease, now_ns):
        self._owner(session_id, lease, now_ns)
        self._revoke("released", "RELEASED")

    def status(self, now_ns):
        self.tick(now_ns)
        return {
            "phase": self.phase,
            "reason": self.reason,
            "owner": self.session_id,
            "pending": self.pending is not None,
            "replaced_count": self.replaced_count,
            "positions": list(self.device.positions),
            "stream_epoch": self.device.epoch,
        }
