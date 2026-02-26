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
    monkeypatch.setattr(runtime, "_is_binary_valid_for_host", lambda _: True)
    monkeypatch.setattr(runtime, "_is_binary_fresh", lambda *_: True)

    finder = runtime.VulcanBinaryFinder(root)
    spec = finder.find_spec("engine.cli")

    assert spec is not None
    assert calls == [("engine.cli", str(candidate))]


def test_activate_vulcan_skips_stale_binary(monkeypatch, tmp_path):
    root = tmp_path
    bin_dir = root / ".doxoade" / "vulcan" / "bin"
    bin_dir.mkdir(parents=True)
    source = root / "engine" / "__main__.py"
    source.parent.mkdir(parents=True)
    source.write_text("print('x')\n", encoding="utf-8")

    candidate = bin_dir / f"v_engine{runtime._binary_ext()}"
    candidate.write_bytes(b"MZ" + b"0" * 5000)

    now = source.stat().st_mtime
    candidate_ts = now - 60
    source_ts = now + 60
    import os
    os.utime(candidate, (candidate_ts, candidate_ts))
    os.utime(source, (source_ts, source_ts))

    monkeypatch.setattr(runtime, "find_vulcan_project_root", lambda _: root)

    called = {"load": False}

    def fake_load(*_):
        called["load"] = True
        return None

    monkeypatch.setattr(runtime, "load_vulcan_binary", fake_load)

    assert runtime.activate_vulcan({}, str(source)) is False
    assert called["load"] is False


def test_finder_skips_invalid_binary(tmp_path):
    root = tmp_path
    bin_dir = root / ".doxoade" / "vulcan" / "bin"
    bin_dir.mkdir(parents=True)
    bad = bin_dir / f"v_engine_cli{runtime._binary_ext()}"
    bad.write_bytes(b"not-a-valid-binary")

    finder = runtime.VulcanBinaryFinder(root)
    spec = finder.find_spec("engine.cli")
    assert spec is None
