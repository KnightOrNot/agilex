"""The daemon and embedded CLI share Session; no hardware modules on import."""

import importlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
from test_runtime_recording import wait_for
from test_runtime_session import configuration


def test_daemon_owner_commands_and_watchdog(tmp_path):
    module = importlib.import_module("agx_runtime.service")
    with tempfile.TemporaryDirectory(prefix="agx-api-") as temporary:
        directory = Path(temporary)
        service = module.RuntimeService(configuration(tmp_path), directory)
        worker = threading.Thread(target=service.run, daemon=True)
        worker.start()
        client = module.RuntimeClient(directory, "operator")
        try:
            assert stat.S_IMODE((directory / "control.sock").stat().st_mode) == 0o600
            with pytest.raises(ValueError):
                client.request("prepare")
            client.request("acquire")
            other = module.RuntimeClient(directory, "other")
            with pytest.raises(ValueError):
                other.request("prepare")
            with pytest.raises(ValueError):
                client.request("prepare", unexpected=True)
            client.request("prepare")
            deadline = time.monotonic() + 6
            while client.request("status")["phase"] != "READY":
                assert time.monotonic() < deadline
                client.request("heartbeat")
                time.sleep(0.01)
            assert "front/rgb" in client.request("preview")
            client.request("record")
            time.sleep(0.15)
            client.request("save")

            def saved():
                client.request("heartbeat")
                return client.request("status")["episode"]["phase"] == "COMPLETE"

            wait_for(saved, 7)
            # Read-only polling is not a heartbeat; a disconnected controller
            # cannot keep motion alive through an unrelated status subscriber.
            wait_for(lambda: client.request("status")["phase"] == "FAILED", 3)
            assert "watchdog" in client.request("status")["error"]
            client.request("shutdown")
            worker.join(3)
            assert not worker.is_alive()
        finally:
            service.stop()
            worker.join(3)
        assert not (directory / "control.sock").exists()


def test_runtime_import_is_independent_of_sim_and_hardware():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import agx_runtime.session, agx_runtime.service; "
            "assert not any(k.startswith(('agx_sim', 'agilex_gello', "
            "'camera_realsense', 'piper_sdk', 'lerobot')) for k in sys.modules)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_cli_sensor_run_and_offline_check(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agx_runtime",
            "run",
            "--config",
            "config/runtime-sensors.toml",
            "--seconds",
            "0.2",
            "--data-root",
            str(tmp_path / "raw"),
            "--lock-path",
            str(tmp_path / "session.lock"),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    assert report["episode"]["phase"] == "COMPLETE"
    for action in ("check", "replay"):
        checked = subprocess.run(
            [sys.executable, "-m", "agx_runtime", action, report["episode"]["path"]],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert checked.returncode == 0, checked.stderr


def test_service_rejects_public_or_symlink_directory(tmp_path):
    module = importlib.import_module("agx_runtime.service")
    with pytest.raises(PermissionError):
        os.chmod(tmp_path, 0o755)
        module.RuntimeService(configuration(tmp_path), tmp_path)
