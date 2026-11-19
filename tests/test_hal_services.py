"""Shared HAL authority stays live while a physical-like backend blocks."""

import importlib
import importlib.util
import threading
import time
from contextlib import contextmanager

import pytest
from agilex_contract import Command
from test_runtime_recording import wait_for

from agx_sim.devices import SimDevice
from agx_transport import HalClient


def implementation():
    assert importlib.util.find_spec("agx_hal"), (
        "physical and simulated HALs need a shared service"
    )
    return importlib.import_module("agx_hal.server")


class Backend(SimDevice):
    def __init__(self):
        super().__init__("follower", "arm", axes=2)
        self.entered = threading.Event()
        self.allow = threading.Event()
        self.allow.set()
        self.block = ""
        self.calls = []

    def authorize(self):
        self.calls.append("authorize")
        if self.block == "authorize":
            self.entered.set()
            assert self.allow.wait(2)

    def apply(self, command):
        self.calls.append("apply")
        if self.block == "apply":
            self.entered.set()
            assert self.allow.wait(2)
        super().apply(command)

    def close(self):
        self.calls.append("close")


@contextmanager
def service(tmp_path, **deadlines):
    server = implementation().HalServer(Backend(), tmp_path / "hal", **deadlines)
    thread = threading.Thread(target=server.run)
    thread.start()
    client = HalClient(tmp_path / "hal", timeout_ms=600)
    try:
        yield server, client
    finally:
        server.device.allow.set()
        server.stopping = True
        thread.join(2)
        client.close()
        assert not thread.is_alive()
        assert not list((tmp_path / "hal").glob("*.sock"))
        assert "close" in server.device.calls


def owner(client):
    token = client.request("acquire", session_id="operator")["lease"]
    own = dict(session_id="operator", lease=token)
    client.request("prepare", **own)
    return own


def command(own, seq=0):
    now = time.monotonic_ns()
    return Command(
        **own,
        cmd_seq=seq,
        issued_mono_ns=now,
        expires_mono_ns=now + 1_000_000_000,
        joint_names=("joint_1", "joint_2"),
        positions=(0.1, 0.1),
    )


def activate(client, own):
    client.request("authorize", **own)
    client.request("align_begin", **own)
    assert client.request("align_step", command=command(own)).status == "submitted"
    client.request("activate", **own)


def test_common_server_preserves_private_ipc_and_motion_authority(tmp_path):
    with service(tmp_path) as (server, client):
        assert client.request("hello").device_id == "arm"
        own = owner(client)
        assert not server.device.calls
        assert client.request("align_step", command=command(own)).status == "rejected"
        activate(client, own)
        assert server.device.calls == ["authorize", "apply"]
        assert client.send(command(own, 1))
        wait_for(lambda: server.device.calls.count("apply") == 2)
        client.request("release", **own)
        assert server.gate.phase == "RELEASED"


def test_blocked_authorize_cannot_delay_expiry_or_restore_old_owner(tmp_path):
    with service(tmp_path, lease_timeout_ns=70_000_000) as (server, client):
        own = owner(client)
        server.device.block = "authorize"
        server.device.allow.clear()
        errors = []

        def authorize():
            try:
                client.request("authorize", **own)
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=authorize)
        worker.start()
        assert server.device.entered.wait(1)
        wait_for(lambda: server.gate.phase == "FAULTED", 0.4)
        assert server.gate.lease is None
        server.device.allow.set()
        worker.join(1)
        assert errors
        assert server.gate.phase == "FAULTED"
        new = client.request("acquire", session_id="next")
        assert new["lease"] != own["lease"]
        assert server.gate.phase == "PREPARED"


def test_blocked_sdk_submission_does_not_block_command_watchdog(tmp_path):
    with service(tmp_path, command_timeout_ns=60_000_000) as (server, client):
        own = owner(client)
        activate(client, own)
        server.device.block = "apply"
        server.device.allow.clear()
        client.send(command(own, 1))
        assert server.device.entered.wait(1)
        wait_for(lambda: server.gate.phase == "FAULTED", 0.4)
        assert server.gate.pending is None
        assert server.gate.reason == "command_timeout"
        server.device.allow.set()
        time.sleep(0.03)
        assert server.gate.phase == "FAULTED"


def test_common_stream_publisher_keeps_cached_time_and_producer_boundaries():
    implementation()
    from agilex_contract import JointState

    from agx_hal.streams import StreamPublisher

    descriptor = SimDevice("leader", "leader", axes=2).descriptor
    stream = StreamPublisher(descriptor)
    first = stream.sample(
        "joints",
        JointState(("joint_1", "joint_2"), (0.1, 0.2), (0.0, 0.0)),
        t_sample_ns=100,
        t_host_rx_mono_ns=100,
        t_publish_mono_ns=100,
        source_key=1,
    )
    stream.begin_episode("episode", 90, 100)
    cached = stream.sample(
        "joints",
        first.payload,
        t_sample_ns=100,
        t_host_rx_mono_ns=100,
        t_publish_mono_ns=200,
        source_key=1,
    )
    assert cached.header.seq == first.header.seq
    assert cached.header.t_sample_ns == 100 and cached.header.freshness == "cached"
    assert not cached.header.new_sample
    boundaries = stream.end_episode("episode", 200, 200)
    assert boundaries[0].produced_count == 1
    assert boundaries[1].produced_count == 0


def test_driver_authorize_failure_returns_error_and_leaves_service_available(
    tmp_path, monkeypatch
):
    with service(tmp_path) as (server, client):
        own = owner(client)

        def failed():
            raise RuntimeError("backend enable refused")

        monkeypatch.setattr(server.device, "authorize", failed)
        with pytest.raises(ValueError, match="backend enable refused"):
            client.request("authorize", **own)
        assert server.gate.phase == "FAULTED" and server.gate.lease is None
        assert client.request("acquire", session_id="next")["lease"] != own["lease"]


@pytest.mark.parametrize("expired", [False, True])
def test_source_release_policy_runs_after_manual_release_or_expiry(
    tmp_path, monkeypatch, expired
):
    with service(tmp_path, lease_timeout_ns=70_000_000) as (server, client):
        own = owner(client)
        released = threading.Event()

        def release():
            server.device.prepared = False
            released.set()

        monkeypatch.setattr(server.device, "release", release, raising=False)
        if not expired:
            client.request("release", **own)
        assert released.wait(0.4)
        assert client.request("acquire", session_id="next")["lease"] != own["lease"]
        assert server.gate.phase == "DISCOVER"


def test_explicit_service_stop_revokes_before_a_blocked_sdk_call_returns(tmp_path):
    with service(tmp_path) as (server, client):
        own = owner(client)
        activate(client, own)
        server.device.block = "apply"
        server.device.allow.clear()
        client.send(command(own, 1))
        assert server.device.entered.wait(1)
        assert hasattr(server, "stop"), (
            "service shutdown must revoke authority immediately"
        )
        server.stop()
        assert server.gate.lease is None and server.gate.pending is None
        assert server.stopping
        server.device.allow.set()
