"""Tests for the prompt pack.

The prompt pack tells an AI which tools to call. If it names a tool that
does not exist, the AI will call a phantom and the whole "verify with a
read-back" discipline collapses.  These tests keep the pack and the server
in sync.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

PROMPT_DIR = REPO_ROOT / "prompts"
PROMPT_FILES = sorted(PROMPT_DIR.glob("*.md"))

#: The tool names the server actually exposes.
def _server_tool_names() -> set[str]:
    pytest.importorskip("fastmcp")
    import asyncio

    from fl_studio_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


@pytest.fixture(scope="module")
def tool_names() -> set[str]:
    return _server_tool_names()


def test_the_prompt_pack_exists():
    assert PROMPT_FILES, "prompts/ is empty"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: p.name)
def test_prompt_files_are_not_empty(path: Path):
    text = path.read_text(encoding="utf-8")
    assert len(text.strip()) > 200, f"{path.name} is suspiciously short"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: p.name)
def test_prompt_files_have_no_broken_relative_links(path: Path):
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        resolved = (path.parent / target).resolve()
        assert resolved.exists(), f"{path.name}: broken link -> {target}"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: p.name)
def test_prompt_files_reference_only_real_tools(path: Path, tool_names: set[str]):
    """Every `fl_*` tool mentioned in the prompt pack must exist."""
    text = path.read_text(encoding="utf-8")
    mentioned = set(re.findall(r"\bfl_[a-z0-9_]+\b", text))
    unknown = sorted(name for name in mentioned if name not in tool_names)
    assert not unknown, f"{path.name} mentions tools that do not exist: {unknown}"


def test_the_pack_covers_the_essentials():
    """The pack must contain the files the README promises."""
    names = {path.name for path in PROMPT_FILES}
    for required in (
        "README.md",
        "CORE.md",
        "BRIDGE.md",
        "WORKFLOW.md",
        "RECIPE.md",
        "GENRES.md",
        "ARRANGEMENT.md",
        "THEORY.md",
        "MIXING.md",
        "QC.md",
    ):
        assert required in names, f"prompts/{required} is missing"


def test_readme_links_every_prompt_file():
    readme = (PROMPT_DIR / "README.md").read_text(encoding="utf-8")
    for path in PROMPT_FILES:
        if path.name == "README.md":
            continue
        assert path.name in readme, f"prompts/README.md does not mention {path.name}"


def test_core_states_the_verification_invariant():
    core = (PROMPT_DIR / "CORE.md").read_text(encoding="utf-8")
    assert "read back" in core
    assert "fl_project_snapshot" in core


def test_bridge_documents_the_diagnostics_tool():
    bridge = (PROMPT_DIR / "BRIDGE.md").read_text(encoding="utf-8")
    assert "fl_diagnostics" in bridge
    assert "fl_connection_status" in bridge


def test_qc_defines_gates_with_pass_and_fail():
    qc = (PROMPT_DIR / "QC.md").read_text(encoding="utf-8")
    assert "PASS" in qc and "FAIL" in qc
    # At least half a dozen numbered gate groups.
    assert len(re.findall(r"^### G\d", qc, re.MULTILINE)) >= 6


def test_the_pack_bans_vague_adjectives():
    core = (PROMPT_DIR / "CORE.md").read_text(encoding="utf-8")
    for word in ("professional", "radio-ready", "high quality"):
        assert word in core, f"CORE.md should call out {word!r} as a word that does nothing"


def test_genres_cover_at_least_ten_styles():
    genres = (PROMPT_DIR / "GENRES.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", genres, re.MULTILINE)
    styles = [h for h in headings if not h.startswith(("Cross-genre", "Recipe"))]
    assert len(styles) >= 10, f"only {len(styles)} style specs found: {styles}"


def test_genre_specs_contain_numbers():
    """A style spec without numbers is not a spec."""
    genres = (PROMPT_DIR / "GENRES.md").read_text(encoding="utf-8")
    blocks = re.split(r"^## ", genres, flags=re.MULTILINE)[1:]
    for block in blocks:
        if block.startswith("Cross-genre"):
            continue
        assert re.search(r"\d", block), f"style spec without numbers: {block.splitlines()[0]}"
