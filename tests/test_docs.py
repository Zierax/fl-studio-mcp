"""Tests that keep the documentation honest.

Documentation drifts silently: hard coded paths, invalid JSON snippets and
stale version numbers. These tests turn the most common mistakes into
failures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

DOC_FILES = sorted(
    path
    for pattern in ("*.md", "docs/*.md")
    for path in REPO_ROOT.glob(pattern)
    if path.is_file()
)


def _json_blocks(text: str) -> list[str]:
    """Return every ```json fenced block in *text*."""
    return re.findall(r"```json\n(.*?)```", text, re.DOTALL)


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: p.name)
def test_json_snippets_are_valid(doc: Path):
    """Every ```json block must be parseable JSON."""
    blocks = _json_blocks(doc.read_text(encoding="utf-8"))
    for index, block in enumerate(blocks):
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            pytest.fail(f"{doc.name}: json block #{index + 1} is invalid: {e}\n\n{block}")


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: p.name)
def test_no_hardcoded_author_paths(doc: Path):
    """The author's checkout path must not leak into the documentation."""
    text = doc.read_text(encoding="utf-8")
    assert "D:\\\\Axioms" not in text, f"{doc.name} contains a hard coded local path"
    assert "D:\\Axioms" not in text, f"{doc.name} contains a hard coded local path"


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: p.name)
def test_relative_links_exist(doc: Path):
    """Relative markdown links must point at files that exist."""
    text = doc.read_text(encoding="utf-8")
    for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        resolved = (doc.parent / target).resolve()
        assert resolved.exists(), f"{doc.name}: broken link -> {target}"


def test_readme_documents_the_mcp_config():
    """The README must show a copy-pasteable MCP client configuration."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    blocks = _json_blocks(readme)
    assert blocks, "README has no json snippet"

    config = None
    for block in blocks:
        parsed = json.loads(block)
        if isinstance(parsed, dict) and "mcpServers" in parsed:
            config = parsed
            break

    assert config is not None, "README has no mcpServers snippet"
    server = config["mcpServers"]["fl-studio"]
    assert server["command"] == "uv"
    assert "--directory" in server["args"]
    assert server["args"][-1] == "fl-studio-mcp"


def test_setup_documents_the_mcp_config():
    setup = (REPO_ROOT / "docs" / "SETUP.md").read_text(encoding="utf-8")
    blocks = _json_blocks(setup)
    configs = [json.loads(block) for block in blocks]
    matching = [c for c in configs if isinstance(c, dict) and "mcpServers" in c]
    assert matching, "SETUP.md has no mcpServers snippet"
    assert matching[0]["mcpServers"]["fl-studio"]["command"] == "uv"


def test_version_is_consistent():
    """The version in pyproject must match the one advertised in the README."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"Version {version}" in readme, f"README does not mention version {version}"


def test_troubleshooting_mentions_the_stripped_standard_library():
    """The ModuleNotFoundError from GitHub issue #2 must be documented."""
    troubleshooting = (REPO_ROOT / "docs" / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
    assert "ModuleNotFoundError" in troubleshooting
    assert "json" in troubleshooting


def test_troubleshooting_hot_reload_marker_matches_the_script():
    """The MCP_VERSION shown in the docs must match the controller script."""
    troubleshooting = (REPO_ROOT / "docs" / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
    script = (REPO_ROOT / "fl_controller" / "device_FLStudioMCP.py").read_text(encoding="utf-8")
    version = re.search(r"^MCP_VERSION = (\d+)", script, re.MULTILINE).group(1)
    assert f"MCP_VERSION = {version}" in troubleshooting
