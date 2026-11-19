"""Exercise actual raw files and deadline races without hardware."""

import importlib
import json
import threading
import time
from dataclasses import replace

import pytest
from agilex_contract import to_wire

from agx_runtime.config import RecordConfig, StreamPolicy
from agx_sim.devices import SimDevice


class Producer:
    def __init__(self, device):
        self.device = device
        self.block_end = threading.Event()
        self.block_end.set()

    def request(self, method, **args):
        if method == "boundary_begin":
            self.device.begin_episode(
                args["episode_id"], args["start_mono_ns"], time.monotonic_ns()
            )
            return {}
        assert method == "boundary_end"
        self.block_end.wait(2)
        return {
            "boundaries": [
                to_wire(b)
                for b in self.device.end_episode(
                    args["episode_id"], args["end_mono_ns"], time.monotonic_ns()
                )
            ]
        }


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition did not become true"
        time.sleep(0.005)


def fixture(tmp_path, kinds=("camera", "camera", "wrench"), **options):
    recording = importlib.import_module("agx_runtime.recording")
    devices = [SimDevice(kind, f"dev{i}") for i, kind in enumerate(kinds)]
    for d in devices:
        d.prepare()
    policies = [
        StreamPolicy(
            d.descriptor.device_id, s.name, "record_required", ("READY", "RECORDING")
        )
        for d in devices
        for s in d.descriptor.streams
    ]
    clients = {d.descriptor.device_id: Producer(d) for d in devices}
    recorder = recording.Recorder(
        tmp_path, RecordConfig(**{"boundary_timeout_s": 0.15, **options})
    )
    episode = recorder.start([d.descriptor for d in devices], policies, clients)
    wait_for(lambda: episode.started or episode.error)
    assert not episode.error
    return recorder, episode, devices, clients


def emit(episode, devices, count=3):
    emitted = []
    for _ in range(count):
        for device in devices:
            for sample in device.samples(time.monotonic_ns()):
                episode.offer(sample)
                emitted.append(sample)
        time.sleep(0.013)
    return emitted


def test_full_sensor_episode_roundtrips_two_cameras_and_force(tmp_path):
    recorder, episode, devices, _ = fixture(tmp_path)
    emitted = emit(episode, devices)
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert episode.error is None
    raw = importlib.import_module("agx_runtime.raw")
    report = raw.inspect_episode(episode.path)
    assert report["complete"] is True
    assert len(report["streams"]) == 5
    replay = list(raw.replay_episode(episode.path))
    assert len(replay) == 15
    assert {s.header.device_id for s in replay} == {"dev0", "dev1", "dev2"}
    assert [s.payload for s in replay] == [
        s.payload
        for s in sorted(
            emitted,
            key=lambda s: (
                s.header.t_sample_ns,
                s.header.device_id,
                s.header.stream,
                s.header.seq,
            ),
        )
    ]
    assert all(
        s["produced"] == s["received"] == s["written"] == 3
        for s in report["streams"].values()
    )
    assert not episode.path.name.endswith(".partial")
    recorder.close()


def test_sampled_records_selection_times_and_counts_unselected_separately(tmp_path):
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("camera",), mode="sampled")
    emitted = emit(episode, devices, 4)
    chosen = emitted[-2:]
    target = time.monotonic_ns()
    episode.selection(target, chosen)
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert not episode.error
    raw = importlib.import_module("agx_runtime.raw")
    report = raw.inspect_episode(episode.path)
    assert all(
        s["received"] == 4
        and s["written"] == 1
        and s["intentional_skipped"] == 3
        and s["transport_lost"] == 0
        for s in report["streams"].values()
    )
    selection = json.loads((episode.path / "selections.jsonl").read_text())
    assert selection["target_mono_ns"] == target
    assert {r["seq"] for r in selection["samples"]} == {3}
    assert len(list(raw.replay_episode(episode.path))) == 2
    recorder.close()


def test_missing_tail_is_incomplete_even_without_later_sequence(tmp_path):
    recorder, episode, devices, _ = fixture(
        tmp_path, kinds=("camera",), drain_timeout_s=0.3
    )
    emit(episode, devices)
    devices[0].samples(time.monotonic_ns())  # Produced, deliberately not delivered.
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert episode.error and "missing" in episode.error
    assert not (episode.path / "complete.json").exists()
    assert episode.stats()["dev0/rgb"]["transport_lost"] == 1
    recorder.close()


