"""Installer control flow with fake tools; never install or access hardware."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / "project"
    (root / "scripts").mkdir(parents=True)
    shutil.copyfile(
        Path(__file__).parents[1] / "scripts/setup.sh", root / "scripts/setup.sh"
    )
    (root / ".gitmodules").touch()
    for name in ("raw", "lerobot"):
        (root / "data" / name).mkdir(parents=True)
    projects = [
        root,
        *(
            root / "third-party" / name
            for name in (
                "agilex-sdk-python",
                "agilex-gello-software",
                "lerobot-converter",
                "camera-realsense-d455f",
                "agilex-adapters",
            )
        ),
    ]
    for project in projects:
        project.mkdir(parents=True, exist_ok=True)
        (project / "pyproject.toml").touch()
        (project / ".python-version").write_text("3.12\n")
        executable(
            project / ".venv/bin/python",
            '#!/bin/sh\ncase "$*" in *platform.python_version*) '
            'echo "${TEST_PYTHON_VERSION:-3.12.16}";; esac\n',
        )
        for cli in (
            "agilex-sdk-python",
            "agilex-sdk-python-server",
            "agilex-gello-software",
            "lerobot-converter",
        ):
            executable(project / ".venv/bin" / cli, "#!/bin/sh\nexit 0\n")
    tools = tmp_path / "bin"
    executable(
        tools / "uv",
        f"#!{sys.executable}\nimport json, os, sys\n"
        "with open(os.environ['UV_TEST_LOG'], 'a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n",
    )
    executable(tools / "git", "#!/bin/sh\nexit 1\n")
    executable(tools / "ffmpeg", "#!/bin/sh\nexit 0\n")
    log = tmp_path / "uv.jsonl"
    env = {
        **os.environ,
        "PATH": f"{tools}:{os.environ['PATH']}",
        "UV_TEST_LOG": str(log),
    }
    return root, env, log


def test_setup_installs_managed_python_and_frozen_environments(installation):
    root, env, log = installation
    result = subprocess.run(
        ["bash", str(root / "scripts/setup.sh"), "--skip-system", "--skip-submodules"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls.count(["python", "install", "3.12"]) == 5
    syncs = [call for call in calls if call[0] == "sync"]
    assert len(syncs) == 5
    assert all("--managed-python" in call and "--frozen" in call for call in syncs)
    assert any("dataset" in call for call in syncs)


@pytest.mark.parametrize("version, expected", [("3.12.16", 0), ("3.11.18", 1)])
def test_check_only_checks_version_without_installing(installation, version, expected):
    root, env, log = installation
    result = subprocess.run(
        ["bash", str(root / "scripts/setup.sh"), "--check-only"],
        env={**env, "TEST_PYTHON_VERSION": version},
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected, result.stderr
    assert [json.loads(line) for line in log.read_text().splitlines()] == [
        ["--version"]
    ]
    if expected:
        assert "需要 3.12" in result.stderr
