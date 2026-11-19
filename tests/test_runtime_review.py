"""Regressions from the P2 whole-branch review, using disk and local IPC."""

import json
import threading
import time
from dataclasses import replace

import pytest
from test_hal_ipc import running
from test_runtime_recording import emit, fixture, wait_for
from test_runtime_session import configuration, record_one, start

from agx_runtime import raw
from agx_runtime.config import DeviceConfig, RuntimeConfig, StreamPolicy
from agx_sim.control import ControlGate
from agx_sim.devices import SimDevice


def test_failure_at_final_publication_cannot_be_overwritten(tmp_path, monkeypatch):
    from agx_runtime import recording

    recorder, episode, devices, _ = fixture(tmp_path, kinds=("wrench",))
    real_rename, real_clock = recording.os.rename, time.monotonic
    published = threading.Event()

    def rename(source, destination):
        real_rename(source, destination)
        if not str(destination).endswith(".partial"):
            published.set()

    def clock():
        if published.is_set() and threading.current_thread() is episode._coordinator:
            published.clear()
            episode.fail("HAL fault during final publication")
        return real_clock()

    monkeypatch.setattr(recording.os, "rename", rename)
    monkeypatch.setattr(recording.time, "monotonic", clock)
    emit(episode, devices, 1)
    episode.finish(time.monotonic_ns())
    episode._coordinator.join(2)
    assert not episode._coordinator.is_alive()
    assert episode.phase == "FAILED"
    assert episode.path.name.endswith(".partial")
    assert not (episode.path / "complete.json").exists()
    recorder.close()


def test_optional_camera_loss_does_not_stop_sampled_session(tmp_path):
    config = configuration(tmp_path, teleop=True, mode="sampled")
    config = replace(
        config,
        streams=tuple(
            replace(p, role="optional") if p.device_id == "front" else p
            for p in config.streams
        ),
    )
    session = start(config)
    try:
        session.confirm(True)
        wait_for(lambda: session.phase == "FOLLOWING")
        session.record()
        wait_for(lambda: session.episode.started or session.episode.done)
        assert session.episode.started, session.status()
        time.sleep(0.12)
        session.supervisor.processes["front"].kill()
        time.sleep(0.22)
        assert session.status()["error"] is None
        assert session.phase == "RECORDING"
        session.save()
        wait_for(lambda: session.episode.done)
        assert session.episode.error is None
        assert raw.inspect_episode(session.episode.path)["complete"]
        assert session.episode.warnings
    finally:
        session.stop()
        assert session.wait(3)


def test_optional_epoch_change_is_quarantined_without_mixing(tmp_path):
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("camera",))
    episode.policies = {
        key: replace(p, role="optional") for key, p in episode.policies.items()
    }
    samples = emit(episode, devices, 1)
    episode.offer(
        replace(samples[0], header=replace(samples[0].header, stream_epoch="restart"))
    )
    assert episode.error is None
    assert episode.warnings
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert episode.error is None
    assert all(
        s.header.stream_epoch == devices[0].epoch
        for s in raw.replay_episode(episode.path)
    )
    recorder.close()


@pytest.mark.parametrize("expired", [False, True])
def test_revocation_closes_producer_episode_and_keeps_old_counts(expired):
    device = SimDevice("camera", "front")
    gate = ControlGate(device, lease_timeout_ns=100)
    lease = gate.acquire("old", 10)
    gate.prepare("old", lease, 10)
    device.begin_episode("old-episode", 10, 10)
    device.samples(20)
    if expired:
        gate.tick(110)
        end = 110
    else:
        gate.release("old", lease, 30)
        end = 30
    new_lease = gate.acquire("new", 120)
    device.begin_episode("new-episode", 120, 120)
    with pytest.raises(ValueError):
        gate._owner("old", lease, 120)
    assert new_lease != lease
    assert all(
        b.produced_count == 1 for b in device.end_episode("old-episode", end, 130)
    )
    assert all(
        b.produced_count == 0 for b in device.end_episode("new-episode", 130, 130)
    )


def test_external_hal_can_record_after_unsaved_session_stops(tmp_path):
    with running(tmp_path, kind="camera", name="cam") as (client, _, directory):
        config = RuntimeConfig(
            devices=(DeviceConfig("cam", "camera", endpoint=str(directory)),),
            streams=tuple(
                StreamPolicy("cam", stream, "record_required", ("READY", "RECORDING"))
                for stream in ("rgb", "depth")
            ),
            data_root=str(tmp_path / "raw"),
            lock_path=str(tmp_path / "lock"),
        )
        first = start(config)
        first.record()
        wait_for(lambda: first.episode.started)
        first.stop()
        assert first.wait(3)
        second = start(config)
        try:
            assert raw.inspect_episode(record_one(second))["complete"]
            assert client.request("hello").device_id == "cam"
        finally:
            second.stop()
            assert second.wait(3)


