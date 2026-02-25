from pathlib import Path
import importlib
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "doxoade" in sys.modules and not getattr(sys.modules["doxoade"], "__file__", None):
    del sys.modules["doxoade"]

runtime = importlib.import_module("doxoade.tools.vulcan.runtime")


class _FakeModule:
    def run_vulcan_optimized(self):
        return "ok"


def test_find_vulcan_project_root(tmp_path: Path):
    project = tmp_path / "proj"
    target = project / ".doxoade" / "vulcan" / "bin"
    target.mkdir(parents=True)

    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)

    root = runtime.find_vulcan_project_root(nested)
    assert root == project


def test_activate_vulcan_injects_optimized_symbol(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    (project / ".doxoade" / "vulcan" / "bin").mkdir(parents=True)

    monkeypatch.setattr(runtime, "load_vulcan_binary", lambda module_name, project_root: _FakeModule())

    globs = {}
    activated = runtime.activate_vulcan(globs, str(project / "run.py"), project_root=project)

    assert activated is True
    assert "run" in globs
    assert globs["run"]() == "ok"


def test_activate_vulcan_returns_false_without_binary(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    (project / ".doxoade" / "vulcan" / "bin").mkdir(parents=True)

    monkeypatch.setattr(runtime, "load_vulcan_binary", lambda module_name, project_root: None)

    activated = runtime.activate_vulcan({}, str(project / "run.py"), project_root=project)
    assert activated is False
