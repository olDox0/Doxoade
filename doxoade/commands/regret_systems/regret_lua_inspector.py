# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_lua_inspector.py
"""
🔍 Inspetor Semântico Avançado de Símbolos, Pipelines, Contratos, Orfandade e Volatilidade de Código em Lua.
Fase 3: Detecção de Funcionalidades Órfãs (Comandos sem gatilho, Atalhos mortos, Funções zumbis).
Compliance: ProDeNov 1.2.1 | PASC-6.1
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
    "doxoade:open-real-terminal": "doxoade:terminal-launch-real",
    "doxoade:terminal-launch-admin-venv": "doxoade:terminal-launch-admin",
}

@dataclass
class RegretFinding:
    """Achado de regressão funcional, segurança, volatilidade, UX ou orfandade."""
    category: str
    identifier: str
    severity: str  # "critical", "high", "medium", "low", "info"
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
    """Inventário completo de capacidades e conexões semânticas de um arquivo Lua."""
    commands: Dict[str, Tuple[str, str]] = field(default_factory=dict)         # [cmd_name] = (code, file)
    keymaps: Dict[str, Tuple[str, str]] = field(default_factory=dict)          # [key_combo] = (cmd_target, file)
    methods: Dict[str, LuaMethodBody] = field(default_factory=dict)            # [method_sig] = LuaMethodBody
    contracts: Dict[str, Tuple[str, str]] = field(default_factory=dict)        # [tag] = (code, file)
    constants: Dict[str, Any] = field(default_factory=dict)                    # [name] = val
    draw_shields: List[str] = field(default_factory=list)
    all_pipeline_steps: Dict[str, str] = field(default_factory=dict)
    ui_buttons: Dict[str, str] = field(default_factory=dict)                   # [btn_id] = btn_label
    ux_defaults: Dict[str, Any] = field(default_factory=dict)
    
    # 🧩 ETAPA 1: Novos campos para Grafo de Conectividade e Detecção de Orfandade
    called_commands: Set[str] = field(default_factory=set)                     # Comandos acionados via command.perform("...")
    local_functions: Dict[str, int] = field(default_factory=dict)              # [func_name] = line_declared
    all_identifier_calls: Set[str] = field(default_factory=set)                # Conjunto de todos os foo(...) chamados no arquivo
    ui_button_actions: Set[str] = field(default_factory=set)                   # Comandos referenciados dentro de tabelas de ação de botões

class RegretLuaInspector:
    """Extrai inventários profundos e calcula perdas, relocações, volatilidade e orfandades."""
    RE_COMMAND_ADD = re.compile(r'\[["\']([^"\']+)["\']\]\s*=\s*function\s*\((.*?)\)', re.MULTILINE)
    RE_COMMAND_PERFORM = re.compile(r'command\.perform\s*\(\s*["\']([^"\']+)["\']', re.MULTILINE)
    RE_CONTRACT_TAG = re.compile(r'--\s*@(?:contract|qa|regression)\s*:\s*([A-Za-z0-9_\-]+)', re.IGNORECASE)
    RE_UI_BUTTON = re.compile(r'\{\s*id\s*=\s*["\']([^"\']+)["\']\s*,\s*label\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
    RE_BUTTON_ACTION_PERFORM = re.compile(r'action\s*=\s*function\s*\([^)]*\)[\s\S]*?command\.perform\s*\(\s*["\']([^"\']+)["\']', re.MULTILINE)
    RE_LOCAL_FUNCTION = re.compile(r'^\s*local\s+function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', re.MULTILINE)
    RE_ANY_CALL = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', re.MULTILINE)

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

    RE_KEYMAP_BLOCK = re.compile(r"keymap\.add\s*(\{[\s\S]*?\})", re.MULTILINE)
    RE_KEYMAP_ENTRY = re.compile(r'\[\s*["\']([^"\']+)["\']\s*\]\s*=\s*["\']([^"\']+)["\']')

    @classmethod
    def extract_keymaps_safely(cls, lua_content: str) -> Dict[str, str]:
        """Extrai apenas atalhos reais declarados dentro de blocos keymap.add { ... }."""
        keymaps = {}
        for block_match in cls.RE_KEYMAP_BLOCK.finditer(lua_content):
            block_text = block_match.group(1)
            for entry in cls.RE_KEYMAP_ENTRY.finditer(block_text):
                key = entry.group(1).strip()
                action = entry.group(2).strip()
                # Blindagem: ignora caracteres de desenho de caixa Unicode (falsos positivos)
                if len(key) > 1 or key.isalnum() or key in ("+", "-", "=", "[", "]"):
                    keymaps[key.lower()] = action
        return keymaps

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
        """Extrai o inventário completo de símbolos e conexões de execução."""
        inventory = LuaCapabilityInventory()
        if not source_code:
            return inventory

        # 1. Comandos registrados via command.add
        for m in cls.RE_COMMAND_ADD.finditer(source_code):
            inventory.commands[m.group(1)] = (m.group(0), file_name)

        # 2. Atalhos seguros em keymap.add
        raw_keymaps = cls.extract_keymaps_safely(source_code)
        for k, action in raw_keymaps.items():
            inventory.keymaps[k] = (action, file_name)

        # 3. Comandos disparados ativamente via command.perform
        for m in cls.RE_COMMAND_PERFORM.finditer(source_code):
            inventory.called_commands.add(m.group(1))

        # 4. Comandos acionados por botões de UI
        for m in cls.RE_BUTTON_ACTION_PERFORM.finditer(source_code):
            inventory.ui_button_actions.add(m.group(1))

        # 5. Funções locais e suas linhas
        for m in cls.RE_LOCAL_FUNCTION.finditer(source_code):
            line_no = source_code[:m.start()].count('\n') + 1
            inventory.local_functions[m.group(1)] = line_no

        # 6. Todas as chamadas de identificadores no arquivo
        for m in cls.RE_ANY_CALL.finditer(source_code):
            inventory.all_identifier_calls.add(m.group(1))

        # 7. Métodos, constantes e metadados visuais
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
        """Funde inventários de múltiplos arquivos/templates irmãos."""
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
            # Fusão dos novos grafos
            merged.called_commands.update(inv.called_commands)
            merged.local_functions.update(inv.local_functions)
            merged.all_identifier_calls.update(inv.all_identifier_calls)
            merged.ui_button_actions.update(inv.ui_button_actions)
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

    KNOWN_LITEXL_COMMANDS: Set[str] = {
        "core:open-file", "core:new-doc", "core:restart", "core:quit",
        "doc:save", "doc:save-as", "doc:save-all", "doc:undo", "doc:redo",
        "doc:cut", "doc:copy", "doc:paste", "doc:select-all",
        "doc:delete-lines", "doc:duplicate-lines", "doc:toggle-line-comments",
        "doc:go-to-line", "doc:unindent", "doc:indent",
        "find-replace:find", "find-replace:replace", "find-replace:repeat-find",
        "find-replace:previous-find",
        "root:close", "root:switch-to-next-tab", "root:switch-to-previous-tab",
        "root:split-left", "root:split-right", "root:split-up", "root:split-down",
    }

    @classmethod
    def audit_orphans(
        cls,
        inventory: LuaCapabilityInventory,
        source_code: str,
        file_name: str = "",
        external_inventories: Optional[List[LuaCapabilityInventory]] = None
    ) -> List[RegretFinding]:
        """
        Calcula orfandade estrutural cruzando comandos registrados contra
        atalhos de teclado, botões de interface e invocações ativas.
        """
        findings: List[RegretFinding] = []
        lines = source_code.splitlines()

        # Agrega conhecimento de templates irmãos (se fornecidos)
        known_keymap_targets: Set[str] = set()
        known_called_commands: Set[str] = set()
        known_button_actions: Set[str] = set()
        known_registered_commands: Set[str] = set(cls.KNOWN_LITEXL_COMMANDS)

        # 1. Alimenta com o próprio inventário
        for _, (target_cmd, _) in inventory.keymaps.items():
            known_keymap_targets.add(target_cmd)
        known_called_commands.update(inventory.called_commands)
        known_button_actions.update(inventory.ui_button_actions)
        known_registered_commands.update(inventory.commands.keys())

        # 2. Alimenta com inventários externos (ecosistema de templates)
        if external_inventories:
            for ext in external_inventories:
                for _, (target_cmd, _) in ext.keymaps.items():
                    known_keymap_targets.add(target_cmd)
                known_called_commands.update(ext.called_commands)
                known_button_actions.update(ext.ui_button_actions)
                known_registered_commands.update(ext.commands.keys())

        # Consumers consolidados
        all_consumers = known_keymap_targets | known_called_commands | known_button_actions

        # ───────────────────────────────────────────────────────────────────────
        # TESTE 1: COMANDOS ÓRFÃOS (command.add sem atalho, sem botão e sem perform)
        # ───────────────────────────────────────────────────────────────────────
        for cmd_name, (cmd_code, origin_file) in inventory.commands.items():
            # Verifica aliases conhecidos
            has_alias = cmd_name in COMMAND_ALIASES and COMMAND_ALIASES[cmd_name] in all_consumers
            is_consumed = (cmd_name in all_consumers) or has_alias

            # Ignora comandos de ciclo de vida universais da paleta de comandos do Lite XL
            is_palette_standard = cmd_name.startswith("core:") or cmd_name.startswith("doc:")

            if not is_consumed and not is_palette_standard:
                # Estima a linha
                line_no = 1
                for idx, line in enumerate(lines, 1):
                    if cmd_name in line:
                        line_no = idx
                        break

                findings.append(RegretFinding(
                    category="ORPHAN_COMMAND",
                    identifier=cmd_name,
                    severity="medium",
                    old_line_approx=line_no,
                    snippet_lost=cmd_code.splitlines()[0] if cmd_code else f"['{cmd_name}']",
                    impact_description=f"O comando '{cmd_name}' está registrado mas é ÓRFÃO: não tem atalho em keymap, não tem botão na UI e nunca é chamado por command.perform.",
                    mitigation_hint=f"Mapeie em keymap.add {{ ['<tecla>'] = '{cmd_name}' }}, associe a um botão ou execute via perform.",
                    mutation_pct=0.0
                ))

        # ───────────────────────────────────────────────────────────────────────
        # TESTE 2: ATALHOS CEGOS / MORTOS (keymap.add apontando para o vazio)
        # ───────────────────────────────────────────────────────────────────────
        for key_combo, (target_cmd, origin_file) in inventory.keymaps.items():
            # Se o comando não está registrado em lugar nenhum
            if target_cmd not in known_registered_commands and target_cmd not in COMMAND_ALIASES:
                line_no = 1
                for idx, line in enumerate(lines, 1):
                    if key_combo in line.lower():
                        line_no = idx
                        break

                findings.append(RegretFinding(
                    category="DEAD_KEYMAP",
                    identifier=f"[{key_combo}] -> {target_cmd}",
                    severity="high",
                    old_line_approx=line_no,
                    snippet_lost=f"['{key_combo}'] = '{target_cmd}'",
                    impact_description=f"O atalho '{key_combo}' aponta para o comando fantasma '{target_cmd}', que NÃO está registrado em nenhum command.add.",
                    mitigation_hint=f"Registre o comando '{target_cmd}' via command.add ou corrija o nome do comando no keymap.",
                    mutation_pct=0.0
                ))

        # ───────────────────────────────────────────────────────────────────────
        # TESTE 3: FUNÇÕES LOCAIS ZUMBIS (Declaradas mas nunca chamadas no módulo)
        # ───────────────────────────────────────────────────────────────────────
        for func_name, line_declared in inventory.local_functions.items():
            # Não audita helpers que começam com '_' de polyfill explícito ou hooks conhecidos
            if func_name.startswith("_static_") or func_name == "_replacer":
                continue

            # Conta quantas vezes a palavra exata da função aparece como chamada
            # (Se aparecer apenas 1 vez, é a própria declaração 'local function foo')
            call_matches = len(re.findall(rf'\b{re.escape(func_name)}\b', source_code))
            if call_matches <= 1:
                snippet = lines[line_declared - 1].strip() if line_declared <= len(lines) else f"local function {func_name}()"
                findings.append(RegretFinding(
                    category="ORPHAN_LOCAL_FUNCTION",
                    identifier=func_name,
                    severity="low",
                    old_line_approx=line_declared,
                    snippet_lost=snippet,
                    impact_description=f"A função local '{func_name}' foi declarada na linha {line_declared}, mas nunca é chamada no arquivo (código morto).",
                    mitigation_hint=f"Conecte '{func_name}' ao fluxo de execução ou remova a função para reduzir a entropia do arquivo.",
                    mutation_pct=0.0
                ))

        return findings

    @classmethod
    def _compute_diff(
        cls,
        old_inv: LuaCapabilityInventory,
        new_inv: LuaCapabilityInventory,
        file_name: str = "",
        is_split_mode: bool = False,
        sibling_sources: Optional[Dict[str, str]] = None
    ) -> List[RegretFinding]:
        findings: List[RegretFinding] = []

        # 1. Checagem diferencial tradicional (Comandos extirpados)
        for cmd, (old_snippet, origin) in old_inv.commands.items():
            if cmd not in new_inv.commands:
                # Checa aliases canônicos
                if cmd in COMMAND_ALIASES and COMMAND_ALIASES[cmd] in new_inv.commands:
                    continue

                # Checa se foi movido para arquivo irmão
                relocated = False
                if sibling_sources:
                    for s_name, s_code in sibling_sources.items():
                        if f'["{cmd}"]' in s_code or f"['{cmd}']" in s_code:
                            relocated = True
                            findings.append(RegretFinding(
                                category="RELOCATED_CROSS_FILE",
                                identifier=cmd,
                                severity="info",
                                old_line_approx=1,
                                snippet_lost=old_snippet,
                                impact_description=f"O comando '{cmd}' foi movido para o arquivo irmão '{s_name}'.",
                                mitigation_hint="Nenhuma ação necessária."
                            ))
                            break

                if not relocated:
                    findings.append(RegretFinding(
                        category="COMMAND_LOST",
                        identifier=cmd,
                        severity="high",
                        old_line_approx=1,
                        snippet_lost=old_snippet,
                        impact_description=f"O comando '{cmd}' não foi encontrado em nenhum dos módulos ativos.",
                        mitigation_hint=f"Restaurar command.add para '{cmd}'."
                    ))

        # 2. Checagem diferencial de Keymaps (Atalhos extirpados)
        for key, (old_target, origin) in old_inv.keymaps.items():
            if key not in new_inv.keymaps:
                # Checa mapeamento canônico
                if key in CANONICAL_KEYMAP_MAPPINGS:
                    new_key, expected_cmd = CANONICAL_KEYMAP_MAPPINGS[key]
                    if new_key in new_inv.keymaps:
                        continue

                # Checa se foi remapeado para outro atalho com mesmo comando
                remapped = False
                for nk, (nt, _) in new_inv.keymaps.items():
                    if nt == old_target or (old_target in COMMAND_ALIASES and nt == COMMAND_ALIASES[old_target]):
                        remapped = True
                        findings.append(RegretFinding(
                            category="KEYMAP_REASSIGNED",
                            identifier=f"{key} ➔ {nk}",
                            severity="info",
                            old_line_approx=1,
                            snippet_lost=f"['{key}'] = '{old_target}'",
                            impact_description=f"O atalho '{key}' para '{old_target}' foi remapeado para '{nk}'.",
                            mitigation_hint="Atalho atualizado."
                        ))
                        break

                if not remapped:
                    findings.append(RegretFinding(
                        category="KEYMAP_LOST",
                        identifier=key,
                        severity="high",
                        old_line_approx=1,
                        snippet_lost=f"['{key}'] = '{old_target}'",
                        impact_description=f"O atalho '{key}' não foi herdado em nenhum dos módulos novos.",
                        mitigation_hint=f"Reinserir keymap.add {{ ['{key}'] = '{old_target}' }}."
                    ))

        # 3. Métodos e Funções (Mutação e Volatilidade)
        for sig, old_body in old_inv.methods.items():
            if sig not in new_inv.methods:
                findings.append(RegretFinding(
                    category="METHOD_DROPPED",
                    identifier=sig,
                    severity="high",
                    old_line_approx=1,
                    snippet_lost=old_body.full_code,
                    impact_description=f"O método '{sig}' foi totalmente extirpado.",
                    mitigation_hint=f"Verificar se a lógica de {sig} ainda é necessária."
                ))
            else:
                new_body = new_inv.methods[sig]
                # Calcula volatilidade / mutação
                ratio = difflib.SequenceMatcher(None, old_body.full_code, new_body.full_code).ratio()
                mut_pct = round((1.0 - ratio) * 100, 1)

                if mut_pct > 80.0:
                    findings.append(RegretFinding(
                        category="VOLATILE_MUTATION",
                        identifier=f"{sig} ({mut_pct}% mutado)",
                        severity="medium",
                        old_line_approx=1,
                        snippet_lost=old_body.full_code,
                        impact_description=f"Reescrita radical ({mut_pct}% mutado). Considerada INSTÁVEL.",
                        mitigation_hint=f"Homologar o comportamento de {sig} em runtime.",
                        mutation_pct=mut_pct
                    ))
                elif mut_pct > 25.0:
                    findings.append(RegretFinding(
                        category="MODIFIED_MODERATE",
                        identifier=f"{sig} ({mut_pct}% mutado)",
                        severity="info",
                        old_line_approx=1,
                        snippet_lost="",
                        impact_description=f"Alteração moderada de fluxo/lógica ({mut_pct}% mutado).",
                        mitigation_hint=f"Revisar alterações internas em {sig}.",
                        mutation_pct=mut_pct
                    ))

        return findings
