# doxoade/doxoade/_version.py
__version__ = '270.0'
__version__ = ''

def _update_version_file(git_root: str) -> bool:
    """Atualiza doxoade/_version.py com o número total de commits."""
    from pathlib import Path
    count = _run_git_command(['rev-list', '--count', 'HEAD'], capture_output=True, silent_fail=True, cwd=git_root)
    if not count or not count.isdigit():
        return False
    
    version_file = Path(git_root) / 'doxoade' / '_version.py'
    if not version_file.exists():
        return False
    
    new_content = f"# doxoade/doxoade/_version.py\n__version__ = '{count}.0'\n"
    try:
        version_file.write_text(new_content, encoding='utf-8')
        return True
    except Exception:
        return False