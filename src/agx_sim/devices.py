"""Synthetic devices with the same descriptors and sample envelopes as HALs."""

import math
import struct
import uuid

from agilex_contract import (
    DepthFrame,
    DeviceDescriptor,
    ImageFrame,
    JointState,
    Sample,
    SampleHeader,
    StreamSpec,
    WrenchSample,
)


class SimDevice:
    def __init__(
        self, kind: str, device_id: str, *, axes: int = 6, hz: float | None = None
    ):
        if kind not in ("leader", "follower", "camera", "wrench"):
            raise ValueError("unsupported simulated device kind")
        if type(axes) is not int or not 1 <= axes <= 32:
            raise ValueError("axes must be between 1 and 32")
        self.kind = kind
        self.hz = (
            hz if hz is not None else {"camera": 30.0, "wrench": 200.0}.get(kind, 50.0)
        )
        if (
            type(self.hz) not in (float, int)
            or not math.isfinite(self.hz)
            or not 0 < self.hz <= 1000
        ):
            raise ValueError("simulation hz must be in (0, 1000]")
        stale_ns = int(3e9 / self.hz)
        names = tuple(f"joint_{i + 1}" for i in range(axes))
        self.positions = (0.0,) * axes
        self.gripper_m = 0.04
        self.prepared = False
        self.epoch = uuid.uuid4().hex
        self._seq = {}
        self._cached = {}
        if kind in ("leader", "follower"):
            streams = (
                StreamSpec("joints", "joint", names, "rad", self.hz, stale_ns),
                StreamSpec("gripper", "joint", ("gripper",), "m", self.hz, stale_ns),
            )
        elif kind == "camera":
            streams = tuple(
                StreamSpec(
                    name,
                    name,
                    (),
                    "rgb8" if name == "rgb" else "z16_le",
                    self.hz,
                    stale_ns,
                )
                for name in ("rgb", "depth")
            )
        else:
            streams = (
                StreamSpec(
                    "wrench",
                    "wrench",
                    ("fx", "fy", "fz", "tx", "ty", "tz"),
                    "N,N*m",
                    self.hz,
                    stale_ns,
                ),
            )
        self.descriptor = DeviceDescriptor(
            device_id,
            f"sim-{kind}",
            f"synthetic-{device_id}",
            "0.1.0",
            streams,
            names if kind == "follower" else (),
            ((-math.pi, math.pi),) * axes if kind == "follower" else (),
            (0.0, 0.08) if kind == "follower" else None,
            ("start_synthetic_streams",),
            "stop_simulated_targets",
            "simulated",
        )

    def prepare(self):
        self.prepared = True

    def apply(self, command):
        self.positions = command.positions
        if command.gripper_m is not None:
            self.gripper_m = command.gripper_m

    def samples(self, now_ns: int) -> list[Sample]:
        if not self.prepared:
            return []
        if self.kind == "leader":
            self.positions = tuple(
                0.1 * math.sin(now_ns / 1e9 + i) for i in range(len(self.positions))
            )
        result = []
        for spec in self.descriptor.streams:
            seq = self._seq.get(spec.name, 0)
            if spec.name == "joints":
                payload = JointState(
                    spec.channels, self.positions, (0.0,) * len(self.positions)
                )
            elif spec.name == "gripper":
                payload = JointState(spec.channels, (self.gripper_m,), (0.0,))
            elif spec.name == "rgb":
                color = bytes(
                    (seq % 256, sum(map(ord, self.descriptor.device_id)) % 256, 127)
                )
                payload = ImageFrame(8, 6, color * 48)
            elif spec.name == "depth":
                payload = DepthFrame(
                    8, 6, struct.pack("<H", 1000 + seq % 100) * 48, 0.001
                )
            else:
                payload = WrenchSample(
                    (0.0, 0.0, float(seq % 10)),
                    (0.0, 0.0, 0.0),
                    "sim_tool",
                    (0.0, 0.0, 0.0),
                    (0.0,) * 6,
                    "synthetic-v1",
                )
            header = SampleHeader(
                self.descriptor.device_id,
                spec.name,
                seq,
                self.epoch,
                now_ns,
                now_ns,
                now_ns,
                origin="estimated",
            )
            sample = Sample(header, payload)
            result.append(sample)
            self._cached[spec.name] = sample
            self._seq[spec.name] = seq + 1
        return result

    def cached(self, stream: str, now_ns: int) -> Sample:
        sample = self._cached[stream]
        spec = next(s for s in self.descriptor.streams if s.name == stream)
        stale = now_ns - sample.header.t_host_rx_mono_ns >= spec.stale_after_ns
        return Sample(sample.header.republished(now_ns, stale=stale), sample.payload)
