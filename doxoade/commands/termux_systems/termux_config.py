#!/usr/bin/env python3
# doxoade/commands/termux_systems/termux_config.py

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any

HOME = Path.home()
BACKUP_DIR = HOME / ".doxoade" / "backups" / "termux_config"

NANO_BEGIN = "## >>> doxoade-termux-config"
NANO_END = "## <<< doxoade-termux-config"

TERMUX_BEGIN = "# >>> doxoade-termux-config"
TERMUX_END = "# <<< doxoade-termux-config"

TERMUX_COLOR_BODY = "\n".join([
    "background=#0a331a",
    "foreground=#ffffff",
    "cursor=#26bc5f",
    "color2=#26bc5f",
])

MICRO_SETTINGS_PATH = HOME / ".config" / "micro" / "settings.json"
MICRO_BINDINGS_PATH = HOME / ".config" / "micro" / "bindings.json"
MICRO_THEME_PATH = HOME / ".config" / "micro" / "colorschemes" / "meutema.micro"

STATE_FILE = HOME / ".doxoade_termux_config_state.json"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def backup_path_for(path: Path) -> Path:
    resolved = path.resolve(strict=False).as_posix().lstrip("/")
    safe = resolved.replace(":", "")
    return BACKUP_DIR / f"{safe}.bak"


def backup_file(path: Path) -> None:
    if not path.exists():
        return
    backup = backup_path_for(path)
    if backup.exists():
        return
    ensure_parent(backup)
    shutil.copy2(path, backup)


def restore_file(path: Path) -> None:
    backup = backup_path_for(path)
    if backup.exists():
        ensure_parent(path)
        shutil.copy2(backup, path)
        backup.unlink(missing_ok=True)
    elif path.exists():
        path.unlink()


def replace_or_append_block(content: str, begin: str, end: str, body: str) -> str:
    block = f"{begin}\n{body.rstrip()}\n{end}\n"
    pattern = rf"(?ms)^{re.escape(begin)}\n.*?^{re.escape(end)}\n?"
    if re.search(pattern, content):
        return re.sub(pattern, block, content)
    if content and not content.endswith("\n"):
        content += "\n"
    return content + block


def remove_block(content: str, begin: str, end: str) -> str:
    pattern = rf"(?ms)^{re.escape(begin)}\n.*?^{re.escape(end)}\n?"
    return re.sub(pattern, "", content)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def apply_nanorc() -> None:
    path = HOME / ".nanorc"
    body = "\n".join([
        "set linenumbers",
        "set tabsize 4",
        "set tabstospaces",
    ])
    text = read_text(path)
    text = replace_or_append_block(text, NANO_BEGIN, NANO_END, body)
    write_text(path, text)


def remove_nanorc() -> None:
    path = HOME / ".nanorc"
    if not path.exists():
        return
    text = read_text(path)
    text = remove_block(text, NANO_BEGIN, NANO_END)
    write_text(path, text)


def apply_termux_colors() -> None:
    path = HOME / ".termux" / "colors.properties"
    text = read_text(path)
    text = remove_block(text, TERMUX_BEGIN, TERMUX_END)
    text = replace_or_append_block(text, TERMUX_BEGIN, TERMUX_END, TERMUX_COLOR_BODY)
    write_text(path, text)


def remove_termux_colors() -> None:
    path = HOME / ".termux" / "colors.properties"
    if not path.exists():
        return
    text = read_text(path)
    text = remove_block(text, TERMUX_BEGIN, TERMUX_END)
    write_text(path, text)


def apply_micro_theme() -> None:
    # Não criamos tema custom agora, porque isso estava quebrando a coloração do código.
    # O Micro já possui colorscheme default embutido.
    if MICRO_THEME_PATH.exists():
        restore_file(MICRO_THEME_PATH)


def remove_micro_theme() -> None:
    restore_file(MICRO_THEME_PATH)


def apply_micro_settings() -> None:
    backup_file(MICRO_SETTINGS_PATH)

    settings = load_json(MICRO_SETTINGS_PATH)
    settings.update({
        "colorscheme": "default",
        "syntax": True,
        "cursorline": True,
        "truecolor": "auto",
        "autoindent": False,
        "smartpaste": False,
        "softwrap": False,
        "wordwrap": False,
        "smartindent": False,
        "tabstospaces": True,
        "tabsize": 4,
        "diffgutter": True,
        "savehistory": True,
        "ruler": True,
        "relativeruler": False,
        "ftoptions": False,
    })

    save_json(MICRO_SETTINGS_PATH, settings)

def remove_micro_settings() -> None:
    restore_file(MICRO_SETTINGS_PATH)


def apply_micro_bindings() -> None:
    backup_file(MICRO_BINDINGS_PATH)

    bindings = load_json(MICRO_BINDINGS_PATH)
    bindings.update({
        "Alt-s": "HSplit",
        "Alt-v": "VSplit",
        "Ctrl-w": "NextSplit",
        "Alt-w": "NextSplit",
        "Backtab": "OutdentSelection|OutdentLine",
        "Ctrl-z": "Undo",
        "Ctrl-y": "Redo",
        "Alt-d": "command:diff",
    })
    save_json(MICRO_BINDINGS_PATH, bindings)


def remove_micro_bindings() -> None:
    restore_file(MICRO_BINDINGS_PATH)


def reload_termux_settings() -> None:
    try:
        from doxoade.tools.exec_safe import run_safe
    except Exception:
        return
    run_safe("termux-reload-settings")


def apply() -> None:
    apply_nanorc()
    apply_termux_colors()
    apply_micro_theme()
    apply_micro_settings()
    apply_micro_bindings()
    reload_termux_settings()
    print("✔️  Configuração aplicada/atualizada com sucesso.")


def remove() -> None:
    remove_nanorc()
    remove_termux_colors()
    remove_micro_theme()
    remove_micro_settings()
    remove_micro_bindings()
    reload_termux_settings()
    print("✔️  Configuração removida e restaurada com sucesso.")


def reset() -> None:
    remove()

    reset_micro_full()

    for path in [STATE_FILE]:
        if path.exists():
            path.unlink()

    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)

    print("✔️  Reset TOTAL concluído.")

def reset_micro_full():
    micro_dir = HOME / ".config" / "micro"

    if micro_dir.exists():
        shutil.rmtree(micro_dir, ignore_errors=True)

    print("✔️  Micro resetado completamente.")

def main(mode: str = "apply") -> None:
    if mode == "remove":
        remove()
    elif mode == "reset":
        reset()
    else:
        apply()


if __name__ == "__main__":
    main()