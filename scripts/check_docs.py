"""Validate project routing and paired documentation without network access."""

from __future__ import annotations

import argparse
import html
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "HABITS.md",
    "SKILLS.md",
    ".ai-stage",
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.zh-CN.md",
    "Makefile",
    ".agents/project.md",
    ".agents/conventions.md",
    ".agents/workflows.md",
    ".agents/constraints.md",
    ".agents/git.md",
)
STAGES = {
    "PLANNING": "planning.md",
    "CODING": "architecture.md",
    "TESTING": "testing.md",
    "DEPLOY": "deployment.md",
}
REQUIRED_PAGES = {
    "index.md",
    "installation.md",
    "reference/cli.md",
    "reference/config.md",
    "reference/errors.md",
}
FENCES = re.compile(r"^```([^\n]*)\n(.*?)^```[^\S\n]*$", re.M | re.S)
LINKS = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")


def examples(text: str) -> Counter[tuple[str, str]]:
    """Compare executable examples while allowing translated comments."""
    result: Counter[tuple[str, str]] = Counter()
    for language, body in FENCES.findall(text):
        if language not in {"bash", "sh", "python", "toml", "json"}:
            continue
        lines = []
        for line in body.splitlines():
            # These documentation examples do not use # inside string values.
            line = line.split("#", 1)[0].strip()
            if line:
                lines.append(line)
        result[(language, "\n".join(lines))] += 1
    return result


def anchors(text: str) -> set[str]:
    """Build GitHub-style heading anchors, including repeated headings."""
    seen: Counter[str] = Counter()
    result = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        heading = re.sub(r"<[^>]*>", "", heading)
        heading = re.sub(r"[^\w\- ]", "", html.unescape(heading).lower())
        heading = heading.replace(" ", "-")
        suffix = f"-{seen[heading]}" if seen[heading] else ""
        result.add(heading + suffix)
        seen[heading] += 1
    return result


def validate(root: Path) -> list[str]:
    """Return actionable failures; do not mutate documentation or environments."""
    errors = []
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            errors.append(f"Missing required file: {name}")
    for language in ("en", "zh"):
        for name in sorted(REQUIRED_PAGES):
            if not (root / "docs" / language / name).is_file():
                errors.append(f"Missing required page: docs/{language}/{name}")
    agents = root / "AGENTS.md"
    if agents.is_file() and len(agents.read_text().splitlines()) > 60:
        errors.append("AGENTS.md must contain at most 60 lines")
    bridge = root / "CLAUDE.md"
    if bridge.is_file() and bridge.read_text() != "@AGENTS.md\n":
        errors.append("CLAUDE.md must contain only @AGENTS.md and a newline")
    stage_file = root / ".ai-stage"
    if stage_file.is_file():
        stage = stage_file.read_text().strip()
        if stage not in STAGES:
            errors.append(".ai-stage must contain exactly one supported stage")
        else:
            stage_path = root / ".agents/docs/stages" / STAGES[stage]
            if not stage_path.is_file():
                errors.append(f"Missing current stage document: {stage_path.name}")
            if agents.is_file() and f"`{stage}`" not in agents.read_text():
                errors.append("AGENTS.md current stage does not match .ai-stage")

    pairs = [
        (root / "README.md", root / "README.zh-CN.md"),
        (root / "CONTRIBUTING.md", root / "CONTRIBUTING.zh-CN.md"),
    ]
    pages = {}
    for language in ("en", "zh"):
        directory = root / "docs" / language
        pages[language] = {
            path.relative_to(directory) for path in directory.rglob("*.md")
        }
    for missing in sorted(pages["en"] ^ pages["zh"]):
        errors.append(f"Missing bilingual counterpart: {missing}")
    pairs.extend(
        (root / "docs/en" / name, root / "docs/zh" / name)
        for name in sorted(pages["en"] & pages["zh"])
    )
    for english, chinese in pairs:
        if not english.is_file() or not chinese.is_file():
            continue
        for source, target in ((english, chinese), (chinese, english)):
            targets = []
            introduction = "\n".join(source.read_text().splitlines()[1:6])
            for raw in LINKS.findall(introduction):
                targets.append((source.parent / raw).resolve())
            if target.resolve() not in targets:
                errors.append(f"Missing top language link: {source.relative_to(root)}")
        if examples(english.read_text()) != examples(chinese.read_text()):
            errors.append(f"Bilingual example drift: {english.relative_to(root)}")

    documents = set(root.glob("*.md"))
    documents.update(root.glob("docs/**/*.md"))
    documents.update(root.glob(".agents/**/*.md"))
    for source in sorted(documents):
        text = FENCES.sub("", source.read_text())
        for raw in LINKS.findall(text):
            parsed = urlsplit(raw.strip("<>"))
            if parsed.scheme or parsed.netloc:
                continue
            target = (source.parent / unquote(parsed.path)).resolve()
            if not parsed.path:
                target = source.resolve()
            if not target.exists():
                errors.append(f"Broken link in {source.relative_to(root)}: {raw}")
            elif parsed.fragment and target.suffix == ".md":
                if unquote(parsed.fragment) not in anchors(target.read_text()):
                    errors.append(f"Broken anchor in {source.relative_to(root)}: {raw}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    root = parser.parse_args().root.resolve()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "Documentation OK: routing, required files, bilingual pages/examples and links"
    )
    print("Scope: local links and executable examples; prose translation needs review")
    print(
        "Not configured: root mypy, coverage threshold, pre-commit; "
        "not reported as passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
