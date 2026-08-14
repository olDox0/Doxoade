# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/bg_rotator.py
"""SOFTCLUB ROTATOR — rotação sequencial de fundos (wallpaper/ + extras dropados).
Doutrina: thread única daemon (sem loop concorrente p/ UI); índice implícito
no bg_path persistido; playlist = wallpaper/ (ordenado por nome) + extras.
"""
import threading
import time
from pathlib import Path

_EXT = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}
_thread = None
_stop = threading.Event()

def wallpaper_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / 'wallpaper'
    d.mkdir(parents=True, exist_ok=True)
    readme = d / 'README.md'
    if not readme.exists():
        readme.write_text(
            '# wallpaper/\n\nImagens aqui entram na rotação automática '
            '(padrão: 10 min, tecla `b` avança agora).\n'
            'Formatos: png jpg jpeg bmp gif webp (subpastas ok).\n',
            encoding='utf-8')
    return d

def scan_wallpapers() -> list:
    d = wallpaper_dir()
    return sorted((p for p in d.rglob('*')
                   if p.is_file() and p.suffix.lower() in _EXT),
                  key=lambda p: p.name.lower())

def playlist(extras) -> list:
    """wallpaper/ + extras (dropados fora da pasta), sem duplicatas."""
    seen, out = set(), []
    for p in scan_wallpapers() + [Path(x) for x in (extras or [])]:
        try:
            k = str(p.resolve())
        except Exception:
            continue
        if p.exists() and k not in seen:
            seen.add(k)
            out.append(p)
    return out

def start(on_next, get_state, interval_min=10):
    """get_state() -> (bg_path_atual, extras); on_next(path) aplica c/ fade."""
    global _thread
    if _thread is not None:
        return
    _stop.clear()

    def loop():
        last = time.time()
        while not _stop.is_set():
            time.sleep(2.0)
            now = time.time()
            if now - last >= max(1, interval_min) * 60:
                last = now
                try:
                    cur, extras = get_state()
                    pl = playlist(extras)
                    if len(pl) < 2:
                        continue
                    idx = 0
                    if cur:
                        for i, p in enumerate(pl):
                            if str(p) == str(cur):
                                idx = (i + 1) % len(pl)
                                break
                    on_next(pl[idx])
                except Exception:
                    pass
    _thread = threading.Thread(target=loop, daemon=True)
    _thread.start()