def test_all_boundary_requests_share_one_deadline_and_late_replies_do_not_commit(
    tmp_path,
):
    recorder, episode, devices, clients = fixture(tmp_path)
    emit(episode, devices)
    for client in clients.values():
        client.block_end.clear()
    started = time.monotonic()
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert time.monotonic() - started < 0.4
    assert "boundary" in episode.error
    for client in clients.values():
        client.block_end.set()
    time.sleep(0.04)
    assert not (episode.path / "complete.json").exists()
    recorder.close()


def test_blocked_disk_does_not_hold_failure_lock_and_late_write_cannot_commit(
    tmp_path, monkeypatch
):
    recording = importlib.import_module("agx_runtime.recording")
    raw = importlib.import_module("agx_runtime.raw")
    real = raw.write_sample
    entered, release = threading.Event(), threading.Event()

    def blocked(*args):
        entered.set()
        release.wait(2)
        return real(*args)

    monkeypatch.setattr(raw, "write_sample", blocked)
    recorder, episode, devices, _ = fixture(
        tmp_path, kinds=("wrench",), drain_timeout_s=0.3
    )
    emit(episode, devices, 1)
    assert entered.wait(1)
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert "drain" in episode.error
    before = time.monotonic()
    episode.fail("hardware failure")
    recorder.close()
    assert time.monotonic() - before < 0.05
    release.set()
    time.sleep(0.05)
    assert not (episode.path / "complete.json").exists()
    assert recording is not None


def test_raw_checker_rejects_payload_tampering_and_partial_directory(tmp_path):
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("camera",))
    emit(episode, devices, 1)
    episode.finish(time.monotonic_ns())
    wait_for(lambda: episode.done)
    assert not episode.error
    raw = importlib.import_module("agx_runtime.raw")
    binary = next(episode.path.rglob("*.bin"))
    binary.write_bytes(b"corrupted")
    with pytest.raises(ValueError):
        raw.inspect_episode(episode.path)
    partial = tmp_path / "unfinished.partial"
    partial.mkdir()
    with pytest.raises(ValueError):
        raw.inspect_episode(partial)
    recorder.close()


def test_cached_republication_does_not_count_as_new_and_epoch_change_fails(tmp_path):
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("wrench",))
    samples = emit(episode, devices, 1)
    episode.offer(devices[0].cached("wrench", time.monotonic_ns()))
    assert episode.stats()["dev0/wrench"]["received"] == 1
    episode.offer(
        replace(samples[0], header=replace(samples[0].header, stream_epoch="restart"))
    )
    assert episode.error and "epoch" in episode.error
    recorder.close()


def test_integrity_io_has_an_independent_drain_timer(tmp_path, monkeypatch):
    from agx_runtime import raw

    original = raw.inventory
    entered, release = threading.Event(), threading.Event()

    def blocked(path):
        entered.set()
        release.wait(2)
        return original(path)

    monkeypatch.setattr(raw, "inventory", blocked)
    recorder, episode, devices, _ = fixture(
        tmp_path, kinds=("wrench",), drain_timeout_s=0.3
    )
    emit(episode, devices, 1)
    episode.finish(time.monotonic_ns())
    assert entered.wait(1)
    try:
        wait_for(lambda: episode.done, 0.6)
        assert "drain" in episode.error
    finally:
        release.set()
        recorder.close()
    time.sleep(0.05)
    assert not (episode.path / "complete.json").exists()


def test_queue_saturation_fails_without_waiting_for_writer(tmp_path, monkeypatch):
    from agx_runtime import raw

    entered, release = threading.Event(), threading.Event()
    original = raw.write_sample

    def blocked(*args):
        entered.set()
        release.wait(2)
        return original(*args)

    monkeypatch.setattr(raw, "write_sample", blocked)
    recorder, episode, devices, _ = fixture(tmp_path, kinds=("wrench",), queue_size=1)
    emit(episode, devices, 1)
    assert entered.wait(1)
    try:
        emit(episode, devices, 3)
        assert episode.done and "queue full" in episode.error
    finally:
        release.set()
        recorder.close()
    time.sleep(0.05)
    assert not (episode.path / "complete.json").exists()
