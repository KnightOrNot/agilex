"""PiPER-X HAL uses SDK feedback provenance and separates motion authority."""

import importlib
import importlib.util
from types import SimpleNamespace

import pytest
from agilex_contract import Command

from agx_hal.control import ControlGate


class Clock:
    mono = 10_000_000_000
    wall = 100_000_000_000

    def advance(self, ns):
        self.mono += ns
        self.wall += ns


class Driver:
    def __init__(self):
        self.connected = self.enabled = self.limits = False
        self.closed = False
        self.positions = (0.0,) * 6
        self.timestamp = 100.0
        self.gripper = 0.03
        self.gripper_stamp = 100.0
        self.joint_commands = []
        self.gripper_commands = []
        self.enable_calls = 0
        self.limit_calls = 0

    def connect(self):
        self.connected = True

    def close(self):
        self.closed = True

    def get_state(self):
        return SimpleNamespace(
            joint_positions_rad=self.positions,
            feedback_timestamp=self.timestamp,
            joint_feedback_timestamp=self.timestamp,
            feedback_age=0.0,
            enabled_joints=(self.enabled,) * 6,
            errors=SimpleNamespace(any=False),
            communication_ok=True,
            arm_status=0,
        )

    def get_gripper_status(self):
        if self.gripper is None:
            raise RuntimeError("gripper feedback unavailable")
        return dict(
            value=self.gripper,
            feedback_timestamp=self.gripper_stamp,
            feedback_age=0.0,
            error=False,
        )

    def maximize_joint_motion_limits(self, *, require_confirmation, before_send):
        assert require_confirmation
        before_send()
        self.limit_calls += 1
        self.limits = True
        return True

    def enable(self, *, before_send):
        before_send()
        self.enable_calls += 1
        self.enabled = True

    def require_motion_ready(self):
        state = self.get_state()
        if not all(state.enabled_joints):
            raise RuntimeError("not all joints report enabled")
        return state

    def begin_fast_response_mode(self, *, before_send):
        before_send()
        assert self.enabled

    def command_joints(self, positions, *, fast_response, before_send):
        assert self.enabled and fast_response
        before_send()
        self.joint_commands.append(tuple(positions))

    def command_gripper(self, width, force, *, before_send):
        before_send()
        self.gripper_commands.append((width, force))


def device():
    assert importlib.util.find_spec("agx_hal_piperx"), "PiPER-X HAL wrapper is missing"
    cls = importlib.import_module("agx_hal_piperx.device").PiperXDevice
    driver, clock = Driver(), Clock()
    result = cls(
        {"device_id": "arm", "channel": "can0"},
        driver_factory=lambda **kw: driver,
        clock_ns=lambda: clock.mono,
        wall_ns=lambda: clock.wall,
    )
    return result, driver, clock


def target():
    return Command(
        "operator",
        "lease",
        0,
        10_000_000_000,
        11_000_000_000,
        tuple(f"joint_{n}" for n in range(1, 7)),
        (0.01, 0.01, -0.01, 0.0, 0.0, 0.0),
        0.04,
    )


def test_discovery_and_prepare_never_enable_or_write_motion_parameters():
    hal, driver, clock = device()
    assert not driver.connected
    hal.discover()
    hal.prepare()
    assert driver.connected and not driver.enabled and not driver.limits
    assert hal.descriptor.disconnect_behavior == "unverified"
    assert hal.descriptor.prepare_effects == ()
    assert not driver.joint_commands
    hal.authorize()
    assert driver.enabled and driver.limits
    hal.apply(target())
    assert driver.joint_commands == [(0.01, 0.01, -0.01, 0.0, 0.0, 0.0)]
    assert driver.gripper_commands == [(0.04, 1.0)]
    hal.revoke("command_timeout")
    with pytest.raises(RuntimeError):
        hal.apply(target())
    hal.close()
    assert driver.closed and driver.enabled  # No implicit disable.


def test_republished_feedback_keeps_original_sample_time_and_epoch():
    hal, driver, clock = device()
    hal.discover()
    hal.prepare()
    first = hal.samples(clock.mono)
    clock.advance(30_000_000)
    second = hal.samples(clock.mono)
    assert [s.header.seq for s in second] == [0, 0]
    assert all(s.header.t_sample_ns == 10_000_000_000 for s in second)
    assert all(
        s.header.freshness == "cached" and s.header.origin == "measured" for s in second
    )
    assert all(not s.header.new_sample for s in second)
    assert first[0].header.stream_epoch == second[0].header.stream_epoch
    clock.advance(500_000_000)
    assert all(s.header.freshness == "stale" for s in hal.samples(clock.mono))
    hal.close()


