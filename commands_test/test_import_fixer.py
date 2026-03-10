from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.import_fixer import fix_project_imports


def test_fix_imports_rewrites_from_import_for_moved_module(tmp_path):
    root = tmp_path
    (root / "x" / "m").mkdir(parents=True)
    (root / "x" / "__init__.py").write_text("")
    (root / "x" / "m" / "__init__.py").write_text("")
    (root / "x" / "m" / "z.py").write_text("def a():\n    return 1\n")

    app = root / "app.py"
    app.write_text("from x.y.z import a, b\nprint(a)\n", encoding="utf-8")

    result = fix_project_imports(root)

    assert result.imports_changed == 1
    assert "from x.m.z import a, b" in app.read_text(encoding="utf-8")


def test_fix_imports_keeps_existing_valid_import(tmp_path):
    root = tmp_path
    (root / "x" / "m").mkdir(parents=True)
    (root / "x" / "__init__.py").write_text("")
    (root / "x" / "m" / "__init__.py").write_text("")
    (root / "x" / "m" / "z.py").write_text("def a():\n    return 1\n")

    app = root / "app.py"
    original = "from x.m.z import a\n"
    app.write_text(original, encoding="utf-8")

    result = fix_project_imports(root)

    assert result.imports_changed == 0
    assert app.read_text(encoding="utf-8") == original
