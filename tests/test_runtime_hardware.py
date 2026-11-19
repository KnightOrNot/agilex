"""Actual physical HAL wrappers over private IPC; all hardware backends injected."""

import json
import multiprocessing
import os
import queue
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from types import SimpleNamespace

import numpy as np
import pytest
from test_hal_piperx import Driver
from test_hal_realsense import Stream
from test_runtime_recording import wait_for

from agx_hal.server import HalServer
from agx_hal_gello.device import GelloDevice
from agx_hal_piperx.device import PiperXDevice
from agx_hal_realsense.device import RealSenseDevice
from agx_runtime.config import DeviceConfig, RecordConfig, RuntimeConfig, StreamPolicy
from agx_runtime.raw import inspect_episode, inventory, replay_commands, replay_episode
from agx_runtime.session import Session


@pytest.mark.parametrize(
    "backend,kind,settings",
    [
        ("gello", "follower", {}),
        ("piperx", "follower", {"bogus": 1}),
        ("realsense", "camera", {"serial": ""}),
        ("gello", "leader", {"port": "/dev/fake", "use_fake_fallback": True}),
    ],
)
def test_invalid_hardware_deployment_is_rejected(backend, kind, settings):
    with pytest.raises(ValueError):
        DeviceConfig("device", kind, backend=backend, settings=settings)


def fake_hal_process(kind, directory, settings, enabled, positions, commands):
    class LiveDriver(Driver):
        def get_state(self):
            self.timestamp = time.time()
            self.enabled = enabled.value
            return super().get_state()

        def get_gripper_status(self):
            self.gripper_stamp = time.time()
            return super().get_gripper_status()

        def enable(self, *, before_send):
            super().enable(before_send=before_send)
            enabled.value = True

        def command_joints(self, target, *, fast_response, before_send):
            super().command_joints(
                target, fast_response=fast_response, before_send=before_send
            )
            self.positions = tuple(target)
            positions[:] = target
            commands.put(tuple(target))

    class Source:
        @property
        def _last_successful_read(self):
            return time.monotonic()

    class Agent:
        def __init__(self):
            self._robot = SimpleNamespace(_driver=Source())

        def act(self, obs):
            return np.array([0.1, 0.1, -0.1, 0.0, 0.0, 0.0, 0.4])

        def close(self):
            pass

    class Camera(Stream):
        seq = 0

        def read(self, timeout_s):
            self.seq += 1
            name = "color" if self.seq % 2 else "depth"
            image = (
                np.zeros((1, 2, 3), dtype=np.uint8)
                if name == "color"
                else np.array([[0, 65535]], dtype=np.uint16)
            )
            stamp = time.monotonic_ns()
            wall = time.time_ns()
            return SimpleNamespace(
                stream=name,
                image=image,
                timestamp_ns=stamp,
                received_time_ns=stamp,
                sdk_timestamp_ms=wall / 1e6,
                sdk_timestamp_domain="global_time",
                frame_number=self.seq,
                clock_offset_ns=stamp - wall,
                clock_uncertainty_ns=1000,
            )

    if kind == "gello":
        device = GelloDevice(
            dict(settings, device_id="leader"),
            agent_factory=lambda s: Agent(),
            probe=lambda s: {},
        )
    elif kind == "piperx":
        device = PiperXDevice(
            dict(settings, device_id="arm"), driver_factory=lambda **kw: LiveDriver()
        )
    else:
        device = RealSenseDevice(
            dict(settings, device_id="front"), stream_factory=Camera, probe=lambda s: {}
        )
    server = HalServer(device, directory)
    signal.signal(signal.SIGTERM, lambda *_: setattr(server, "stopping", True))
    server.run()


class DriverReport:
    def __init__(self, enabled, positions, commands):
        self._enabled, self._positions, self._commands = enabled, positions, commands
        self._history = []

    @property
    def enabled(self):
        return self._enabled.value

    def drop_enable(self):
        self._enabled.value = False

    @property
    def positions(self):
        return tuple(self._positions[:])

    @property
    def joint_commands(self):
        while True:
            try:
                self._history.append(self._commands.get_nowait())
            except queue.Empty:
                return self._history


