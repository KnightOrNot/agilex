"""Keep the original GELLO calibration and per-call smoothing implementation."""

import contextlib
import math
import sys
import time

import numpy as np
from agilex_contract import DeviceDescriptor, JointState, StreamSpec

from agx_hal.device import HardwareDevice


def probe_gello(settings):
    from dynamixel_sdk import PacketHandler, PortHandler

    port = PortHandler(settings["port"])
    try:
        if not port.openPort() or not port.setBaudRate(57600):
            raise RuntimeError("cannot open GELLO probe port")
        packet = PacketHandler(2.0)
        motors = []
        for identifier in [*settings["joint_ids"], settings["gripper_config"][0]]:
            model, result, error = packet.ping(port, identifier)
            if result != 0 or error != 0:
                raise RuntimeError(f"GELLO PING failed for ID {identifier}")
            motors.append({"id": identifier, "model": model})
        return {"motors": motors}
    finally:
        port.closePort()


def create_agent(settings):
    from agilex_gello_software.agents.gello_agent import (
        DynamixelRobotConfig,
        GelloAgent,
    )
    from agilex_gello_software.dynamixel.driver import DynamixelDriver

    config = DynamixelRobotConfig(
        joint_ids=settings["joint_ids"],
        joint_offsets=settings["joint_offsets"],
        joint_signs=settings["joint_signs"],
        gripper_config=tuple(settings["gripper_config"]),
    )
    start = settings.get("start_joints")
    if start is None:
        driver = DynamixelDriver(
            (*settings["joint_ids"], settings["gripper_config"][0]),
            port=settings["port"],
            use_fake_fallback=False,
        )
        try:
            start = (
                driver.get_joints() - np.asarray([*settings["joint_offsets"], 0.0])
            ) * np.asarray([*settings["joint_signs"], 1])
            start = np.concatenate((start[:-1], [0.0]))
        finally:
            driver.close()
    return GelloAgent(
        port=settings["port"], dynamixel_config=config, start_joints=np.asarray(start)
    )


class GelloDevice(HardwareDevice):
    def __init__(
        self, settings, *, agent_factory=None, probe=None, clock_ns=time.monotonic_ns
    ):
        self.settings = dict(settings)
        self._factory = agent_factory or create_agent
        self._probe = probe or probe_gello
        self._clock = clock_ns
        self._agent = None
        self._discovered = False
        self._calls = 0
        self._last_source = None
        self.width = settings.get("gripper_max_width_m", 0.1)
        hz = settings.get("hz", 50.0)
        names = tuple(f"joint_{n}" for n in range(1, len(settings["joint_ids"]) + 1))
        stale = round(settings.get("feedback_timeout_s", 1.0) * 1e9)
        descriptor = DeviceDescriptor(
            settings["device_id"],
            "gello",
            settings["port"],
            "agilex-gello-software",
            (
                StreamSpec("joints", "joint", names, "rad", hz, stale),
                StreamSpec("gripper", "joint", ("gripper",), "m", hz, stale),
            ),
            prepare_effects=("disable_leader_torque",),
            exit_policy="close_serial",
            disconnect_behavior="unverified",
        )
        super().__init__(descriptor, hz)
        self._names = names

    def discover(self):
        if not self._discovered:
            self.metadata["probe"] = self._probe(self.settings)
            self._discovered = True

    def prepare(self):
        if self.prepared:
            return
        self.discover()
        with contextlib.redirect_stdout(sys.stderr):
            self._agent = self._factory(self.settings)
        self.metadata["calibration"] = {
            key: self.settings[key]
            for key in ("joint_ids", "joint_offsets", "joint_signs", "gripper_config")
        }
        self.metadata["call_hz"] = self.hz
        self.begin_streams()
        self._calls = 0
        self._last_source = None
        self.prepared = True

    def samples(self, now_ns):
        if not self.prepared:
            return []
        raw = self._agent._robot._driver
        before = getattr(raw, "_last_successful_read", None)
        values = np.asarray(self._agent.act({}), dtype=float)
        after = getattr(raw, "_last_successful_read", None)
        stamp = before if before is not None else after
        if (
            values.shape != (len(self._names) + 1,)
            or not np.all(np.isfinite(values))
            or not 0 <= values[-1] <= 1
        ):
            raise ValueError("invalid GELLO output")
        if stamp is None or not math.isfinite(stamp):
            raise ValueError("GELLO source time is unavailable")
        sample_ns = round(stamp * 1e9)
        published = self._clock()
        if not 0 <= sample_ns <= published:
            raise ValueError("invalid GELLO source clock")
        self._calls += 1
        cached = stamp == self._last_source
        self._last_source = stamp
        fields = dict(
            t_sample_ns=sample_ns,
            t_host_rx_mono_ns=sample_ns,
            t_publish_mono_ns=published,
            source_key=self._calls,
            origin="estimated",
            new_sample=not cached,
            freshness="cached" if cached else "live",
            clock_uncertainty_ns=0
            if before is None or after is None
            else max(0, round((after - before) * 1e9)),
        )
        self.metadata["act_calls"] = self._calls
        return [
            self.publisher.sample(
                "joints",
                JointState(
                    self._names,
                    tuple(float(v) for v in values[:-1]),
                    (0.0,) * len(self._names),
                ),
                **fields,
            ),
            self.publisher.sample(
                "gripper",
                JointState(("gripper",), (float(values[-1]) * self.width,), (0.0,)),
                **fields,
            ),
        ]

    def close(self):
        agent, self._agent = self._agent, None
        self.prepared = False
        if agent is not None:
            agent.close()

    def release(self):
        self.close()