def test_missing_gripper_never_masquerades_as_fresh_measurement():
    hal, driver, clock = device()
    hal.discover()
    hal.prepare()
    driver.gripper = None
    sample = hal.samples(clock.mono)[1]
    assert sample.header.origin == "unknown" and not sample.header.valid
    hal.authorize()
    hal.apply(target())
    clock.advance(10_000_000)
    sample = hal.samples(clock.mono)[1]
    assert sample.header.origin == "command_filled" and not sample.header.valid
    hal.close()


def test_missing_gripper_preserves_last_measured_origin_and_age():
    hal, driver, clock = device()
    hal.discover()
    hal.prepare()
    measured = hal.samples(clock.mono)[1]
    driver.gripper = None
    clock.advance(20_000_000)
    cached = hal.samples(clock.mono)[1]
    assert cached.header.origin == "measured" and cached.header.freshness == "cached"
    assert cached.header.t_sample_ns == measured.header.t_sample_ns
    assert cached.payload == measured.payload
    hal.close()


def test_wall_clock_step_is_rejected_instead_of_refreshing_feedback_age():
    hal, driver, clock = device()
    hal.discover()
    hal.prepare()
    hal.samples(clock.mono)
    clock.wall += 1_000_000_000
    with pytest.raises(RuntimeError, match="clock"):
        hal.samples(clock.mono)
    hal.close()


@pytest.mark.parametrize("readiness", ["enabled", "disabled", "stale"])
def test_cleanup_requires_prior_authority_and_readiness_without_reenabling(readiness):
    hal, driver, clock = device()
    gate = ControlGate(hal, clock_ns=lambda: clock.mono)
    lease = gate.acquire("operator", clock.mono)
    gate.prepare("operator", lease, clock.mono)
    with pytest.raises(ValueError, match="prior authorized session"):
        gate.authorize_cleanup("operator", lease, clock.mono)
    gate.authorize("operator", lease, clock.mono)
    gate.release("operator", lease, clock.mono)
    cleanup = gate.acquire("operator", clock.mono)
    assert cleanup != lease
    if readiness == "enabled":
        gate.authorize_cleanup("operator", cleanup, clock.mono)
        assert hal.authorized
    else:
        if readiness == "disabled":
            driver.enabled = False
        else:
            clock.advance(510_000_000)
        with pytest.raises(RuntimeError, match="not all|stale"):
            gate.authorize_cleanup("operator", cleanup, clock.mono)
        assert not hal.authorized
    assert driver.enable_calls == driver.limit_calls == 1
    assert not driver.joint_commands
    hal.close()


def test_enable_cannot_start_after_lease_deadline_without_watchdog_tick():
    hal, driver, clock = device()
    gate = ControlGate(hal, lease_timeout_ns=1, clock_ns=lambda: clock.mono)
    lease = gate.acquire("operator", clock.mono)
    gate.prepare("operator", lease, clock.mono)
    original = driver.enable

    def late_enable(**kwargs):
        clock.advance(1)
        original(**kwargs)

    driver.enable = late_enable
    with pytest.raises(RuntimeError, match="no longer live"):
        gate.authorize("operator", lease, clock.mono)
    assert gate.phase == "FAULTED"
    assert driver.enable_calls == 0
    hal.close()


@pytest.mark.parametrize("blocked", ["mode", "joints", "limits"])
def test_revocation_prevents_next_sdk_write_after_previous_call_returns(blocked):
    import threading

    hal, driver, clock = device()
    hal.prepare()
    if blocked != "limits":
        hal.authorize()
    entered, release = threading.Event(), threading.Event()
    errors = []
    if blocked == "mode":
        original = driver.begin_fast_response_mode
    elif blocked == "joints":
        original = driver.command_joints
    else:
        original = driver.maximize_joint_motion_limits

    def pause(*args, **kwargs):
        entered.set()
        assert release.wait(1)
        return original(*args, **kwargs)

    if blocked == "mode":
        driver.begin_fast_response_mode = pause
    elif blocked == "joints":
        driver.command_joints = pause
    else:
        driver.maximize_joint_motion_limits = pause

    def run():
        try:
            hal.authorize() if blocked == "limits" else hal.apply(target())
        except RuntimeError as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    assert entered.wait(1)
    hal.revoke("lease_expired")
    release.set()
    thread.join(1)
    assert errors
    if blocked == "limits":
        assert not driver.enabled
    elif blocked == "mode":
        assert driver.joint_commands == []
    else:
        assert driver.gripper_commands == []
    hal.close()
