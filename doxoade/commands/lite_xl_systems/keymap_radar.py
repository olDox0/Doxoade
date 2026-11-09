# doxoade/commands/lite_xl_systems/keymap_radar.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set, Tuple

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths

QWERTY_BASE_KEYS = [
    # Letras
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    # Números
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    # Teclas de Função
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    # Pontuação e navegação
    "`", "-", "=", "[", "]", "\\", ";", "'", ",", ".", "/",
    "tab", "escape", "return", "enter", "backspace", "delete", "space",
    "home", "end", "pageup", "pagedown", "up", "down", "left", "right"
]

MODIFIER_COMBINATIONS = [
    "",
    "ctrl+",
    "alt+",
    "shift+",
    "ctrl+alt+",
    "ctrl+shift+",
    "alt+shift+",
    "ctrl+alt+shift+",
]

class KeymapRadar:
    @classmethod
    def normalize_chord(cls, chord: str) -> str:
        parts = [p.strip().lower() for p in chord.split("+") if p.strip()]
        if not parts:
            return ""
        key = parts[-1]
        mods = sorted(list(set(parts[:-1])))
        order = {"ctrl": 1, "alt": 2, "altgr": 3, "shift": 4}
        mods.sort(key=lambda m: order.get(m, 99))
        if mods:
            return "+".join(mods) + "+" + key
        return key

    @classmethod
    def _is_probable_key(cls, k: str) -> bool:
        k_lower = k.lower().strip()
        if "+" in k_lower or k_lower.startswith("f") or k_lower in (
            "tab", "escape", "return", "enter", "space", "backspace", "delete",
            "home", "end", "pageup", "pagedown", "up", "down", "left", "right"
        ):
            return True
        if len(k_lower) == 1 and k_lower in "abcdefghijklmnopqrstuvwxyz0123456789`-=[]\\;',./":
            return True
        return False

    @classmethod
    def get_code_snippet(cls, file_path: Path, target_line: int, radius: int = 2) -> List[Tuple[int, bool, str]]:
        if not file_path.exists():
            return []
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, target_line - radius)
        end = min(len(lines), target_line + radius)
        return [(ln, ln == target_line, lines[ln - 1]) for ln in range(start, end + 1)]

    @classmethod
    def scan_templates(cls) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]], Set[str]]:
        """
        Escaneia todos os templates .lua:
        Retorna:
          1. by_key: mapa tecla_normalizada -> lista de registros
          2. by_cmd: mapa comando -> lista de registros
          3. registered_commands: conjunto de comandos declarados via command.add
        """
        template_dir = LiteXLPaths.get_template_dir()
        templates = sorted([t for t in template_dir.glob("*.lua") if t.is_file()])
        
        by_key = defaultdict(list)
        by_cmd = defaultdict(list)
        registered_commands = set()
        
        # Padrões de extração
        pat_key_single = re.compile(r'\[\s*["\']([^"\']+)["\']\s*\]\s*=\s*["\']([^"\']+)["\']')
        pat_key_table = re.compile(r'\[\s*["\']([^"\']+)["\']\s*\]\s*=\s*\{(.*?)\}', re.DOTALL)
        pat_cmd_decl = re.compile(r'\[\s*["\']([a-zA-Z0-9_\-:]+)["\']\s*\]\s*=\s*(?:function|[_a-zA-Z0-9])')

        for tf in templates:
            raw_text = tf.read_text(encoding="utf-8", errors="replace")
            lines = raw_text.splitlines()

            # Extrai declarações de comandos
            for m in pat_cmd_decl.finditer(raw_text):
                cmd_name = m.group(1).strip()
                if ":" in cmd_name:
                    registered_commands.add(cmd_name)

            # Extrai keymaps
            for line_idx, line in enumerate(lines, 1):
                clean_line = line.strip()
                if clean_line.startswith("--"):
                    continue

                # Padrão simples: ["key"] = "cmd"
                m_single = pat_key_single.search(clean_line)
                if m_single:
                    raw_k = m_single.group(1).strip()
                    cmd = m_single.group(2).strip()
                    if cls._is_probable_key(raw_k):
                        norm_k = cls.normalize_chord(raw_k)
                        entry = {
                            "raw_key": raw_k,
                            "normalized_key": norm_k,
                            "command": cmd,
                            "template": tf.name,
                            "path": tf,
                            "line": line_idx,
                            "code": clean_line
                        }
                        by_key[norm_k].append(entry)
                        by_cmd[cmd].append(entry)

            # Padrão tabela: ["key"] = { "cmd1", "cmd2" }
            for m in pat_key_table.finditer(raw_text):
                raw_k = m.group(1).strip()
                if not cls._is_probable_key(raw_k):
                    continue
                norm_k = cls.normalize_chord(raw_k)
                line_no = raw_text[:m.start()].count("\n") + 1
                cmds = re.findall(r'["\']([a-zA-Z0-9_\-:]+)["\']', m.group(2))
                for cmd in cmds:
                    if cmd and not cmd.startswith("--") and ":" in cmd:
                        entry = {
                            "raw_key": raw_k,
                            "normalized_key": norm_k,
                            "command": cmd,
                            "template": tf.name,
                            "path": tf,
                            "line": line_no,
                            "code": lines[line_no - 1].strip() if line_no <= len(lines) else ""
                        }
                        by_key[norm_k].append(entry)
                        by_cmd[cmd].append(entry)

        return dict(by_key), dict(by_cmd), registered_commands

    @classmethod
    def find_collisions(
        cls, 
        by_key: Dict[str, List[Dict[str, Any]]], 
        registered_commands: Set[str]
    ) -> List[Dict[str, Any]]:
        collisions = []
        for key, entries in by_key.items():
            unique_cmds = set(e["command"] for e in entries)
            unique_templates = set(e["template"] for e in entries)
            
            # 1. Colisão Divergente: Tecla aciona comandos diferentes
            if len(unique_cmds) > 1:
                collisions.append({
                    "type": "DIVERGENT_COLLISION",
                    "severity": "CRITICAL",
                    "key": key,
                    "commands": list(unique_cmds),
                    "templates": list(unique_templates),
                    "entries": entries,
                    "message": f"A tecla [{key}] dispara {len(unique_cmds)} comandos DIFERENTES. Isso quebra a previsibilidade de input."
                })
            # 2. Colisão Duplicada: Mesmo comando registrado em múltiplos templates para a mesma tecla
            elif len(entries) > 1 and len(unique_templates) > 1:
                collisions.append({
                    "type": "REDUNDANT_REGISTRATION",
                    "severity": "WARNING",
                    "key": key,
                    "commands": list(unique_cmds),
                    "templates": list(unique_templates),
                    "entries": entries,
                    "message": f"A tecla [{key}] está registrada redundantemente em {len(unique_templates)} templates para o mesmo comando."
                })

        return sorted(collisions, key=lambda c: (c["severity"] == "CRITICAL", len(c["entries"])), reverse=True)

    @classmethod
    def find_free_alternatives(cls, base_key: str, by_key: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Procura atalhos totalmente livres derivados da mesma tecla base."""
        free_chords = []
        clean_key = base_key.strip().lower()
        if "+" in clean_key:
            clean_key = clean_key.split("+")[-1]

        for mod in MODIFIER_COMBINATIONS:
            chord = cls.normalize_chord(f"{mod}{clean_key}")
            if chord and chord not in by_key:
                free_chords.append(chord)
        return free_chords

    @classmethod
    def generate_matrix_radar(cls, base_key: str, by_key: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        radar = []
        clean_key = base_key.strip().lower()
        if "+" in clean_key:
            clean_key = clean_key.split("+")[-1]

        for mod in MODIFIER_COMBINATIONS:
            chord = cls.normalize_chord(f"{mod}{clean_key}")
            entries = by_key.get(chord, [])
            status = "FREE"
            if len(entries) == 1:
                status = "BOUND"
            elif len(entries) > 1:
                unique_cmds = set(e["command"] for e in entries)
                status = "COLLISION" if len(unique_cmds) > 1 else "BOUND"
            
            radar.append({
                "chord": chord,
                "status": status,
                "entries": entries,
            })
        return radar
