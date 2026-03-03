from pathlib import Path


def _load_bootstrap_source() -> str:
    src = Path('doxoade/commands/vulcan_cmd.py').read_text(encoding='utf-8')
    return src


def test_bootstrap_registers_runtime_alias_module():
    src = _load_bootstrap_source()
    assert '_doxo_sys.modules["_doxoade_vulcan_runtime"] = _doxo_mod' in src


def test_bootstrap_registers_embedded_alias_module():
    src = _load_bootstrap_source()
    assert '_doxo_sys.modules["_doxoade_vulcan_embedded"] = _doxo_mod2' in src
