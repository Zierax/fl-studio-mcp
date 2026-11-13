"""Shared pytest fixtures for the FL Studio MCP test suite.

The FL Studio controller script normally runs inside FL Studio's embedded
Python interpreter.  To test it we load it in a normal interpreter with the
FL API modules replaced by stubs, and -- crucially -- with the standard
library modules that FL Studio does not ship blocked.  That reproduces the
environment of FL Studio 21, where ``import json`` fails.
"""

from __future__ import annotations

import builtins
import importlib
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEVICE_SCRIPT = REPO_ROOT / "fl_controller" / "device_FLStudioMCP.py"

#: Standard library modules that FL Studio's stripped interpreter does not
#: ship.  Importing any of them inside FL Studio raises ModuleNotFoundError.
FL_UNAVAILABLE_MODULES = (
    "json",
    "os",
    "pathlib",
    "importlib",
    "importlib.util",
    "shutil",
    "subprocess",
    "dataclasses",
    "collections",
    "functools",
    "itertools",
    "textwrap",
    "csv",
    "socket",
    "urllib",
    "urllib.parse",
)

#: Names of the FL Studio API modules the controller script talks to.
FL_API_MODULES = (
    "channels",
    "mixer",
    "transport",
    "plugins",
    "general",
    "ui",
    "playlist",
    "patterns",
    "arrangement",
    "midi",
    "device",
)


class StubModule(types.ModuleType):
    """A stand-in for an FL Studio API module.

    Any attribute access returns a callable stub; names that look like
    constants (``REC_UpdateValue``, ``FPT_Play``) return integers so that
    bitwise operations keep working.
    """

    def __init__(self, name: str, **attributes: object) -> None:
        super().__init__(name)
        for key, value in attributes.items():
            setattr(self, key, value)

    def __getattr__(self, name: str):  # pragma: no cover - exercised indirectly
        if name.startswith("__"):
            raise AttributeError(name)
        if name.isupper():
            return 0
        calls: list[tuple] = []

        def _stub(*args, **kwargs):
            calls.append((args, kwargs))
            return 0

        _stub.calls = calls  # type: ignore[attr-defined]
        return _stub


def _make_stub_modules() -> dict[str, types.ModuleType]:
    """Create a fresh set of FL API stub modules."""
    stubs: dict[str, types.ModuleType] = {}
    for name in FL_API_MODULES:
        module = StubModule(name)
        if name == "general":
            module.getVersion = lambda: 40  # type: ignore[attr-defined]
        if name == "mixer":
            module.getCurrentTempo = lambda *a: 140000  # type: ignore[attr-defined]
        stubs[name] = module
    return stubs


def install_stubs() -> dict[str, types.ModuleType]:
    """Install the FL API stub modules into ``sys.modules``.

    The returned mapping can be handed to :func:`restore_modules` to undo the
    change.
    """
    stubs = _make_stub_modules()
    saved = {name: sys.modules.get(name) for name in FL_API_MODULES}
    sys.modules.update(stubs)
    return {"_saved": saved}  # type: ignore[return-value]


def restore_modules(state) -> None:
    """Undo :func:`install_stubs`."""
    saved = state["_saved"]
    for name, previous in saved.items():
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


class BlockedImports:
    """Context manager that hides modules from ``import`` statements."""

    def __init__(self, blocked: tuple[str, ...]) -> None:
        self.blocked = blocked
        self._original_import = builtins.__import__
        self._saved: dict[str, types.ModuleType | None] = {}

    def _fake_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".")[0]
        if root in self.blocked:
            raise ModuleNotFoundError(f"No module named {root!r}", name=name)
        return self._original_import(name, globals, locals, fromlist, level)

    def __enter__(self) -> "BlockedImports":
        for name in self.blocked:
            self._saved[name] = sys.modules.get(name)
            sys.modules.pop(name, None)
        builtins.__import__ = self._fake_import
        return self

    def __exit__(self, *exc_info) -> None:
        builtins.__import__ = self._original_import
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def load_device_script(blocked: tuple[str, ...] = FL_UNAVAILABLE_MODULES):
    """Execute the controller script with stubbed FL modules.

    The standard library modules FL Studio does not ship are blocked for the
    duration of the import, so the script has to work without them.
    """
    source = DEVICE_SCRIPT.read_text(encoding="utf-8")
    stubs = _make_stub_modules()

    saved_modules = {name: sys.modules.get(name) for name in FL_API_MODULES}
    sys.modules.update(stubs)
    try:
        with BlockedImports(blocked):
            module = types.ModuleType("device_FLStudioMCP")
            module.__file__ = str(DEVICE_SCRIPT)
            exec(compile(source, str(DEVICE_SCRIPT), "exec"), module.__dict__)
    finally:
        for name, previous in saved_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return module


@pytest.fixture(scope="session")
def device_module():
    """The controller script, loaded with stubbed FL modules."""
    return load_device_script()


@pytest.fixture
def fl_stubs():
    """Install the FL API stub modules for the duration of a test."""
    state = install_stubs()
    try:
        yield state
    finally:
        restore_modules(state)


@pytest.fixture
def stripped_interpreter():
    """Hide the standard library modules FL Studio does not ship."""
    with BlockedImports(FL_UNAVAILABLE_MODULES) as blocker:
        yield blocker


@pytest.fixture
def repo_root() -> Path:
    """Root directory of the repository."""
    return REPO_ROOT


@pytest.fixture
def src_on_path():
    """Make ``fl_studio_mcp`` importable without installing the package."""
    src = str(REPO_ROOT / "src")
    added = False
    if src not in sys.path:
        sys.path.insert(0, src)
        added = True
    try:
        yield src
    finally:
        if added and src in sys.path:
            sys.path.remove(src)


@pytest.fixture
def fresh_import(src_on_path):
    """Re-import the server side modules so env changes take effect."""
    for name in list(sys.modules):
        if name.startswith("fl_studio_mcp"):
            del sys.modules[name]
    importlib.invalidate_caches()
    yield