@contextmanager
def hardware(tmp_path, mode="full"):
    context = multiprocessing.get_context("spawn")
    enabled, positions = context.Value("b", False), context.Array("d", 6)
    commands = context.Queue()
    options = dict(
        port="/dev/fake",
        joint_ids=list(range(1, 7)),
        joint_offsets=[0.0] * 6,
        joint_signs=[1] * 6,
        gripper_config=[7, 0, 90],
        gripper_max_width_m=0.1,
        start_joints=[0.0] * 7,
    )
    items = [
        ("leader", "leader", "gello", options),
        ("arm", "follower", "piperx", {}),
        ("front", "camera", "realsense", {"serial": "test"}),
    ]
    processes, devices, policies = [], [], []
    try:
        for name, kind, backend, settings in items:
            directory = tmp_path / name
            process = context.Process(
                target=fake_hal_process,
                args=(backend, directory, settings, enabled, positions, commands),
            )
            process.start()
            processes.append(process)
            devices.append(
                DeviceConfig(
                    name,
                    kind,
                    backend=backend,
                    settings=settings,
                    endpoint=str(directory),
                    exit_policy="piperx_return_zero" if kind == "follower" else "",
                )
            )
            for stream in (
                ("rgb", "depth") if kind == "camera" else ("joints", "gripper")
            ):
                policies.append(
                    StreamPolicy(
                        name,
                        stream,
                        "record_required" if kind == "camera" else "control_required",
                        ("READY", "ALIGN", "FOLLOWING", "RECORDING"),
                    )
                )
        config = RuntimeConfig(
            devices=tuple(devices),
            streams=tuple(policies),
            leader="leader",
            follower="arm",
            data_root=str(tmp_path / "raw"),
            lock_path=str(tmp_path / "lock"),
            record=RecordConfig(mode=mode),
        )
        yield config, DriverReport(enabled, positions, commands)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(3)
            if process.is_alive():
                process.kill()
                process.join(1)
                pytest.fail("fake HAL did not close")
        commands.close()


@pytest.mark.parametrize("mode", ["full", "sampled"])
def test_physical_wrappers_save_native_raw_without_preconfirmation_motion(
    tmp_path, mode
):
    with hardware(tmp_path, mode) as (config, driver):
        session = Session(config)
        session.prepare()
        try:
            wait_for(lambda: session.phase in ("CONFIRM", "FAILED"), 8)
            assert session.error is None, session.status()
            assert not driver.enabled and not driver.joint_commands
            session.confirm(True)
            wait_for(lambda: session.phase in ("FOLLOWING", "FAILED"), 4)
            assert session.phase == "FOLLOWING", session.status()
            assert driver.joint_commands[0] == (0.0,) * 6
            assert any(max(abs(v) for v in c) > 0.025 for c in driver.joint_commands)
            session.record()
            time.sleep(0.25)
            session.save()
            wait_for(lambda: session.episode.done, 7)
            assert session.episode.error is None, session.status()
            assert inspect_episode(session.episode.path)["complete"]
            samples = list(replay_episode(session.episode.path))
            camera = [s for s in samples if s.header.device_id == "front"]
            assert camera and all(s.payload.info.calibration_id for s in camera)
            manifest = json.loads((session.episode.path / "manifest.json").read_text())
            assert (
                manifest["metadata"]["hal_metadata"]["front"]["camera"]["depth"][
                    "depth_units_m"
                ]
                == 0.001
            )
            assert list(replay_commands(session.episode.path))
            damaged = tmp_path / "missing-calibration"
            shutil.copytree(session.episode.path, damaged)
            manifest["metadata"]["hal_metadata"]["front"]["calibrations"] = {}
            (damaged / "manifest.json").write_text(json.dumps(manifest))
            complete = json.loads((damaged / "complete.json").read_text())
            complete["files"] = inventory(damaged)
            (damaged / "complete.json").write_text(json.dumps(complete))
            with pytest.raises(ValueError, match="calibration"):
                inspect_episode(damaged)
        finally:
            session.stop()
            assert session.wait(4)
        assert session.status()["exit_actions"]["arm"]["result"] == "completed", (
            session.status()
        )
        assert max(abs(p) for p in driver.positions) <= np.deg2rad(1.5)
        assert driver.enabled


def test_physical_exit_never_reenables_disabled_arm(tmp_path):
    with hardware(tmp_path) as (config, driver):
        session = Session(config)
        session.prepare()
        try:
            wait_for(lambda: session.phase in ("CONFIRM", "FAILED"), 8)
            assert session.error is None, session.status()
            session.confirm(True)
            wait_for(lambda: session.phase in ("FOLLOWING", "FAILED"), 4)
            assert session.phase == "FOLLOWING", session.status()
            driver.drop_enable()
            assert session.wait(4), session.status()
        finally:
            session.stop()
            assert session.wait(4)
        result = session.status()["exit_actions"]["arm"]
        assert result["result"] == "refused" and result["steps"] == 0
        assert not driver.enabled


