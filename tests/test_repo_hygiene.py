"""Repository hygiene tests.

These guard against the kind of silent corruption that is easy to miss in a
diff: NUL bytes smuggled into a text file, broken shell scripts and stray
merge markers.
"""

from __future__ import annotations

import subprocess

import pytest

from tests.conftest import REPO_ROOT

TRACKED_FILES = subprocess.run(
    ["git", "ls-files"], capture_output=True, text=True, cwd=str(REPO_ROOT), check=True
).stdout.split()

TEXT_SUFFIXES = {".py", ".sh", ".ps1", ".md", ".toml", ".json", ".txt", ".pyscript", ".cfg", ".yml", ".yaml"}
SHELL_SCRIPTS = [f for f in TRACKED_FILES if f.endswith((".sh", ".bash"))]


@pytest.mark.parametrize("filename", TRACKED_FILES, ids=lambda f: f)
def test_no_nul_bytes_in_text_files(filename):
    """A NUL byte in a text file silently breaks the file.

    ``install.ps1`` shipped with every ``-`` replaced by ``\\x00``, which
    made the Windows installer unparseable.  This test makes sure that can
    never happen again.
    """
    path = REPO_ROOT / filename
    if not path.is_file():
        pytest.skip(f"{filename} is not present in the working tree")

    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES or not path.suffix:
        assert b"\x00" not in data, f"{filename} contains NUL bytes"


@pytest.mark.parametrize("filename", TRACKED_FILES, ids=lambda f: f)
def test_no_conflict_markers(filename):
    path = REPO_ROOT / filename
    if not path.is_file():
        pytest.skip(f"{filename} is not present in the working tree")
    data = path.read_bytes()
    if b"\x00" in data:
        pytest.skip(f"{filename} is binary")
    for marker in (b"<<<<<<< ", b">>>>>>> "):
        assert marker not in data, f"{filename} contains a merge conflict marker"


@pytest.mark.parametrize("filename", SHELL_SCRIPTS, ids=lambda f: f)
def test_shell_scripts_have_lf_endings(filename):
    """A CRLF shell script dies with "bad interpreter: /bin/bash^M"."""
    path = REPO_ROOT / filename
    if not path.is_file():
        pytest.skip(f"{filename} is not present in the working tree")
    data = path.read_bytes()
    assert b"\r\n" not in data, f"{filename} has CRLF line endings"


@pytest.mark.parametrize("filename", TRACKED_FILES, ids=lambda f: f)
def test_files_end_with_a_newline(filename):
    path = REPO_ROOT / filename
    if not path.is_file():
        pytest.skip(f"{filename} is not present in the working tree")
    data = path.read_bytes()
    if not data or b"\x00" in data:
        pytest.skip(f"{filename} is binary or empty")
    assert data.endswith(b"\n"), f"{filename} does not end with a newline"
