import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.lib_forge import LibForge


def test_is_safe_requirement_accepts_simple_and_pinned_names():
    assert LibForge._is_safe_requirement("numpy")
    assert LibForge._is_safe_requirement("orjson==3.10.7")
    assert LibForge._is_safe_requirement("pydantic>=2.8.0")


def test_is_safe_requirement_rejects_shell_like_inputs():
    assert not LibForge._is_safe_requirement("")
    assert not LibForge._is_safe_requirement("numpy; rm -rf /")
    assert not LibForge._is_safe_requirement("../evil")
    assert not LibForge._is_safe_requirement("package with spaces")
