"""Control leases and stale targets must fail closed without real hardware."""

import importlib

import pytest
from agilex_contract import Command


@pytest.fixture
def gate():
    devices = importlib.import_module("agx_sim.devices")
    control = importlib.import_module("agx_sim.control")
    device = devices.SimDevice("follower", "arm", axes=2)
    return control.ControlGate(
        device,
        command_timeout_ns=100,
        lease_timeout_ns=1000,
        align_step_timeout_ns=50,
        align_total_timeout_ns=200,
    )


def command(gate, lease, seq=0, now=10, expiry=90, positions=(0.1, 0.2)):
    return Command(
        "operator",
        lease,
        seq,
        now,
        expiry,
        gate.device.descriptor.joint_names,
        positions,
    )


def active(gate, now=0):
    lease = gate.acquire("operator", now)
    gate.prepare("operator", lease, now)
    gate.authorize("operator", lease, now)
    gate.begin_alignment("operator", lease, now)
    assert (
        gate.alignment_step(command(gate, lease, now=now, expiry=now + 100), now).status
        == "submitted"
    )
    gate.activate("operator", lease, now)
    return lease


def test_motion_requires_prepare_authorize_and_alignment(gate):
    lease = gate.acquire("operator", 0)
    assert gate.accept(command(gate, lease), 10).status == "rejected"
    with pytest.raises(ValueError):
        gate.authorize("operator", lease, 0)
    gate.prepare("operator", lease, 0)
    with pytest.raises(ValueError):
        gate.activate("operator", lease, 0)
    gate.authorize("operator", lease, 0)
    gate.begin_alignment("operator", lease, 0)
    with pytest.raises(ValueError):
        gate.activate("operator", lease, 0)
    assert gate.device.positions == (0.0, 0.0)


def test_latest_target_replaces_pending_and_expiry_checked_before_submission(gate):
    lease = active(gate)
    assert gate.accept(command(gate, lease, seq=1), 10).status == "accepted"
    assert (
        gate.accept(command(gate, lease, seq=2, positions=(0.3, 0.4)), 11).status
        == "accepted"
    )
    assert gate.submit_pending(12).status == "submitted"
    assert gate.device.positions == (0.3, 0.4)
    assert gate.replaced_count == 1
    assert (
        gate.accept(command(gate, lease, seq=3, now=13, expiry=15), 13).status
        == "accepted"
    )
    assert gate.submit_pending(15).status == "rejected"
    assert gate.device.positions == (0.3, 0.4)


def test_rejections_queries_and_lease_renewal_do_not_refresh_command_watchdog(gate):
    lease = active(gate)
    assert gate.accept(command(gate, lease, seq=0), 10).status == "rejected"
    assert gate.accept(command(gate, "old", seq=1), 20).status == "rejected"
    assert gate.accept(command(gate, lease, seq=2, now=80), 30).status == "rejected"
    assert (
        gate.accept(command(gate, lease, seq=3, positions=(100.0, 0.0)), 40).status
        == "rejected"
    )
    gate.renew("operator", lease, 50)
    gate.status(99)
    gate.tick(100)
    assert gate.phase == "FAULTED"
    assert gate.lease is None
    assert gate.pending is None
    assert gate.reason == "command_timeout"


def test_expired_lease_revokes_pending_target_and_reacquisition_needs_alignment(gate):
    old = active(gate)
    with pytest.raises(ValueError):
        gate.acquire("other", 1)
    assert gate.accept(command(gate, old, seq=1), 10).status == "accepted"
    gate.tick(1000)
    assert gate.pending is None
    new = gate.acquire("operator", 1000)
    assert new != old
    assert gate.phase == "PREPARED"
    assert (
        gate.accept(command(gate, new, seq=2, now=1001, expiry=1100), 1001).status
        == "rejected"
    )
    gate.authorize("operator", new, 1001)
    gate.begin_alignment("operator", new, 1001)
    assert (
        gate.alignment_step(command(gate, new, now=1001, expiry=1100), 1001).status
        == "submitted"
    )
    gate.activate("operator", new, 1001)
    assert (
        gate.accept(command(gate, old, seq=5, now=1002, expiry=1100), 1002).status
        == "rejected"
    )


def test_alignment_has_step_gap_and_total_deadlines(gate):
    lease = gate.acquire("operator", 0)
    gate.prepare("operator", lease, 0)
    gate.authorize("operator", lease, 0)
    gate.begin_alignment("operator", lease, 0)
    gate.tick(50)
    assert gate.reason == "alignment_step_timeout"
    lease = gate.acquire("operator", 100)
    gate.authorize("operator", lease, 100)
    gate.begin_alignment("operator", lease, 100)
    for seq, now in enumerate((100, 140, 180, 220, 260, 299)):
        assert (
            gate.alignment_step(
                command(gate, lease, seq=seq, now=now, expiry=now + 100), now
            ).status
            == "submitted"
        )
    gate.tick(300)
    assert gate.reason == "alignment_total_timeout"


def test_release_discards_pending_and_queries_cannot_reactivate(gate):
    lease = active(gate)
    gate.accept(command(gate, lease, seq=1), 10)
    gate.release("operator", lease, 11)
    assert gate.submit_pending(12) is None
    assert gate.status(12)["phase"] == "RELEASED"


def test_simulated_extended_devices_have_separate_stream_identity_and_provenance():
    SimDevice = importlib.import_module("agx_sim.devices").SimDevice
    devices = [
        SimDevice(kind, name)
        for kind, name in (
            ("leader", "leader"),
            ("camera", "front"),
            ("camera", "side"),
            ("wrench", "force"),
        )
    ]
    for device in devices:
        assert device.samples(10) == []
        device.prepare()
    samples = [s for device in devices for s in device.samples(100)]
    assert {s.header.device_id for s in samples} == {"leader", "front", "side", "force"}
    assert all(s.header.origin == "estimated" for s in samples)
    assert {s.header.stream for s in samples if s.header.device_id == "front"} == {
        "rgb",
        "depth",
    }
    first = devices[1].cached("rgb", 200)
    assert (first.header.t_sample_ns, first.header.new_sample) == (100, False)
    assert SimDevice("camera", "front").epoch != devices[1].epoch
