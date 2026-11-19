"""Public runtime sessions exercise real simulated HAL subprocesses and IPC."""

import importlib
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

import pytest
from test_hal_ipc import running
from test_runtime_recording import wait_for

from agx_runtime.config import DeviceConfig, RecordConfig, RuntimeConfig, StreamPolicy
from agx_runtime.raw import inspect_episode, replay_episode


def configuration(tmp_path, teleop=False, mode="full", extended=False):
    kinds = [("front", "camera")]
    if teleop:
        kinds = [("leader", "leader"), ("arm", "follower"), *kinds]
    if extended or not teleop:
        kinds += [("side", "camera"), ("force", "wrench")]
    devices = tuple(DeviceConfig(name, kind, axes=4) for name, kind in kinds)
    policies = []
    for name, kind in kinds:
        streams = {"camera": ("rgb", "depth"), "wrench": ("wrench",)}.get(
            kind, ("joints", "gripper")
        )
        for stream in streams:
            policies.append(
                StreamPolicy(
                    name,
                    stream,
                    "control_required"
                    if kind in ("leader", "follower")
                    else "record_required",
                    ("READY", "ALIGN", "FOLLOWING", "RECORDING"),
                )
            )
    return RuntimeConfig(
        devices=devices,
        streams=tuple(policies),
        leader="leader" if teleop else "",
        follower="arm" if teleop else "",
        record=RecordConfig(mode=mode, boundary_timeout_s=0.3),
        data_root=str(tmp_path / "raw"),
        lock_path=str(tmp_path / "session.lock"),
    )


def start(config):
    session = importlib.import_module("agx_runtime.session").Session(config)
    session.prepare()
    wait_for(lambda: session.status()["phase"] in ("READY", "CONFIRM", "FAILED"), 8)
    assert session.status()["error"] is None, session.status()
    return session


def record_one(session):
    session.record()
    wait_for(lambda: session.episode is not None and session.episode.started)
    time.sleep(0.22)
    session.save()
    wait_for(lambda: session.episode.done, 7)
    assert session.episode.error is None, session.status()
    return session.episode.path


def test_sensor_only_session_two_cameras_and_force_can_save_twice(tmp_path):
    session = start(configuration(tmp_path))
    try:
        first = record_one(session)
        wait_for(lambda: session.status()["phase"] == "READY")
        second = record_one(session)
        assert first != second
        for path in (first, second):
            report = inspect_episode(path)
            assert len(report["streams"]) == 5
            assert (
                report["streams"]["force/wrench"]["written"]
                > report["streams"]["front/rgb"]["written"]
            )
            assert len(list(replay_episode(path))) == report["samples"]
    finally:
        session.stop()
        assert session.wait(3)
    assert all(p.poll() is not None for p in session.supervisor.processes.values())


@pytest.mark.parametrize("mode", ["full", "sampled"])
def test_four_axis_following_requires_confirmation_and_records_real_commands(
    tmp_path, mode
):
    session = start(configuration(tmp_path, teleop=True, mode=mode))
    try:
        assert session.status()["phase"] == "CONFIRM"
        assert session.status()["target"]["joint_names"] == [
            f"joint_{i}" for i in range(1, 5)
        ]
        assert session.supervisor.rpc("arm", "status")["phase"] == "PREPARED"
        with pytest.raises(ValueError):
            session.confirm(False)
        with pytest.raises(ValueError):
            session.record()
        session.confirm(True)
        wait_for(lambda: session.status()["phase"] in ("FOLLOWING", "FAILED"), 3)
        assert session.status()["phase"] == "FOLLOWING", session.status()
        path = record_one(session)
        assert (path / "commands.jsonl").stat().st_size > 0
        assert inspect_episode(path)["complete"]
        from agx_runtime.raw import replay_commands

        commands = list(replay_commands(path))
        assert commands and all(len(c.positions) == 4 for c in commands)
        if mode == "sampled":
            assert (path / "selections.jsonl").stat().st_size > 0
    finally:
        session.stop()
        assert session.wait(3)


@pytest.mark.parametrize("block", ["boundary", "disk"])
def test_hal_fault_does_not_wait_for_blocked_record_finish(
    tmp_path, monkeypatch, block
):
    from agx_runtime import raw

    entered, release = threading.Event(), threading.Event()
    session = start(configuration(tmp_path, teleop=True))
    try:
        session.confirm(True)
        wait_for(lambda: session.status()["phase"] == "FOLLOWING", 3)
        if block == "disk":
            original = raw.write_sample

            def blocked(*args):
                entered.set()
                release.wait(3)
                return original(*args)

            monkeypatch.setattr(raw, "write_sample", blocked)
        else:
            client = session.supervisor.boundary_clients()["front"]
            original = client.request

            def blocked(method, **args):
                if method == "boundary_end":
                    entered.set()
                    release.wait(3)
                return original(method, **args)

            monkeypatch.setattr(client, "request", blocked)
        session.record()
        wait_for(lambda: session.episode.started)
        time.sleep(0.1)
        session.save()
        assert entered.wait(1)
        before = time.monotonic()
        session.supervisor.processes["leader"].kill()
        assert session.wait(1.2)
        assert time.monotonic() - before < 1.2
        assert session.status()["error"]
        assert session.episode.error
        release.set()
        time.sleep(0.1)
        assert not (session.episode.path / "complete.json").exists()
    finally:
        release.set()
        session.stop()
        session.wait(3)


