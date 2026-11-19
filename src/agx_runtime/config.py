"""One layered configuration entry point for embedded and daemon clients."""

import math
import os
import re
import sys
import tomllib
import warnings
from dataclasses import dataclass, field, fields
from pathlib import Path

from agx_hal.config import BACKENDS, POLICIES, validate_settings

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config/default.toml"
PHASES = {
    "PREPARING",
    "READY",
    "CONFIRM",
    "AUTHORIZE",
    "ALIGN",
    "FOLLOWING",
    "RECORDING",
    "FINISHING",
    "STOPPING",
    "CLEANUP",
}
CONTROL_PHASES = {"READY", "ALIGN", "FOLLOWING", "RECORDING"}


def positive(value, name, *, integer=False):
    if (
        type(value) not in ((int,) if integer else (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(
            f"{name} must be a finite positive {'integer' if integer else 'number'}"
        )


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value
    ):
        raise ValueError("identifiers must be short path-safe names")
    return value


@dataclass(frozen=True)
class RecordConfig:
    mode: str = "full"
    dataset_fps: int = 30
    max_skew_ms: float = 50.0
    capture_fps_max: float = 90.0
    queue_size: int = 512
    boundary_timeout_s: float = 1.0
    drain_timeout_s: float = 5.0

    def __post_init__(self):
        if self.mode not in ("full", "sampled"):
            raise ValueError("record.mode must be full or sampled")
        for name in ("dataset_fps", "queue_size"):
            positive(getattr(self, name), name, integer=True)
        for name in (
            "max_skew_ms",
            "capture_fps_max",
            "boundary_timeout_s",
            "drain_timeout_s",
        ):
            positive(getattr(self, name), name)


@dataclass(frozen=True)
class MotionConfig:
    position_tolerance_deg: float = 1.5
    max_start_error_rad: float = 0.35
    transition_step_rad: float = 0.02
    max_command_step_rad: float = 1.0
    alignment_timeout_s: float = 10.0

    def __post_init__(self):
        for item in fields(self):
            positive(getattr(self, item.name), item.name)
        if self.transition_step_rad > 0.05:
            raise ValueError("transition_step_rad must be at most 0.05")


@dataclass(frozen=True)
class DeviceConfig:
    device_id: str
    kind: str
    axes: int = 6
    hz: float | None = None
    python: str = field(default_factory=lambda: sys.executable)
    endpoint: str | None = None
    exit_policy: str = ""
    backend: str = "sim"
    settings: dict = field(default_factory=dict)

    def __post_init__(self):
        identifier(self.device_id)
        if self.backend not in BACKENDS or self.kind not in BACKENDS[self.backend]:
            raise ValueError("incompatible HAL backend and device kind")
        validate_settings(self.backend, self.settings)
        if not self.exit_policy:
            object.__setattr__(self, "exit_policy", POLICIES[self.backend][0])
        if self.kind not in ("leader", "follower", "camera", "wrench"):
            raise ValueError("P2 only supports synthetic HAL devices")
        if type(self.axes) is not int or not 1 <= self.axes <= 32:
            raise ValueError("axes must be in [1, 32]")
        if self.hz is not None:
            positive(self.hz, "device hz")
            if self.hz > 1000:
                raise ValueError("device hz exceeds simulation limit")
        if not isinstance(self.python, str) or not self.python:
            raise ValueError("device python must be an interpreter path")
        if self.endpoint is not None and (
            not isinstance(self.endpoint, str) or not Path(self.endpoint).is_absolute()
        ):
            raise ValueError("existing endpoint must be an absolute local directory")
        if self.exit_policy not in POLICIES[self.backend]:
            raise ValueError("unsupported device exit policy")


@dataclass(frozen=True)
class StreamPolicy:
    device_id: str
    stream: str
    role: str
    monitor_when: tuple[str, ...]

    def __post_init__(self):
        identifier(self.device_id)
        identifier(self.stream)
        if self.role not in ("control_required", "record_required", "optional"):
            raise ValueError("invalid stream role")
        if (
            not self.monitor_when
            or any(p not in PHASES for p in self.monitor_when)
            or len(set(self.monitor_when)) != len(self.monitor_when)
        ):
            raise ValueError("invalid monitor_when phases")
        if self.role == "control_required" and not CONTROL_PHASES <= set(
            self.monitor_when
        ):
            raise ValueError("control_required must monitor all consuming phases")
        if self.role == "record_required" and not {"READY", "RECORDING"} <= set(
            self.monitor_when
        ):
            raise ValueError("record_required must monitor readiness and recording")

    @property
    def key(self):
        return f"{self.device_id}/{self.stream}"


@dataclass(frozen=True)
class RuntimeConfig:
    record: RecordConfig = field(default_factory=RecordConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    devices: tuple[DeviceConfig, ...] = ()
    streams: tuple[StreamPolicy, ...] = ()
    control_hz: float = 50.0
    leader: str = ""
    follower: str = ""
    data_root: str = "data/raw-v3"
    lock_path: str = "/tmp/start_gello_follow.lock"
    startup_timeout_s: float = 5.0
    rpc_timeout_s: float = 0.2
    ack_timeout_s: float = 0.25
    command_timeout_s: float = 0.25
    lease_timeout_s: float = 3.0
    watchdog_s: float = 1.0
    mapping: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in (
            "control_hz",
            "startup_timeout_s",
            "rpc_timeout_s",
            "ack_timeout_s",
            "command_timeout_s",
            "lease_timeout_s",
            "watchdog_s",
        ):
            positive(getattr(self, name), name)
        if self.control_hz > 1000 or 1 / self.control_hz >= min(
            self.ack_timeout_s, self.command_timeout_s
        ):
            raise ValueError("command/ack deadline must exceed a control period")
        if self.record.dataset_fps > self.control_hz and self.record.mode == "sampled":
            raise ValueError("sampled FPS cannot exceed control frequency")
        names = {d.device_id for d in self.devices}
        if len(names) != len(self.devices) or len({p.key for p in self.streams}) != len(
            self.streams
        ):
            raise ValueError("duplicate device or stream policy")
        if any(p.device_id not in names for p in self.streams):
            raise ValueError("policy references an unknown device")
        if bool(self.leader) != bool(self.follower):
            raise ValueError("teleoperation needs both leader and follower")
        if self.leader and (
            self.leader not in names
            or self.follower not in names
            or self.leader == self.follower
        ):
            raise ValueError("invalid leader/follower devices")
        if self.record.mode == "sampled" and (
            not self.leader or any(d.kind == "wrench" for d in self.devices)
        ):
            raise ValueError(
                "sampled requires a teleoperation time grid; "
                "multi-rate sensors use full"
            )
        for name in ("data_root", "lock_path"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be a path")

    @property
    def physical_follower(self):
        return any(
            device.device_id == self.follower and device.backend == "piperx"
            for device in self.devices
        )


def _model(cls, values):
    if not isinstance(values, dict) or set(values) - {f.name for f in fields(cls)}:
        raise ValueError(f"unknown fields in {cls.__name__}")
    try:
        return cls(**values)
    except TypeError as exc:
        raise ValueError(f"invalid {cls.__name__}: {exc}") from exc


def load_config(path=None, overrides=None):
    base = {}
    if DEFAULT_CONFIG.is_file():
        with DEFAULT_CONFIG.open("rb") as stream:
            base = tomllib.load(stream)
    values = {key: base.get(key, {}).copy() for key in ("runtime", "record", "motion")}
    values.update(devices=[], streams=[], mapping={})
    layers = []
    if path is not None and Path(path).resolve() != DEFAULT_CONFIG:
        with Path(path).open("rb") as stream:
            layers.append(tomllib.load(stream))
    if overrides is not None:
        layers.append(overrides)
    allowed = {
        "runtime",
        "record",
        "motion",
        "devices",
        "streams",
        "mapping",
        "robot",
        "gello",
        "recording",
        "safety",
        "camera",
        "paths",
        "collection",
    }
    for layer in layers:
        if not isinstance(layer, dict) or set(layer) - allowed:
            raise ValueError("unknown runtime configuration section")
        if "recording" in layer:
            warnings.warn(
                "[recording] is legacy; migrate dataset_fps/queue_size to [record]",
                UserWarning,
                stacklevel=2,
            )
            for key in ("dataset_fps", "queue_size"):
                if key in layer["recording"]:
                    values["record"][key] = layer["recording"][key]
        for key in ("runtime", "record", "motion", "mapping"):
            if key in layer:
                if not isinstance(layer[key], dict):
                    raise ValueError(f"{key} must be a table")
                values[key].update(layer[key])
        for key in ("devices", "streams"):
            if key in layer:
                if not isinstance(layer[key], list):
                    raise ValueError(f"{key} must be an array of tables")
                values[key] = layer[key]
    deployments = []
    directory = (
        Path(path).resolve().parent if path is not None else DEFAULT_CONFIG.parent
    )
    for device in values["devices"]:
        device = dict(device)
        interpreter = device.get("python")
        if (
            isinstance(interpreter, str)
            and "/" in interpreter
            and not Path(interpreter).is_absolute()
        ):
            device["python"] = os.path.abspath(directory / interpreter)
        deployments.append(_model(DeviceConfig, device))
    devices = tuple(deployments)
    policies = []
    for policy in values["streams"]:
        policy = dict(policy)
        if not isinstance(policy.get("monitor_when"), list):
            raise ValueError("monitor_when must be an array")
        policy["monitor_when"] = tuple(policy["monitor_when"])
        policies.append(_model(StreamPolicy, policy))
    return _model(
        RuntimeConfig,
        dict(
            values["runtime"],
            record=_model(RecordConfig, values["record"]),
            motion=_model(MotionConfig, values["motion"]),
            devices=devices,
            streams=tuple(policies),
            mapping=values["mapping"],
        ),
    )
