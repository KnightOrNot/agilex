"""Configuration cannot turn off control dependencies or refresh cached feedback."""

import importlib
from dataclasses import replace

import pytest

from agx_sim.devices import SimDevice


def modules():
    return importlib.import_module("agx_runtime.config"), importlib.import_module(
        "agx_runtime.safety"
    )


@pytest.mark.parametrize("value", [0, -1, True, float("nan"), float("inf"), "1"])
@pytest.mark.parametrize("key", ["boundary_timeout_s", "drain_timeout_s"])
def test_record_deadlines_reject_unbounded_or_mistyped_values(key, value):
    config, _ = modules()
    with pytest.raises(ValueError):
        config.load_config(overrides={"record": {key: value}})


def test_required_control_phases_and_unknown_fields_rejected():
    config, _ = modules()
    with pytest.raises(ValueError):
        config.load_config(overrides={"record": {"drain_timout_s": 1}})
    with pytest.raises(ValueError):
        config.StreamPolicy("leader", "joints", "control_required", ("RECORDING",))


def test_legacy_recording_aliases_are_migrated_without_overriding_explicit_record(
    tmp_path,
):
    config, _ = modules()
    path = tmp_path / "legacy.toml"
    path.write_text(
        "[recording]\ndataset_fps = 20\nqueue_size = 100\n[record]\ndataset_fps = 25\n"
    )
    with pytest.warns(UserWarning, match="recording"):
        result = config.load_config(path)
    assert result.record.dataset_fps == 25
    assert result.record.queue_size == 100


def test_cached_value_and_optional_staleness_have_distinct_outcomes():
    config, safety = modules()
    device = SimDevice("camera", "cam")
    device.prepare()
    sample = device.samples(1_000_000_000)[0]
    required = config.StreamPolicy(
        "cam", "rgb", "record_required", ("READY", "FOLLOWING", "RECORDING")
    )
    monitor = safety.StreamMonitor([device.descriptor], [required])
    monitor.update(sample)
    monitor.update(device.cached("rgb", 1_090_000_000))
    with pytest.raises(safety.SafetyFault, match="stale"):
        monitor.check("FOLLOWING", 1_110_000_000)
    optional = replace(required, role="optional")
    monitor = safety.StreamMonitor([device.descriptor], [optional])
    monitor.update(sample)
    assert "stale" in monitor.check("FOLLOWING", 1_110_000_000)[0]


def test_stream_restart_invalid_samples_and_future_timestamps_refuse_control():
    config, safety = modules()
    device = SimDevice("follower", "arm", axes=4)
    device.prepare()
    sample = device.samples(1_000_000_000)[0]
    policy = config.StreamPolicy(
        "arm",
        "joints",
        "control_required",
        ("READY", "ALIGN", "FOLLOWING", "RECORDING"),
    )
    monitor = safety.StreamMonitor([device.descriptor], [policy])
    monitor.update(sample)
    with pytest.raises(safety.SafetyFault, match="epoch"):
        monitor.update(
            replace(sample, header=replace(sample.header, stream_epoch="new"))
        )
    with pytest.raises(safety.SafetyFault):
        safety.checked_positions(
            device.descriptor,
            replace(sample, header=replace(sample.header, valid=False)),
            (0.0,) * 4,
            1_000_000_010,
        )
    with pytest.raises(safety.SafetyFault):
        safety.checked_positions(device.descriptor, sample, (0.0,) * 4, 2_000_000_000)
    with pytest.raises(safety.SafetyFault):
        safety.checked_positions(device.descriptor, sample, (0.0,) * 4, 999_000_000)


def test_mapping_uses_names_scales_limits_and_independent_gripper():
    _, safety = modules()
    leader = SimDevice("leader", "leader", axes=4)
    follower = SimDevice("follower", "arm", axes=4)
    mapping = safety.JointMapping(
        leader.descriptor,
        follower.descriptor,
        {
            "joint_1": ("joint_2", -1.0),
            "joint_2": ("joint_1", 2.0),
            "joint_3": ("joint_3", 1.0),
            "joint_4": ("joint_4", 1.0),
        },
    )
    leader.prepare()
    sample = leader.samples(1_000_000_000)[0]
    sample = replace(
        sample, payload=replace(sample.payload, positions=(0.1, 0.2, 0.3, 0.4))
    )
    assert mapping.target(sample) == (-0.2, 0.2, 0.3, 0.4)
    with pytest.raises(ValueError):
        safety.JointMapping(
            leader.descriptor, SimDevice("follower", "other", axes=6).descriptor
        )
    follower.prepare()
    feedback = follower.samples(1_000_000_000)[0]
    assert safety.checked_positions(
        follower.descriptor, feedback, (0.4, 0.2, 0.0, 0.0), 1_000_000_001, max_step=0.1
    ) == pytest.approx((0.1, 0.05, 0.0, 0.0), abs=1e-15, rel=0)


def test_unknown_stream_or_unmonitored_control_dependency_is_not_silently_accepted():
    config, safety = modules()
    device = SimDevice("camera", "cam")
    policy = config.StreamPolicy(
        "cam", "missing", "record_required", ("READY", "RECORDING")
    )
    with pytest.raises(ValueError, match="stream"):
        safety.StreamMonitor([device.descriptor], [policy])


def test_optional_unknown_time_warns_without_breaking_quality_monitor():
    config, safety = modules()
    camera = SimDevice("camera", "cam")
    camera.prepare()
    sample = camera.samples(1_000_000_000)[0]
    sample = replace(
        sample, header=replace(sample.header, t_sample_ns=None, valid=False)
    )
    policy = config.StreamPolicy("cam", "rgb", "optional", ("READY",))
    monitor = safety.StreamMonitor([camera.descriptor], [policy])
    monitor.update(sample)
    assert monitor.quality("READY", 1_000_000_001, 50)


def test_republished_invalid_feedback_cannot_keep_previous_valid_state():
    config, safety = modules()
    device = SimDevice("follower", "arm")
    device.prepare()
    sample = device.samples(1_000_000_000)[0]
    policy = config.StreamPolicy(
        "arm",
        "joints",
        "control_required",
        ("READY", "ALIGN", "FOLLOWING", "RECORDING"),
    )
    monitor = safety.StreamMonitor([device.descriptor], [policy])
    monitor.update(sample)
    monitor.update(
        replace(sample, header=replace(sample.header, valid=False, freshness="cached"))
    )
    with pytest.raises(safety.SafetyFault):
        monitor.check("FOLLOWING", 1_000_000_001)


def test_return_to_zero_rejects_command_filled_and_out_of_limit_feedback():
    _, safety = modules()
    device = SimDevice("follower", "arm", axes=4)
    device.prepare()
    sample = device.samples(1_000_000_000)[0]
    for invalid in (
        replace(sample, header=replace(sample.header, origin="command_filled")),
        replace(sample, payload=replace(sample.payload, positions=(100.0,) * 4)),
    ):
        with pytest.raises(safety.SafetyFault):
            safety.checked_positions(
                device.descriptor, invalid, (0.0,) * 4, 1_000_000_001, max_step=0.02
            )


def test_installed_package_defaults_work_without_checkout_config(tmp_path, monkeypatch):
    config, _ = modules()
    expected = config.load_config()
    monkeypatch.setattr(config, "DEFAULT_CONFIG", tmp_path / "missing.toml")
    assert config.load_config() == expected
