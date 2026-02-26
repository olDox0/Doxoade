import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.compiler import VulcanCompiler


def test_format_verbose_build_error_contains_context():
    msg = VulcanCompiler._format_verbose_build_error(
        module_name="v_x",
        cmd=["python", "setup_tmp.py", "build_ext"],
        returncode=1,
        stdout="line1\nline2\n",
        stderr="err1\nerr2\n",
    )

    assert "Build failed for v_x (exit=1)" in msg
    assert "CMD: python setup_tmp.py build_ext" in msg
    assert "--- STDERR (tail) ---" in msg
    assert "err2" in msg
    assert "--- STDOUT (tail) ---" in msg
    assert "line2" in msg
