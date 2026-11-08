"""Exercise documentation checks on editable copies, without network access."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def documentation(tmp_path):
    for source in ROOT.glob("*.md"):
        shutil.copy2(source, tmp_path / source.name)
    for name in (".ai-stage", "Makefile", "LICENSE"):
        shutil.copy2(ROOT / name, tmp_path / name)
    for name in ("docs", ".agents"):
        shutil.copytree(ROOT / name, tmp_path / name)
    for name in ("third-party", "config"):
        (tmp_path / name).symlink_to(ROOT / name, target_is_directory=True)
    return tmp_path


def check(root):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_docs.py"), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_paired_documentation_is_valid(documentation):
    result = check(documentation)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_translation_fails(documentation):
    (documentation / "docs/zh/reference/cli.md").unlink()
    result = check(documentation)
    assert result.returncode == 1
    assert "Missing bilingual counterpart: reference/cli.md" in result.stdout


def test_changed_configuration_example_fails(documentation):
    path = documentation / "docs/zh/reference/config.md"
    path.write_text(path.read_text().replace("hz = 50.0", "hz = 51.0", 1))
    result = check(documentation)
    assert result.returncode == 1
    assert "Bilingual example drift: docs/en/reference/config.md" in result.stdout


@pytest.mark.parametrize("target", ["missing.md", "#missing-heading"])
def test_broken_link_or_anchor_fails(documentation, target):
    path = documentation / "README.md"
    path.write_text(path.read_text() + f"\n[Broken link]({target})\n")
    result = check(documentation)
    assert result.returncode == 1
    assert "Broken" in result.stdout


def test_removed_language_link_reports_error_without_crashing(documentation):
    (documentation / "README.md").write_text("# Incomplete landing page\n")
    result = check(documentation)
    assert result.returncode == 1
    assert "Missing top language link: README.md" in result.stdout
    assert not result.stderr


def test_stage_transition_requires_document_and_routing(documentation):
    (documentation / ".ai-stage").write_text("CODING\n")
    result = check(documentation)
    assert result.returncode == 1
    assert "Missing current stage document: architecture.md" in result.stdout
    assert "current stage does not match" in result.stdout


def test_claude_bridge_cannot_accumulate_project_rules(documentation):
    (documentation / "CLAUDE.md").write_text("@AGENTS.md\nExtra duplicated rules\n")
    result = check(documentation)
    assert result.returncode == 1
    assert "CLAUDE.md must contain only" in result.stdout


def test_missing_skill_index_fails(documentation):
    (documentation / "SKILLS.md").unlink()
    result = check(documentation)
    assert result.returncode == 1
    assert "Missing required file: SKILLS.md" in result.stdout
