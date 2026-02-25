from pathlib import Path
import importlib
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "doxoade" in sys.modules and not getattr(sys.modules["doxoade"], "__file__", None):
    del sys.modules["doxoade"]

module_generator = importlib.import_module("doxoade.tools.vulcan.module_generator")


def test_generate_local_vulcan_module_creates_runtime(tmp_path: Path):
    created, runtime_path = module_generator.generate_local_vulcan_module(tmp_path)

    assert created is True
    assert runtime_path.exists()
    assert "activate_vulcan" in runtime_path.read_text(encoding="utf-8")


def test_generate_local_vulcan_module_respects_force(tmp_path: Path):
    created, runtime_path = module_generator.generate_local_vulcan_module(tmp_path)
    assert created is True

    runtime_path.write_text("OLD", encoding="utf-8")

    created_second, _ = module_generator.generate_local_vulcan_module(tmp_path, force=False)
    assert created_second is False
    assert runtime_path.read_text(encoding="utf-8") == "OLD"

    created_third, _ = module_generator.generate_local_vulcan_module(tmp_path, force=True)
    assert created_third is True
    assert "OLD" not in runtime_path.read_text(encoding="utf-8")
