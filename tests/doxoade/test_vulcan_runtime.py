from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from doxoade.tools.vulcan import runtime


def test_activate_vulcan_uses_parent_name_for_main(monkeypatch, tmp_path):
    root = tmp_path
    (root / ".doxoade" / "vulcan" / "bin").mkdir(parents=True)

    module = ModuleType("v_engine")
    module.main_vulcan_optimized = lambda: "ok"

    monkeypatch.setattr(runtime, "find_vulcan_project_root", lambda _: root)
    monkeypatch.setattr(runtime, "load_vulcan_binary", lambda module_name, _: module if module_name == "v_engine" else None)

    globs = {}
    activated = runtime.activate_vulcan(globs, str(root / "engine" / "__main__.py"))

    assert activated is True
    assert "main" in globs


def test_activate_vulcan_installs_import_finder_once(monkeypatch, tmp_path):
    root = tmp_path
    (root / ".doxoade" / "vulcan" / "bin").mkdir(parents=True)

    module = ModuleType("v_engine")
    module.run_vulcan_optimized = lambda: "ok"

    monkeypatch.setattr(runtime, "find_vulcan_project_root", lambda _: root)
    monkeypatch.setattr(runtime, "load_vulcan_binary", lambda *_: module)

    original_meta_path = list(runtime.sys.meta_path)
    try:
        runtime.activate_vulcan({}, str(root / "engine" / "__main__.py"))
        runtime.activate_vulcan({}, str(root / "engine" / "__main__.py"))

        finders = [f for f in runtime.sys.meta_path if isinstance(f, runtime.VulcanBinaryFinder) and f.project_root == root.resolve()]
        assert len(finders) == 1
    finally:
        runtime.sys.meta_path[:] = original_meta_path


def test_finder_resolves_joined_module_name(monkeypatch, tmp_path):
    root = tmp_path
    bin_dir = root / ".doxoade" / "vulcan" / "bin"
    bin_dir.mkdir(parents=True)
    candidate = bin_dir / f"v_engine_cli{runtime._binary_ext()}"
    candidate.write_bytes(b"binary")

    calls: list[tuple[str, str]] = []

    def fake_spec(fullname: str, path: str):
        calls.append((fullname, path))
        return SimpleNamespace(loader=object())

    monkeypatch.setattr(runtime.importlib.util, "spec_from_file_location", fake_spec)

    finder = runtime.VulcanBinaryFinder(root)
    spec = finder.find_spec("engine.cli")

    assert spec is not None
    assert calls == [("engine.cli", str(candidate))]
