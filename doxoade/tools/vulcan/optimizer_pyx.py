# doxoade/doxoade/tools/vulcan/optimizer_pyx.py
from pathlib import Path

def optimize_pyx_file(pyx_path: Path) -> Path:
    """
    Otimiza um .pyx antes da compilação.
    Retorna o Path do arquivo otimizado (pode ser o mesmo).
    NUNCA levanta exceção.
    """
    try:
        text = pyx_path.read_text(encoding='utf-8')
        lines = []
        last_blank = False
        for line in text.splitlines():
            if not line.strip():
                if last_blank:
                    continue
                last_blank = True
            else:
                last_blank = False
            lines.append(line.rstrip())
        optimized = '\n'.join(lines) + '\n'
        pyx_path.write_text(optimized, encoding='utf-8')
        return pyx_path
    except Exception:
        return pyx_path