#!/usr/bin/env python3
# doxoade/commands/termux_systems/termux_config.py

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict

HOME = Path.home()
STATE_FILE = HOME / ".doxoade_termux_config_state.json"
BACKUP_DIR = HOME / ".doxoade" / "backups" / "termux_config"

NANO_BEGIN = "## >>> doxoade-termux-config"
NANO_END = "## <<< doxoade-termux-config"

TERMUX_BEGIN = "# >>> doxoade-termux-config"
TERMUX_END = "# <<< doxoade-termux-config"

TERMUX_COLOR_BODY = "\n".join([
    "background=#000000",
    "foreground=#ffffff",
    "cursor=#26bc5f",
    "color2=#26bc5f",
])

MICRO_THEME_CONTENT = 'color-link cursor-line ",#e05a00"\n'
MICRO_SETTINGS_TARGETS = {
    "colorscheme": "meutema",
    "cursorline": True,
    "truecolor": True,
    "autoindent": False,
    "smartpaste": False,
}
MICRO_SETTINGS_PATH = HOME / ".config" / "micro" / "settings.json"
MICRO_THEME_PATH = HOME / ".config" / "micro" / "colorschemes" / "meutema.micro"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    ensure_parent(STATE_FILE)
    STATE_FILE.write_text(
        json.dumps(state, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )


def backup_path_for(path: Path) -> Path:
    rel = str(path).replace(":", "").lstrip("/\\").replace("\\", "/")
    return BACKUP_DIR / f"{rel}.bak"


def backup_file(path: Path) -> None:
    if not path.exists():
        return
    backup = backup_path_for(path)
    ensure_parent(backup)
    if not backup.exists():
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


def apply_nanorc() -> None:
    path = HOME / ".nanorc"
    text = read_text(path)
    new_text = replace_or_append_block(text, NANO_BEGIN, NANO_END, "set linenumbers")
    write_text(path, new_text)


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
    backup_file(MICRO_THEME_PATH)
    write_text(MICRO_THEME_PATH, MICRO_THEME_CONTENT)


def remove_micro_theme() -> None:
    restore_file(MICRO_THEME_PATH)


def apply_micro_settings() -> None:
    state = load_state()
    json_backups = state.setdefault("json_backups", {})
    key = str(MICRO_SETTINGS_PATH)
    path_state = json_backups.setdefault(key, {})

    data: Dict[str, Any] = {}
    if MICRO_SETTINGS_PATH.exists():
        try:
            data = json.loads(MICRO_SETTINGS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    for setting_key, desired in MICRO_SETTINGS_TARGETS.items():
        if setting_key not in path_state:
            path_state[setting_key] = data.get(setting_key, "__MISSING__")
        data[setting_key] = desired

    ensure_parent(MICRO_SETTINGS_PATH)
    MICRO_SETTINGS_PATH.write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    save_state(state)


def remove_micro_settings() -> None:
    state = load_state()
    json_backups = state.get("json_backups", {})
    key = str(MICRO_SETTINGS_PATH)
    path_state = json_backups.get(key, {})

    if not MICRO_SETTINGS_PATH.exists() and not path_state:
        return

    data: Dict[str, Any] = {}
    if MICRO_SETTINGS_PATH.exists():
        try:
            data = json.loads(MICRO_SETTINGS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    for setting_key, previous in path_state.items():
        if previous == "__MISSING__":
            data.pop(setting_key, None)
        else:
            data[setting_key] = previous

    ensure_parent(MICRO_SETTINGS_PATH)
    MICRO_SETTINGS_PATH.write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    if key in json_backups:
        del json_backups[key]
    if not json_backups:
        state.pop("json_backups", None)
    save_state(state)


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
    reload_termux_settings()
    print("✔️  Configuração aplicada/atualizada com sucesso.")


def remove() -> None:
    remove_nanorc()
    remove_termux_colors()
    remove_micro_theme()
    remove_micro_settings()
    reload_termux_settings()
    print("✔️  Configuração removida e restaurada com sucesso.")


def main(mode: str = "apply") -> None:
    if mode == "remove":
        remove()
    else:
        apply()


if __name__ == "__main__":
    main()