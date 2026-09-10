# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_lua_inspector.py
"""
🔍 Inspetor Semântico Avançado de Símbolos, Pipelines, Contratos e Volatilidade de Código em Lua.
Fase 2: Reconciliação Cross-File, Consciência de UX Canônica (Notepad++) e Consolidação de UI.
"""
from __future__ import annotations
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple

CANONICAL_KEYMAP_MAPPINGS: Dict[str, Tuple[str, str]] = {
    "ctrl+alt+/": ("f1", "doxoade:show-shortcuts-cheat-sheet"),
    "ctrl+alt+shift+c": ("ctrl+alt+c", "doxoade:copy-path-menu"),
    "ctrl+alt+h": ("ctrl+h", "find-replace:replace"),
    "ctrl+alt+left": ("ctrl+shift+tab", "root:switch-to-previous-tab"),
    "ctrl+alt+right": ("ctrl+tab", "root:switch-to-next-tab"),
}

COMMAND_ALIASES: Dict[str, str] = {
    "doxoade:interactive-find-replace": "find-replace:replace",
    "doxoade:tab-copy-full-path": "doxoade:copy-path-menu",
    "root:switch-to-left": "root:switch-to-previous-tab",
    "root:switch-to-right": "root:switch-to-next-tab",
}


@dataclass
class RegretFinding:
    """Achado de regressão funcional, segurança, volatilidade ou UX."""
    category: str
    identifier: str
    severity: str  # critical, high, medium, low, info
    old_line_approx: int
    snippet_lost: str
    impact_description: str
    mitigation_hint: str
    mutation_pct: float = 0.0


@dataclass
class LuaMethodBody:
    signature: str
    full_code: str
    called_identifiers: Set[str] = field(default_factory=set)
    contains_pcall: bool = False
    contains_yield: bool = False
    image_pipeline_steps: List[str] = field(default_factory=list)
    contract_tag: Optional[str] = None
    origin_file: str = ""


@dataclass
class LuaCapabilityInventory:
    commands: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    keymaps: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    methods: Dict[str, LuaMethodBody] = field(default_factory=dict)
    contracts: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    constants: Dict[str, Any] = field(default_factory=dict)
    draw_shields: List[str] = field(default_factory=list)
    all_pipeline_steps: Dict[str, str] = field(default_factory=dict)
    ui_buttons: Dict[str, str] = field(default_factory=dict)
    ux_defaults: Dict[str, Any] = field(default_factory=dict)


