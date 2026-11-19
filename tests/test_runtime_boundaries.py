"""Producer counts, including samples the subscriber never saw."""

import importlib
import os

import pytest
from test_hal_ipc import prepare, running

from agx_sim.devices import SimDevice


def tracker():
    device = SimDevice("camera", "front")
    device.prepare()
    assert hasattr(device, "begin_episode"), "HAL needs episode-scoped counters"
    return device


def test_boundary_excludes_preroll_and_postroll_and_retains_tail_counts():
    device = tracker()
    device.samples(100)
    device.samples(200)
    device.begin_episode("episode", 150, 210)
    device.samples(300)
    device.samples(400)
    boundaries = device.end_episode("episode", 350, 450)
    assert [
        (b.stream, b.first_seq, b.last_seq, b.produced_count) for b in boundaries
    ] == [("rgb", 1, 2, 2), ("depth", 1, 2, 2)]
    assert all(b.stream_epoch == device.epoch for b in boundaries)
    device.samples(500)
    assert device.end_episode("episode", 350, 600) == boundaries
    with pytest.raises(ValueError):
        device.end_episode("episode", 400, 600)


def test_empty_boundary_and_overlapping_episode_rejected():
    device = tracker()
    device.begin_episode("one", 100, 100)
    with pytest.raises(ValueError):
        device.begin_episode("two", 100, 110)
    result = device.end_episode("one", 150, 150)
    assert all(
        b.first_seq is None and b.last_seq is None and b.produced_count == 0
        for b in result
    )
    device.begin_episode("two", 200, 200)
    device.samples(210)
    assert all(b.produced_count == 1 for b in device.end_episode("two", 220, 220))


def test_unverifiable_old_and_future_boundaries_are_rejected():
    device = tracker()
    for now in range(9000):
        device.samples(now)
    with pytest.raises(ValueError):
        device.begin_episode("old", 1, 9000)
    with pytest.raises(ValueError):
        device.begin_episode("future", 10000, 9000)
    device.begin_episode("ok", 8990, 9000)
    with pytest.raises(ValueError):
        device.end_episode("ok", 10000, 9000)
    with pytest.raises(ValueError):
        device.end_episode("wrong-id", 9000, 9000)


def test_boundary_rpc_requires_owner_and_does_not_revoke_control(tmp_path):
    import time

    with running(tmp_path, "camera", "front") as (client, _, _):
        owner = prepare(client)
        start = time.monotonic_ns()
        client.request("boundary_begin", **owner, episode_id="one", start_mono_ns=start)
        assert client.receive(1) is not None
        end = time.monotonic_ns()
        with pytest.raises(ValueError):
            client.request(
                "boundary_end",
                session_id="intruder",
                lease="no",
                episode_id="one",
                end_mono_ns=end,
            )
        result = client.request(
            "boundary_end", **owner, episode_id="one", end_mono_ns=end
        )
        assert len(result["boundaries"]) == 2
        assert client.request("status")["phase"] == "PREPARED"


def test_shared_client_refuses_public_or_symlinked_endpoint(tmp_path):
    transport = importlib.import_module("agx_transport")
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    os.chmod(public, 0o755)
    with pytest.raises((ValueError, PermissionError)):
        transport.HalClient(public)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    link = tmp_path / "alias"
    link.symlink_to(private, target_is_directory=True)
    with pytest.raises((ValueError, PermissionError)):
        transport.HalClient(link)