def test_sampled_without_a_selection_is_not_complete(tmp_path):
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("camera",), mode="sampled")
    emit(episode, devices, 1)
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert episode.phase == "FAILED"
    assert "selection" in episode.error
    assert not (episode.path / "complete.json").exists()
    recorder.close()


@pytest.mark.parametrize(
    "damage",
    [
        "missing-grid",
        "empty-grid",
        "missing-required",
        "duplicate-ref",
        "skew",
        "missing-devices",
        "missing-policy",
        "missing-stats",
        "wrong-channels",
    ],
)
def test_checker_rejects_semantic_damage_even_with_matching_hashes(tmp_path, damage):
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("camera",), mode="sampled")
    samples = emit(episode, devices, 2)
    episode.selection(time.monotonic_ns(), samples[-2:])
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert not episode.error
    path = episode.path
    manifest = json.loads((path / "manifest.json").read_text())
    grid = path / "selections.jsonl"
    item = json.loads(grid.read_text())
    if damage == "missing-grid":
        grid.unlink()
    elif damage == "empty-grid":
        grid.write_text("")
    elif damage == "missing-required":
        item["samples"].pop()
    elif damage == "duplicate-ref":
        item["samples"].append(item["samples"][0])
    elif damage == "skew":
        manifest["record"]["max_skew_ms"] = 0.000001
    elif damage == "missing-devices":
        manifest["devices"] = []
    elif damage == "missing-policy":
        manifest["policies"].pop()
    elif damage == "missing-stats":
        manifest["streams"].pop("dev0/rgb")
    elif damage == "wrong-channels":
        manifest["devices"][0]["streams"][0]["kind"] = "joint"
        manifest["devices"][0]["streams"][0]["channels"] = ["bad"]
    if damage not in ("missing-grid", "empty-grid"):
        grid.write_text(json.dumps(item) + "\n")
    (path / "manifest.json").write_text(json.dumps(manifest))
    complete = json.loads((path / "complete.json").read_text())
    complete["files"] = raw.inventory(path)
    (path / "complete.json").write_text(json.dumps(complete))
    with pytest.raises(ValueError):
        raw.inspect_episode(path)
    recorder.close()


def test_stop_during_actor_turn_does_not_send_another_target(tmp_path, monkeypatch):
    session = start(configuration(tmp_path, teleop=True))
    sent_after_stop = []
    try:
        session.confirm(True)
        wait_for(lambda: session.phase == "FOLLOWING")
        original_send = session.clients["arm"].send
        original_requests = session._requests_once

        def send(command):
            if session._stop.is_set():
                sent_after_stop.append(command)
            return original_send(command)

        def requests():
            session.stop()
            time.sleep(0.025)
            return original_requests()

        monkeypatch.setattr(session.clients["arm"], "send", send)
        # Force a due tick in the same actor turn as the stop request.
        monkeypatch.setattr(session, "_requests_once", requests)
        assert session.wait(3)
        assert not sent_after_stop
    finally:
        session.stop()
        session.wait(3)


def test_late_optional_samples_cannot_enter_after_writer_finalization(
    tmp_path, monkeypatch
):
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("camera", "camera"))
    episode.policies = {
        key: replace(p, role="optional") if p.device_id == "dev1" else p
        for key, p in episode.policies.items()
    }
    emit(episode, devices[:1], 1)
    late = devices[1].samples(time.monotonic_ns())
    entered, release = threading.Event(), threading.Event()
    original = raw.atomic_json

    def blocked(path, value):
        if path.name == "manifest.json":
            entered.set()
            release.wait(2)
        return original(path, value)

    monkeypatch.setattr(raw, "atomic_json", blocked)
    episode.finish(time.monotonic_ns())
    try:
        assert entered.wait(1)
        for sample in late:
            episode.offer(sample)
    finally:
        release.set()
    wait_for(lambda: episode.done)
    assert episode.error is None
    assert raw.inspect_episode(episode.path)["complete"]
    assert all(
        stats["written"] == 0
        for key, stats in episode.stats().items()
        if key.startswith("dev1/")
    )
    recorder.close()


def test_management_rpc_does_not_open_command_or_sample_channels(tmp_path, monkeypatch):
    import zmq

    from agx_runtime.supervisor import Supervisor

    with running(tmp_path, kind="camera", name="cam") as (_, _, directory):
        supervisor = Supervisor(RuntimeConfig(), "test-session")
        supervisor.directories["cam"] = directory
        socket_types = []
        original = zmq.Context.socket

        def socket(context, kind, *args, **kwargs):
            socket_types.append(kind)
            return original(context, kind, *args, **kwargs)

        monkeypatch.setattr(zmq.Context, "socket", socket)
        assert supervisor.rpc("cam", "status")["phase"] == "DISCOVER"
        assert socket_types == [zmq.REQ]
