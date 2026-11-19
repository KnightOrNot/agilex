"""GELLO wraps the original stateful agent with the same input/call sequence."""

import importlib
import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest

SETTINGS = dict(
    device_id="leader",
    port="/dev/test-gello",
    joint_ids=[1, 2],
    joint_offsets=[0.0, 0.0],
    joint_signs=[1, -1],
    gripper_config=[3, 0, 90],
    gripper_max_width_m=0.1,
    start_joints=[0.0, 0.0, 0.0],
)


def wrapper(**kwargs):
    assert importlib.util.find_spec("agx_hal_gello"), "GELLO HAL is missing"
    return importlib.import_module("agx_hal_gello.device").GelloDevice(
        SETTINGS, **kwargs
    )


def test_prepare_and_failed_prepare_close_real_agent_resources():
    called = []

    def make(settings):
        called.append("prepare")
        return SimpleNamespace(close=lambda: called.append("close"))

    hal = wrapper(
        agent_factory=make, probe=lambda settings: called.append("read-only probe")
    )
    assert not called
    hal.discover()
    assert called == ["read-only probe"]
    hal.prepare()
    assert called == ["read-only probe", "prepare"]
    assert "disable_leader_torque" in hal.descriptor.prepare_effects
    hal.close()
    hal.close()
    assert called == ["read-only probe", "prepare", "close"]


def test_wrapped_agent_preserves_complete_smoothed_output_sequence(monkeypatch):
    from agilex_gello_software.agents.gello_agent import (
        DynamixelRobotConfig,
        GelloAgent,
    )
    from agilex_gello_software.dynamixel import driver as module

    inputs = [
        np.array([0.1, 0.2, 0.3]),
        np.array([0.2, -0.1, 2.0]),
        np.array([-0.4, 0.3, -0.2]),
    ]

    class Source:
        def __init__(self, ids, **kwargs):
            assert kwargs["use_fake_fallback"] is False
            self.inputs = iter([np.zeros(3), *inputs])
            self._last_successful_read = 10.0
            self.closed = False
            self.count = 0

        def set_torque_mode(self, on):
            assert on is False

        def get_joints(self):
            self.count += 1
            self._last_successful_read += 0.02
            return next(self.inputs).copy()

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "DynamixelDriver", Source)

    def make(settings):
        return GelloAgent(
            port=settings["port"],
            dynamixel_config=DynamixelRobotConfig(
                joint_ids=settings["joint_ids"],
                joint_offsets=settings["joint_offsets"],
                joint_signs=settings["joint_signs"],
                gripper_config=tuple(settings["gripper_config"]),
            ),
            start_joints=np.array(settings["start_joints"]),
        )

    direct = make(SETTINGS)
    expected = [direct.act({}) for _ in inputs]
    hal = wrapper(
        agent_factory=make, probe=lambda settings: None, clock_ns=lambda: 11_000_000_000
    )
    hal.discover()
    hal.prepare()
    actual = []
    for _ in inputs:
        pair = hal.samples(11_000_000_000)
        actual.append(
            np.array([*pair[0].payload.positions, pair[1].payload.positions[0] / 0.1])
        )
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)
    assert hal._agent._robot._driver.count == direct._robot._driver.count == 4
    assert all(s.header.origin == "estimated" for s in pair)
    assert pair[0].header.t_sample_ns == 10_060_000_000
    assert pair[0].header.clock_uncertainty_ns == 20_000_000
    hal.close()
    direct.close()


def test_invalid_agent_output_closes_and_fails_without_fake_substitution():
    closed = []
    raw = SimpleNamespace(_last_successful_read=10.0)
    agent = SimpleNamespace(
        _robot=SimpleNamespace(_driver=raw),
        act=lambda obs: np.array([float("nan")] * 3),
        close=lambda: closed.append(True),
    )
    hal = wrapper(
        agent_factory=lambda settings: agent,
        probe=lambda settings: None,
        clock_ns=lambda: 11_000_000_000,
    )
    hal.prepare()
    with pytest.raises(ValueError):
        hal.samples(11_000_000_000)
    hal.close()
    assert closed == [True]


def test_initial_alignment_read_failure_releases_partially_constructed_driver(
    monkeypatch,
):
    from agilex_gello_software.dynamixel import driver as module

    sources = []

    class Broken:
        def __init__(self, *args, **kwargs):
            self.closed = False
            sources.append(self)

        def set_torque_mode(self, on):
            pass

        def get_joints(self):
            raise RuntimeError("initial read failed")

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "DynamixelDriver", Broken)
    hal = wrapper(probe=lambda settings: None)
    with pytest.raises(RuntimeError, match="initial read failed"):
        hal.prepare()
    assert sources and all(source.closed for source in sources)