def test_real_hal_entrypoint_help_does_not_import_device_libraries():
    for name in ("agx_hal_piperx", "agx_hal_gello", "agx_hal_realsense"):
        result = subprocess.run(
            [sys.executable, "-m", name, "--help"],
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
    script = """
import sys
import agx_runtime.session, agx_runtime.config
prefixes = ('agilex_sdk_python', 'agilex_gello_software', 'camera_realsense',
            'pyrealsense2', 'pyAgxArm')
assert not any(n.startswith(prefixes) for n in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], text=True, capture_output=True, timeout=10
    )
    assert result.returncode == 0, result.stderr


def test_hardware_example_interpreters_resolve_from_config_not_shell_cwd(
    tmp_path, monkeypatch
):
    from pathlib import Path

    from agx_runtime.config import load_config

    path = Path("config/runtime-hardware.example.toml").resolve()
    monkeypatch.chdir(tmp_path)
    result = load_config(path)
    projects = ("agilex-gello-software", "agilex-sdk-python", "camera-realsense-d455f")
    assert [Path(device.python) for device in result.devices] == [
        path.parents[1] / "third-party" / project / ".venv/bin/python"
        for project in projects
    ]
    assert result.devices[1].exit_policy == "piperx_return_zero"
    assert result.motion.position_tolerance_deg == 1.5


def test_hardware_run_refuses_noninteractive_confirmation_before_session(monkeypatch):
    from agx_runtime import __main__ as runtime_cli
    from agx_runtime.config import load_config

    config = load_config("config/runtime-hardware.example.toml")
    monkeypatch.setattr(runtime_cli, "Session", lambda _: pytest.fail("opened session"))
    with pytest.raises(ValueError, match="interactive confirmation"):
        runtime_cli.run(config, 0.1, "yes")


def test_hardware_run_shows_real_target_before_requesting_confirmation(
    monkeypatch, capsys
):
    from agx_runtime import __main__ as runtime_cli
    from agx_runtime.config import load_config

    config = load_config("config/runtime-hardware.example.toml")
    target = {"positions": [0.0] * 6}
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    def decline(prompt):
        assert "physical PiPER-X" in prompt
        assert json.loads(capsys.readouterr().out) == {"hardware_motion_target": target}
        return "no"

    monkeypatch.setattr("builtins.input", decline)
    monkeypatch.setattr(
        runtime_cli,
        "Session",
        lambda _: SimpleNamespace(
            prepare=lambda: None,
            status=lambda: {"phase": "CONFIRM", "target": target, "error": None},
            stop=lambda *_: None,
            wait=lambda _: True,
        ),
    )
    with pytest.raises(ValueError, match="motion was not confirmed"):
        runtime_cli.run(config, 0.1)


def test_runtime_daemon_refuses_physical_following_without_operator_ui(tmp_path):
    from agx_runtime.config import load_config
    from agx_runtime.service import RuntimeService

    config = load_config("config/runtime-hardware.example.toml")
    endpoint = tmp_path / "daemon"
    with pytest.raises(ValueError, match="interactive confirmation"):
        RuntimeService(config, endpoint)
    assert not endpoint.exists()


def test_supervisor_launches_physical_hal_with_selected_interpreter_and_closes_it(
    tmp_path, monkeypatch
):
    from pathlib import Path

    from test_runtime_session import record_one

    package = tmp_path / "fake-sdk" / "agilex_sdk_python"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "driver.py").write_text("""
import os, time
from pathlib import Path
from test_hal_piperx import Driver
class PiperXDriver(Driver):
    def __init__(self, **kwargs): super().__init__()
    def connect(self):
        super().connect()
        Path(os.environ['AGX_TEST_SDK_TRACE']).write_text('connected')
    def get_state(self):
        self.timestamp=time.time()
        return super().get_state()
    def get_gripper_status(self):
        self.gripper_stamp=time.time()
        return super().get_gripper_status()
    def close(self):
        super().close()
        Path(os.environ['AGX_TEST_SDK_TRACE']).write_text('closed')
""")
    trace = tmp_path / "trace"
    monkeypatch.setenv("AGX_TEST_SDK_TRACE", str(trace))
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join((str(package.parent), str(Path("tests").resolve()))),
    )
    config = RuntimeConfig(
        devices=(
            DeviceConfig("arm", "follower", backend="piperx", python=sys.executable),
        ),
        streams=tuple(
            StreamPolicy("arm", name, "record_required", ("READY", "RECORDING"))
            for name in ("joints", "gripper")
        ),
        data_root=str(tmp_path / "raw"),
        lock_path=str(tmp_path / "lock"),
    )
    session = Session(config)
    session.prepare()
    try:
        wait_for(lambda: session.phase in ("READY", "FAILED"), 8)
        assert session.error is None, session.status()
        assert trace.read_text() == "connected"
        assert inspect_episode(record_one(session))["samples"] > 0
    finally:
        session.stop()
        assert session.wait(4)
    assert trace.read_text() == "closed"
    assert all(p.poll() is not None for p in session.supervisor.processes.values())
