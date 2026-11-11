"""Real child processes and owner-private sockets; no hardware libraries."""

import importlib
import os
import stat
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager

import pytest
import zmq
from agilex_contract import (
    Command,
    DepthFrame,
    ImageFrame,
    Sample,
    WrenchSample,
    to_wire,
)

from agx_sim.transport import pack


@contextmanager
def running(tmp_path, kind="follower", name="arm"):
    transport = importlib.import_module("agx_sim.transport")
    directory = tmp_path / name
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agx_sim",
            "serve",
            "--kind",
            kind,
            "--device-id",
            name,
            "--endpoint-dir",
            str(directory),
            "--command-timeout-s",
            "0.25",
            "--lease-timeout-s",
            "3",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    client = transport.HalClient(directory, timeout_ms=200)
    try:
        deadline = time.monotonic() + 5
        while True:
            if process.poll() is not None:
                pytest.fail(process.communicate()[1])
            try:
                descriptor = client.request("hello")
                break
            except TimeoutError:
                if time.monotonic() >= deadline:
                    pytest.fail("HAL did not become ready")
        yield client, descriptor, directory
    finally:
        client.close()
        process.terminate()
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()


def prepare(client):
    lease = client.request("acquire", session_id="operator")["lease"]
    owner = {"session_id": "operator", "lease": lease}
    client.request("prepare", **owner)
    return owner


def activate(client, descriptor):
    owner = prepare(client)
    # Seeing a sample confirms the lossy PUB subscription is ready for acks.
    assert isinstance(client.receive(1.0), Sample)
    client.request("authorize", **owner)
    client.request("align_begin", **owner)
    now = time.monotonic_ns()
    cmd = Command(
        **owner,
        cmd_seq=0,
        issued_mono_ns=now,
        expires_mono_ns=now + 1_000_000_000,
        joint_names=descriptor.joint_names,
        positions=(0.0,) * len(descriptor.joint_names),
    )
    assert client.request("align_step", command=cmd).status == "submitted"
    client.request("activate", **owner)
    return owner


def test_remote_watchdog_revokes_without_new_messages_and_requires_reauthorization(
    tmp_path,
):
    with running(tmp_path) as (client, descriptor, directory):
        assert client.request("status")["phase"] == "DISCOVER"
        assert client.receive(0.05) is None
        for path in directory.iterdir():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        owner = activate(client, descriptor)
        time.sleep(0.4)
        assert client.request("status")["reason"] == "command_timeout"
        renewed = client.request("acquire", session_id="operator")
        assert renewed["lease"] != owner["lease"]
        assert client.request("status")["phase"] == "PREPARED"
        with pytest.raises(ValueError):
            client.request("activate", session_id="operator", lease=renewed["lease"])
    assert not any(directory.glob("*.sock"))


def test_command_channel_and_bad_message_do_not_break_management(tmp_path):
    with running(tmp_path) as (client, descriptor, _):
        # PUSH connects asynchronously and send() deliberately never blocks.
        assert client.commands.poll(1000, zmq.POLLOUT)
        owner = activate(client, descriptor)
        now = time.monotonic_ns()
        target = Command(
            **owner,
            cmd_seq=1,
            issued_mono_ns=now,
            expires_mono_ns=now + 1_000_000_000,
            joint_names=descriptor.joint_names,
            positions=(0.2,) * len(descriptor.joint_names),
        )
        assert client.send(target)
        deadline = time.monotonic() + 1
        statuses = []
        while time.monotonic() < deadline:
            event = client.receive(0.1)
            if event and not isinstance(event, Sample) and event.cmd_seq == 1:
                statuses.append(event.status)
                if event.status == "submitted":
                    break
        assert "submitted" in statuses
        assert client.request("status")["positions"] == [0.2] * len(
            descriptor.joint_names
        )
        client.commands.send(b"\xc1", flags=zmq.DONTWAIT)
        with pytest.raises(ValueError):
            client.request("not_a_method")
        assert client.request("hello").device_id == "arm"
        with pytest.raises(ValueError):
            client.request("acquire", session_id="second-owner")


def test_nested_bad_commands_are_rejected_on_both_channels(tmp_path):
    with running(tmp_path) as (client, _, _):
        assert client.commands.poll(1000, zmq.POLLOUT)
        wire = to_wire(Command("s", "l", 0, 1, 2, ("a",), (0.0,)))
        nested = 0
        for _ in range(500):
            nested = [nested]
        wire["positions"] = nested
        client.commands.send(pack(wire), flags=zmq.DONTWAIT)
        with pytest.raises(ValueError, match="nesting"):
            client.request("align_step", command=wire)
        deadline = time.monotonic() + 1
        while client.request("status")["protocol_errors"] < 2:
            assert time.monotonic() < deadline
        assert client.request("hello").device_id == "arm"


def test_two_cameras_and_wrench_roundtrip_and_restart_epoch(tmp_path):
    with ExitStack() as stack:
        clients = {}
        for kind, name in (
            ("camera", "front"),
            ("camera", "side"),
            ("wrench", "force"),
        ):
            client, descriptor, _ = stack.enter_context(running(tmp_path, kind, name))
            assert descriptor.device_id == name
            prepare(client)
            clients[name] = client
        observed = {}
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and len(observed) < 5:
            for client in clients.values():
                sample = client.receive(0.05)
                if isinstance(sample, Sample):
                    observed[(sample.header.device_id, sample.header.stream)] = sample
        assert set(observed) == {
            ("front", "rgb"),
            ("front", "depth"),
            ("side", "rgb"),
            ("side", "depth"),
            ("force", "wrench"),
        }
        assert isinstance(observed["front", "rgb"].payload, ImageFrame)
        assert isinstance(observed["side", "depth"].payload, DepthFrame)
        assert isinstance(observed["force", "wrench"].payload, WrenchSample)
        for sample in observed.values():
            assert sample.header.t_sample_ns <= sample.t_runtime_rx_mono_ns
        epoch = observed["front", "rgb"].header.stream_epoch
    with running(tmp_path, "camera", "front") as (client, _, _):
        assert client.request("status")["stream_epoch"] != epoch


def test_world_accessible_endpoint_directory_is_rejected(tmp_path):
    server = importlib.import_module("agx_sim.server")
    device = importlib.import_module("agx_sim.devices").SimDevice("camera", "cam")
    os.chmod(tmp_path, 0o755)
    with pytest.raises(ValueError, match="private"):
        server.HalServer(device, tmp_path)