class RegretLuaInspector:
    """Extrai inventários profundos e calcula perdas, relocações, volatilidade e invariantes de UX."""

    RE_COMMAND_ADD = re.compile(r'\[["\']([^"\']+)["\']\]\s*=\s*function\s*\((.*?)\)', re.MULTILINE)
    RE_KEYMAP_ADD = re.compile(r'\[["\']([^"\']+)["\']\]\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
    RE_CONTRACT_TAG = re.compile(r'--\s*@(?:contract|qa|regression)\s*:\s*([A-Za-z0-9_\-]+)', re.IGNORECASE)
    RE_UI_BUTTON = re.compile(r'\{\s*id\s*=\s*["\']([^"\']+)["\']\s*,\s*label\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
    RE_CRITICAL_PIPELINE_KEYWORDS = [
        "paste_clipboard_image",
        "load_cas_image",
        "extract_dox_image_info",
        "extract_dox_image_info_from_line",
        "get_line_extra_height",
        "get_line_screen_position",
        "system.set_clipboard",
        "system.get_file_info",
        "CARD_HEIGHT",
        "image_systems",
        "coroutine.yield",
    ]

    @classmethod
    def _extract_methods_with_bodies(cls, source_code: str, file_name: str = "") -> Dict[str, LuaMethodBody]:
        methods: Dict[str, LuaMethodBody] = {}
        lines = source_code.splitlines()
        i = 0
        current_contract = None

        while i < len(lines):
            line = lines[i]
            tag_match = cls.RE_CONTRACT_TAG.search(line)
            if tag_match:
                current_contract = tag_match.group(1).upper()
                i += 1
                continue

            m_match = re.search(
                r'(?:function\s+([A-Za-z0-9_]+[:.][A-Za-z0-9_]+)\s*\(|'
                r'([A-Za-z0-9_]+[:.][A-Za-z0-9_]+)\s*=\s*function\s*\()',
                line
            )
            if m_match:
                sig = m_match.group(1) or m_match.group(2)
                if not sig:
                    i += 1
                    continue
                body_lines = [line]
                i += 1
                open_blocks = 1
                while i < len(lines) and open_blocks > 0:
                    b_line = lines[i]
                    body_lines.append(b_line)
                    clean_b = re.sub(r'--.*$', '', b_line)
                    clean_b = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '', clean_b)
                    # Cláusula 'elseif ... then' compartilha o 'end' do 'if' e não abre novo bloco
                    clean_b = re.sub(r'\belseif\b.*?\bthen\b', '', clean_b)
                    opens = len(re.findall(r'\b(?:function|then|do|repeat)\b', clean_b))
                    closes = len(re.findall(r'\b(?:end|until)\b', clean_b))
                    open_blocks += (opens - closes)
                    i += 1

                full_body = "\n".join(body_lines)
                calls = set(re.findall(r'([A-Za-z0-9_]+(?::[A-Za-z0-9_]+)?)\s*\(', full_body))
                img_steps = [kw for kw in cls.RE_CRITICAL_PIPELINE_KEYWORDS if kw in full_body]

                methods[sig] = LuaMethodBody(
                    signature=sig,
                    full_code=full_body,
                    called_identifiers=calls,
                    contains_pcall="pcall" in full_body or "xpcall" in full_body,
                    contains_yield="coroutine.yield" in full_body,
                    image_pipeline_steps=img_steps,
                    contract_tag=current_contract,
                    origin_file=file_name,
                )
                current_contract = None
                continue
            i += 1

        return methods

    @classmethod
    def extract_inventory(cls, source_code: str, file_name: str = "") -> LuaCapabilityInventory:
        inventory = LuaCapabilityInventory()
        if not source_code:
            return inventory

        for m in cls.RE_COMMAND_ADD.finditer(source_code):
            inventory.commands[m.group(1)] = (m.group(0), file_name)

        for m in cls.RE_KEYMAP_ADD.finditer(source_code):
            inventory.keymaps[m.group(1).lower()] = (m.group(2), file_name)

        inventory.methods = cls._extract_methods_with_bodies(source_code, file_name=file_name)

        for sig, body in inventory.methods.items():
            if body.contract_tag:
                inventory.contracts[body.contract_tag] = (body.full_code, file_name)

        for const_name in ["CARD_HEIGHT", "header_height", "term_font_size"]:
            m = re.search(rf'{const_name}\s*=\s*(\d+)', source_code)
            if m:
                inventory.constants[const_name] = int(m.group(1))

        for m in cls.RE_UI_BUTTON.finditer(source_code):
            inventory.ui_buttons[m.group(1)] = m.group(2)

        m_mode = re.search(r'mode_1to1\s*=\s*(true|false)', source_code)
        if m_mode:
            inventory.ux_defaults["mode_1to1"] = (m_mode.group(1) == "true")

        for line in source_code.splitlines():
            if "draw_rect_safe" in line or "draw_text_safe" in line:
                inventory.draw_shields.append(line.strip())

        for kw in cls.RE_CRITICAL_PIPELINE_KEYWORDS:
            if kw in source_code:
                inventory.all_pipeline_steps[kw] = file_name

        return inventory

    @classmethod
    def merge_inventories(cls, inventories: List[LuaCapabilityInventory]) -> LuaCapabilityInventory:
        merged = LuaCapabilityInventory()
        for inv in inventories:
            merged.commands.update(inv.commands)
            merged.keymaps.update(inv.keymaps)
            merged.methods.update(inv.methods)
            merged.contracts.update(inv.contracts)
            merged.constants.update(inv.constants)
            merged.draw_shields.extend(inv.draw_shields)
            merged.all_pipeline_steps.update(inv.all_pipeline_steps)
            merged.ui_buttons.update(inv.ui_buttons)
            merged.ux_defaults.update(inv.ux_defaults)
        return merged

    @classmethod
    def compare(
        cls,
        old_code: str,
        new_code: str,
        file_name: str = "",
        sibling_sources: Optional[Dict[str, str]] = None
    ) -> List[RegretFinding]:
        old_inv = cls.extract_inventory(old_code, file_name)
        new_inv = cls.extract_inventory(new_code, file_name)
        return cls._compute_diff(old_inv, new_inv, file_name, sibling_sources=sibling_sources)

    @classmethod
    def compare_against_siblings(cls, old_code: str, old_file_name: str, sibling_sources: Dict[str, str]) -> List[RegretFinding]:
        old_inv = cls.extract_inventory(old_code, old_file_name)
        sibling_invs = [cls.extract_inventory(code, fname) for fname, code in sibling_sources.items()]
        merged_new_inv = cls.merge_inventories(sibling_invs)
        return cls._compute_diff(old_inv, merged_new_inv, old_file_name, is_split_mode=True, sibling_sources=sibling_sources)

    @classmethod
    def _compute_diff(
        cls,
        old_inv: LuaCapabilityInventory,
        new_inv: LuaCapabilityInventory,
        file_name: str,
        is_split_mode: bool = False,
        sibling_sources: Optional[Dict[str, str]] = None
    ) -> List[RegretFinding]:
        findings: List[RegretFinding] = []

        # Monta inventário mesclado de todos os módulos irmãos
        sibling_invs: List[LuaCapabilityInventory] = []
        sibling_raw_text = ""
        if sibling_sources:
            for s_name, s_code in sibling_sources.items():
                sibling_invs.append(cls.extract_inventory(s_code, file_name=s_name))
            sibling_raw_text = "\n".join(sibling_sources.values())

        merged_siblings = cls.merge_inventories(sibling_invs)
        merged_all_new = cls.merge_inventories([new_inv, merged_siblings])

        # 1. Auditoria de Comandos
        for cmd, (snippet, orig_file) in old_inv.commands.items():
            if cmd not in new_inv.commands:
                if cmd in merged_siblings.commands:
                    dest_file = merged_siblings.commands[cmd][1]
                    findings.append(RegretFinding(
                        category="SPLIT_RELOCATED",
                        identifier=f"command[{cmd}] -> {dest_file}",
                        severity="info",
                        old_line_approx=0,
                        snippet_lost=snippet,
                        impact_description=f"O comando '{cmd}' migrou para o módulo irmão '{dest_file}'.",
                        mitigation_hint="Capacidade preservada no ecossistema."
                    ))
                else:
                    findings.append(RegretFinding(
                        category="LOST_IN_SPLIT" if is_split_mode else "COMMAND_LOST",
                        identifier=cmd,
                        severity="high",
                        old_line_approx=0,
                        snippet_lost=snippet,
                        impact_description=f"O comando '{cmd}' não foi encontrado em nenhum dos módulos ativos.",
                        mitigation_hint=f"Restaurar command.add para '{cmd}'."
                    ))

        # 2. Auditoria de Atalhos de Teclado (Keymaps com Consciência Canônica e UI)
        for key, (cmd, orig_file) in old_inv.keymaps.items():
            key_lower = key.lower()
            if key_lower not in new_inv.keymaps:
                # 2.1. Foi remapeado para outra tecla no mesmo arquivo ou irmãos?
                remapped_to = None
                for k, (c, f) in merged_all_new.keymaps.items():
                    if c == cmd:
                        remapped_to = (k, f)
                        break

                if remapped_to:
                    findings.append(RegretFinding(
                        category="KEYMAP_REASSIGNED",
                        identifier=f"{key} ➔ {remapped_to[0]}",
                        severity="info",
                        old_line_approx=0,
                        snippet_lost=f'["{key}"] = "{cmd}"',
                        impact_description=f"O atalho '{key}' para '{cmd}' foi remapeado para '{remapped_to[0]}' no módulo '{remapped_to[1]}'.",
                        mitigation_hint="Atalho atualizado."
                    ))
                    continue

                # 2.2. O atalho foi padronizado para o layout canônico do Notepad++?
                if key_lower in CANONICAL_KEYMAP_MAPPINGS:
                    canon_key, canon_cmd = CANONICAL_KEYMAP_MAPPINGS[key_lower]
                    findings.append(RegretFinding(
                        category="KEYMAP_CANONIZED",
                        identifier=f"{key} ➔ {canon_key}",
                        severity="info",
                        old_line_approx=0,
                        snippet_lost=f'["{key}"] = "{cmd}"',
                        impact_description=f"O atalho '{key}' foi padronizado para a tecla canônica '{canon_key}' ({canon_cmd}).",
                        mitigation_hint="Conforme padrão canônico Notepad++."
                    ))
                    continue

                # 2.3. O comando foi absorvido pela interface (Status Bar, Botões ou Context Menu)?
                effective_cmd = COMMAND_ALIASES.get(cmd, cmd)
                if (effective_cmd in merged_all_new.commands or
                    effective_cmd in sibling_raw_text or
                    cmd in sibling_raw_text):
                    findings.append(RegretFinding(
                        category="UX_CONSOLIDATED",
                        identifier=f"command[{cmd}]",
                        severity="info",
                        old_line_approx=0,
                        snippet_lost=f'["{key}"] = "{cmd}"',
                        impact_description=f"O atalho '{key}' foi consolidado na interface visual (menu/statusbar/painel).",
                        mitigation_hint="Capacidade absorvida pela UX."
                    ))
                    continue

                # 2.4. Perda real de atalho sem equivalente
                findings.append(RegretFinding(
                    category="LOST_IN_SPLIT" if is_split_mode else "KEYMAP_LOST",
                    identifier=key,
                    severity="high",
                    old_line_approx=0,
                    snippet_lost=f'["{key}"] = "{cmd}"',
                    impact_description=f"O atalho '{key}' não foi herdado em nenhum dos módulos novos.",
                    mitigation_hint=f"Reinserir keymap.add {{ ['{key}'] = '{cmd}' }}."
                ))

        # 3. Auditoria de Métodos e Sobrescritas (Cross-File Method Tracking)
        for sig, old_body in old_inv.methods.items():
            if not sig or not isinstance(sig, str):
                continue

            # Chave canônica alternativa (: ⬌ .)
            sig_alt = sig.replace(":", ".") if ":" in sig else sig.replace(".", ":")

            target_method = new_inv.methods.get(sig) or new_inv.methods.get(sig_alt)

            if not target_method:
                # Verifica nos módulos irmãos
                sibling_match = merged_siblings.methods.get(sig) or merged_siblings.methods.get(sig_alt)
                if sibling_match:
                    dest_file = sibling_match.origin_file
                    findings.append(RegretFinding(
                        category="METHOD_RELOCATED_CROSS_FILE",
                        identifier=f"{sig} -> {dest_file}",
                        severity="info",
                        old_line_approx=0,
                        snippet_lost=old_body.full_code[:180] if old_body.full_code else "",
                        impact_description=f"O método/hook '{sig}' foi relocado e continua ativo no módulo irmão '{dest_file}'.",
                        mitigation_hint="Hook ativo em módulo irmão."
                    ))
                    continue

                findings.append(RegretFinding(
                    category="LOST_IN_SPLIT" if is_split_mode else "METHOD_DROPPED",
                    identifier=sig,
                    severity="high",
                    old_line_approx=0,
                    snippet_lost=old_body.full_code[:250] if old_body.full_code else "",
                    impact_description=f"O método '{sig}' foi totalmente extirpado.",
                    mitigation_hint=f"Verificar se a lógica de {sig} ainda é necessária."
                ))
            else:
                new_body = target_method
                s = difflib.SequenceMatcher(None, old_body.full_code, new_body.full_code)
                mutation_pct = round((1.0 - s.ratio()) * 100, 1)

                if mutation_pct >= 60.0:
                    findings.append(RegretFinding(
                        category="VOLATILE_MUTATION",
                        identifier=f"{sig} ({mutation_pct}% mutado)",
                        severity="medium",
                        old_line_approx=0,
                        snippet_lost=new_body.full_code[:200],
                        impact_description=f"Reescrita radical ({mutation_pct}% mutado). Considerada INSTÁVEL.",
                        mitigation_hint=f"Homologar o comportamento de {sig} em runtime.",
                        mutation_pct=mutation_pct,
                    ))
                elif mutation_pct >= 20.0:
                    findings.append(RegretFinding(
                        category="MODIFIED_MODERATE",
                        identifier=f"{sig} ({mutation_pct}% mutado)",
                        severity="low",
                        old_line_approx=0,
                        snippet_lost="",
                        impact_description=f"Alteração moderada de fluxo/lógica ({mutation_pct}% mutado).",
                        mitigation_hint=f"Revisar alterações internas em {sig}.",
                        mutation_pct=mutation_pct,
                    ))
                elif mutation_pct > 0.0:
                    findings.append(RegretFinding(
                        category="MODIFIED_LIGHT",
                        identifier=f"{sig} ({mutation_pct}% mutado)",
                        severity="info",
                        old_line_approx=0,
                        snippet_lost="",
                        impact_description=f"Refatoração leve preservada ({mutation_pct}% mutado).",
                        mitigation_hint="Nenhuma ação necessária.",
                        mutation_pct=mutation_pct,
                    ))

        return findings