def test_camera_required_during_following_and_lock_is_shared(tmp_path):
    config = configuration(tmp_path, teleop=True)
    session = start(config)
    other = importlib.import_module("agx_runtime.session").Session(config)
    try:
        other.prepare()
        assert other.wait(2)
        assert "lock" in other.status()["error"]
        session.confirm(True)
        wait_for(lambda: session.status()["phase"] == "FOLLOWING", 3)
        session.supervisor.processes["front"].kill()
        assert session.wait(2)
        assert session.status()["phase"] == "FAILED"
        assert "front" in session.status()["error"]
    finally:
        other.stop()
        session.stop()
        session.wait(3)


def test_missing_control_policy_cannot_hide_feedback_or_authorize(tmp_path):
    config = configuration(tmp_path, teleop=True)
    config = replace(
        config, streams=tuple(p for p in config.streams if p.key != "arm/joints")
    )
    session = importlib.import_module("agx_runtime.session").Session(config)
    session.prepare()
    assert session.wait(5)
    assert "explicit policy" in session.status()["error"]


@pytest.mark.parametrize("invalid_feedback", [False, True])
def test_explicit_simulated_zero_policy_checks_feedback(
    tmp_path, monkeypatch, invalid_feedback
):
    from agilex_contract import Sample

    config = configuration(tmp_path, teleop=True)
    config = replace(
        config,
        devices=tuple(
            replace(d, exit_policy="simulated_zero") if d.kind == "follower" else d
            for d in config.devices
        ),
    )
    session = start(config)
    session.confirm(True)
    wait_for(lambda: session.status()["phase"] == "FOLLOWING", 3)
    if invalid_feedback:
        client = session.clients["arm"]
        original = client.receive

        def invalid(*args):
            event = original(*args)
            return (
                replace(event, header=replace(event.header, valid=False))
                if isinstance(event, Sample)
                else event
            )

        monkeypatch.setattr(client, "receive", invalid)
        wait_for(lambda: session.status()["error"] is not None)
    session.stop()
    assert session.wait(3)
    result = session.status()["exit_actions"]["arm"]
    if invalid_feedback:
        assert result["result"] == "refused"
        assert result["steps"] == 0
    else:
        assert result["result"] == "completed"
        assert max(abs(p) for p in result["positions"]) <= 0.026180


def test_lost_command_channel_triggers_ack_watchdog(tmp_path, monkeypatch):
    session = start(configuration(tmp_path, teleop=True))
    try:
        session.confirm(True)
        wait_for(lambda: session.status()["phase"] == "FOLLOWING", 3)
        monkeypatch.setattr(session.clients["arm"], "send", lambda command: False)
        assert session.wait(2)
        assert "acknowledgement" in session.status()["error"]
    finally:
        session.stop()
        session.wait(3)


def test_discard_closes_episode_boundary_and_allows_new_recording(tmp_path):
    session = start(configuration(tmp_path))
    try:
        session.record()
        time.sleep(0.12)
        discarded = session.episode
        session.discard()
        wait_for(lambda: session.status()["phase"] == "READY")
        assert discarded.phase == "DISCARDED"
        assert not (discarded.path / "complete.json").exists()
        assert inspect_episode(record_one(session))["complete"]
    finally:
        session.stop()
        session.wait(3)


def test_runtime_process_crash_leaves_external_hal_watchdog_in_control(tmp_path):
    with (
        tempfile.TemporaryDirectory(prefix="agx-crash-") as temporary,
        ExitStack() as stack,
    ):
        endpoints = Path(temporary)
        for name, kind in (
            ("leader", "leader"),
            ("arm", "follower"),
            ("front", "camera"),
        ):
            client, _, _ = stack.enter_context(running(endpoints, kind, name))
            if name == "arm":
                follower = client
        script = """
import sys, time
from pathlib import Path
from agx_runtime.config import load_config
from agx_runtime.session import Session
endpoints, root = map(Path, sys.argv[1:])
config = load_config('config/runtime-sim.toml', {
    'runtime': {'lock_path':str(root/'lock'), 'data_root':str(root/'raw')},
    'devices': [
        {'device_id':name, 'kind':kind, 'endpoint':str(endpoints/name)}
        for name,kind in [('leader','leader'),('arm','follower'),('front','camera')]
    ],
})
session = Session(config)
session.prepare()
deadline = time.monotonic()+6
while session.status()['phase'] != 'CONFIRM':
    assert time.monotonic()<deadline, session.status()
    time.sleep(.005)
session.confirm(True)
while session.status()['phase'] != 'FOLLOWING':
    assert time.monotonic()<deadline, session.status()
    time.sleep(.005)
(root/'following').write_text('ready')
while True: time.sleep(1)
"""
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(endpoints), str(tmp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_for(
                lambda: (tmp_path / "following").exists() or process.poll() is not None,
                8,
            )
            assert process.poll() is None, process.communicate()[1]
            process.kill()
            process.wait(timeout=2)
            wait_for(lambda: follower.request("status")["phase"] == "FAULTED", 2)
            assert follower.request("status")["reason"] == "command_timeout"
            assert follower.request("status")["pending"] is False
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=2)
