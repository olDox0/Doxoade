# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_tree.py
# -*- coding: utf-8 -*-
""" Árvore Declarativa de Modos de Falha do Lite XL (Typhon Doxly Edition - Canônica).
Mapeia hierarquicamente: Sistemas -> Falhas -> Sintomas Regex -> Mitigações.
Proteção anti-duplicata ativa e suporte a tags de estresse composto (STRESS_01..03). """

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""


@dataclass(frozen=True)
class DoxlyFailureMode:
    """Modo de falha específico catalogado no ecossistema Lite XL."""
    id: str
    name: str
    subsystem: str
    severity: str = "high"  # low, medium, high, critical
    symptoms: Tuple[str, ...] = ()
    dev_comment: str = ""
    mitigation: str = ""
    auto_fixable: bool = False

    def matches(self, text: str) -> bool:
        """Verifica se algum sintoma regex casa contra o texto."""
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.symptoms)


@dataclass
class DoxlyNode:
    """Nó estrutural da árvore de componentes do Lite XL."""
    id: str
    name: str
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    failures: List[DoxlyFailureMode] = field(default_factory=list)


class DoxlyDiagnosticTree:
    """Árvore de diagnóstico hierárquica e motor de casamento de sintomas."""

    def __init__(self) -> None:
        self.nodes: Dict[str, DoxlyNode] = {}
        self.failures: Dict[str, DoxlyFailureMode] = {}

    def node(self, nid: str, name: str, parent: Optional[str] = None) -> DoxlyNode:
        """Cria e registra um nó estrutural na árvore."""
        n = DoxlyNode(nid, name, parent)
        self.nodes[nid] = n
        if parent and parent in self.nodes:
            self.nodes[parent].children.append(nid)
        return n

    def failure(self, nid: str, **kw: Any) -> DoxlyFailureMode:
        """Instancia, anexa ao nó e registra a falha com proteção anti-duplicata."""
        if nid not in self.nodes:
            raise KeyError(f"Nó pai '{nid}' não encontrado na árvore Doxly.")
        
        fmid = kw.get("id", "")
        # Se já existe, atualiza no nó e no índice para evitar duplicações silenciosas
        if fmid in self.failures:
            existing = self.failures[fmid]
            self.nodes[nid].failures = [f for f in self.nodes[nid].failures if f.id != fmid]

        fm = DoxlyFailureMode(subsystem=nid, **kw)
        self.nodes[nid].failures.append(fm)
        self.failures[fm.id] = fm
        return fm

    def get_by_id(self, fmid: str) -> Optional[DoxlyFailureMode]:
        return self.failures.get(fmid)

    def match_symptom(self, line: str) -> Optional[DoxlyFailureMode]:
        if not line or not line.strip():
            return None
        for fm in self.failures.values():
            if fm.matches(line):
                return fm
        return None

    def scan_text(self, text: str) -> List[Tuple[DoxlyFailureMode, str]]:
        matches: List[Tuple[DoxlyFailureMode, str]] = []
        seen_ids = set()
        for line in (text or "").splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            for fm in self.failures.values():
                if fm.id not in seen_ids and fm.matches(line_str):
                    matches.append((fm, line_str))
                    seen_ids.add(fm.id)
        return matches

    def print_tree(self, compact: bool = False) -> None:
        sev_icons = {
            "low": f"{Fore.CYAN}·{Fore.RESET}",
            "medium": f"{Fore.YELLOW}~{Fore.RESET}",
            "high": f"{Fore.LIGHTRED_EX}!{Fore.RESET}",
            "critical": f"{Fore.RED}☠{Fore.RESET}",
        }

        print(f"\n{Fore.CYAN}{Style.BRIGHT}🌳 ÁRVORE DIAGNÓSTICA TYPHON DOXLY{Style.RESET_ALL}\n")

        def _render_node(nid: str, depth: int = 0) -> None:
            n = self.nodes[nid]
            indent = "   " * depth
            print(f"{indent}{Fore.BLUE}├─ {Style.BRIGHT}{n.name}{Style.RESET_ALL} ({Fore.LIGHTBLACK_EX}{nid}{Fore.RESET})")

            for fm in n.failures:
                icon = sev_icons.get(fm.severity, "?")
                auto_badge = f" {Fore.GREEN}[Auto-Fix]{Fore.RESET}" if fm.auto_fixable else ""
                print(f"{indent}   [{icon}] {Fore.WHITE}{fm.id:<38}{Fore.RESET}{auto_badge}")
                if not compact:
                    print(f"{indent}       {Fore.LIGHTBLACK_EX}↳ {fm.dev_comment[:80]}…{Fore.RESET}")

            for child_id in n.children:
                _render_node(child_id, depth + 1)

        for nid, n in self.nodes.items():
            if n.parent is None:
                _render_node(nid, 0)
        print()


# =============================================================================
# CATÁLOGO CANÔNICO DOS 12 MODOS DE FALHA (Sem Duplicatas)
# =============================================================================

DOXLY_TREE = DoxlyDiagnosticTree()

DOXLY_TREE.node("doxly", "Lite XL (Doxly Root)")
DOXLY_TREE.node("syntax", "Sintaxe & Tokenizer", parent="doxly")
DOXLY_TREE.node("render", "Renderizador, Layout & Views", parent="doxly")
DOXLY_TREE.node("config", "Configuração & Plugins Nativos", parent="doxly")
DOXLY_TREE.node("runtime", "Runtime, Corrotinas & Processo", parent="doxly")
DOXLY_TREE.node("api_guard", "Contratos de API & Monkey-Patches", parent="doxly")


# --- 1. Sintaxe & Tokenizer ---
DOXLY_TREE.failure(
    "syntax",
    id="doxly.tokenizer.nil_compare",
    name="Comparação Nula no Tokenizer",
    severity="critical",
    symptoms=(
        r"tokenizer\.lua:270: attempt to compare number with nil",
        r"attempt to compare number with nil",
        r"Tokenizer recuperou buffer corrompido",
        r"\[CHAOS\] Tokenizer nil compare disparado",
        r"\[STRESS_03\]",
        r"\[SYNTAX SHIELD\] ⚠ Tokenizer",
    ),
    dev_comment="Ocorre no loop 'while i <= text_len do' quando 'text' ou 'text_len' é nil.",
    mitigation="Ativar o Tokenizer Shield V2.2 com short-circuit binário e sanitização de text.",
    auto_fixable=True,
)

DOXLY_TREE.failure(
    "syntax",
    id="doxly.tokenizer.invalid_state",
    name="Estado de Tokenizer Inválido (Number State)",
    severity="high",
    symptoms=(
        r"tokenizer\.lua:74: attempt to index a number value",
        r"attempt to index a number value \(local 'state'\)",
        r"\[CHAOS\] Tokenizer number state disparado",
    ),
    dev_comment="No Lite XL 2.1+, 'state' deve ser table ou nil. Retornar número quebra o scroll.",
    mitigation="Garantir que o fallback do tokenizer retorne 'nil' para o state em caso de recuperação.",
    auto_fixable=True,
)

DOXLY_TREE.failure(
    "syntax",
    id="doxly.syntax.corrupted_pattern",
    name="Padrão de Sintaxe Corrompido",
    severity="medium",
    symptoms=(
        r"Pattern #\d+ inválido",
        r"Pattern #\d+ inv[aá]lido",
        r"tipo=pattern:nil",
        r"pattern sem campo 'pattern'",
        r"\[CHAOS\] Syntax com pattern corrompido",
        r"Syntax '.*' vacinada",
    ),
    dev_comment="Sintaxes carregadas com tabelas de pattern contendo campos nulos provocam falha no parser.",
    mitigation="Executar a Syntax Vaccine no boot para expurgar patterns inválidos de syntax.items.",
    auto_fixable=True,
)

DOXLY_TREE.failure(
    "syntax",
    id="doxly.syntax.binary_raw_highlight",
    name="Highlight em Buffer Binário/Bytecode",
    severity="high",
    symptoms=(
        r"identificado como bin[aá]rio",
        r"associado [aà] sintaxe Plain Text",
        r"\[BINARY GUARD\]",
        r"\[CHAOS\] Buffer bin[aá]rio aberto",
        r"\[STRESS_01\]",
        r"^\x1bLua",
    ),
    dev_comment="Arquivos compilados em Bytecode (.lua) não devem receber highlighting de código.",
    mitigation="Acionar o Binary Doc Guard no core.open_doc forçando Plain Text e resetando o highlighter.",
    auto_fixable=True,
)


# --- 2. Renderizador, Layout & Views ---
DOXLY_TREE.failure(
    "render",
    id="doxly.docview.nil_highlighter",
    name="DocView com Highlighter Nulo",
    severity="critical",
    symptoms=(
        r"docview\.lua:444: attempt to index a nil value \(field 'highlighter'\)",
        r"docview\.lua:178: attempt to index a nil value \(field 'highlighter'\)",
        r"attempt to index a nil value \(field 'highlighter'\)",
        r"\[CHAOS\] active_doc\.highlighter anulado",
    ),
    dev_comment="DocView:draw_line_body assume como invariante estrita que self.doc.highlighter existe.",
    mitigation="Nunca setar doc.highlighter = nil. Apenas aponte doc.syntax para Plain Text e chame :reset().",
    auto_fixable=True,
)

DOXLY_TREE.failure(
    "render",
    id="doxly.node.orphan_view",
    name="View Órfã sem Métodos de Contrato",
    severity="high",
    symptoms=(
        r"Orphan View",
        r"Active Orphan",
        r"\[CHAOS\] View [oó]rf[aã] injetada",
        r"\[STRESS_02\]",
        r"attempt to call method 'get_name' \(a nil value\)",
    ),
    dev_comment="Views injetadas sem herdar de View causam crash durante o redesenho de abas e layout.",
    mitigation="Aplicar polyfills contratuais automáticos no core.step via sanitize_node.",
    auto_fixable=True,
)


# --- 3. Configuração & Plugins Nativos ---
DOXLY_TREE.failure(
    "config",
    id="doxly.settings.nil_table_index",
    name="Settings Plugin Indexando Retorno Nulo",
    severity="high",
    symptoms=(
        r"settings\.lua:843: attempt to index a nil value \(local 't'\)",
        r"attempt to index a nil value \(local 't'\)",
        r"\[CHAOS\] user_settings\.lua corrompido",
        r"\[STRESS_01\]",
        r"user_settings\.lua Inv[aá]lido",
    ),
    dev_comment="No Lite XL nativo, 'ok and t.config or {}' falha se user_settings.lua retorna nil.",
    mitigation="Inicializar user_settings.lua com tabela explícita 'return { [\"config\"] = { ... } }'.",
    auto_fixable=True,
)

DOXLY_TREE.failure(
    "config",
    id="doxly.config.missing_user_settings",
    name="Arquivo user_settings.lua Ausente",
    severity="medium",
    symptoms=(
        r"user_settings\.lua n[aã]o encontrado",
        r"user_settings\.lua ausente",
        r"\[CHAOS\] user_settings\.lua deletado",
        r"Arquivo user_settings\.lua Ausente",
    ),
    dev_comment="A ausência do arquivo de preferências impede a persistência de FPS e temas.",
    mitigation="Executar auto-bootstrap criando user_settings.lua com baseline de 60 FPS.",
    auto_fixable=True,
)


# --- 4. Runtime, Corrotinas & Processo ---
DOXLY_TREE.failure(
    "runtime",
    id="doxly.khonsu.coroutine_budget_spike",
    name="Estouro de Orçamento da Corrotina Khonsu",
    severity="medium",
    symptoms=(
        r"Khonsu budget overrun",
        r"status: BLOCKING",
        r"thread_bottlenecks",
        r"\[CHAOS\] Thread bloqueante",
        r"\[STRESS_02\]",
        r"Degrada[cç][aã]o de FPS Detectada",
    ),
    dev_comment="Tarefas em background ultrapassando 1.5ms por tick causam stuttering no render loop.",
    mitigation="Ajustar o particionamento de itens em Khonsu.run_sliced_task.",
    auto_fixable=False,
)

DOXLY_TREE.failure(
    "runtime",
    id="doxly.process.ghost_zombie",
    name="Instância Zumbi do Lite XL Ativa",
    severity="high",
    symptoms=(
        r"Processo Lite XL zumbi",
        r"IMAGENAME eq lite-xl\.exe",
        r"LITE_USERDIR bloqueado",
        r"\[CHAOS\] Fila IPC bloqueada",
        r"Fila IPC travada",
    ),
    dev_comment="Processos antigos não encerrados graciosamente travam arquivos de sessão e portas IPC.",
    mitigation="Acionar TyphonDeployEngine.exorcise_instances() para encerrar instâncias residuais.",
    auto_fixable=True,
)


# --- 5. Contratos de API & Monkey-Patches ---
DOXLY_TREE.failure(
    "api_guard",
    id="doxly.api.missing_critical_symbol",
    name="Símbolo Crítico da API Lite XL Ausente",
    severity="critical",
    symptoms=(
        r"APIs cr[ií]ticas ausentes",
        r"runtime_probe\.json: missing",
        r"API Ausente:",
        r"\[CHAOS\] S[ií]mbolo cr[ií]tico ausente",
    ),
    dev_comment="Funções essenciais como RootView.draw ou Doc.insert não foram encontradas pelo API Guard.",
    mitigation="Verificar integridade do executável Lite XL ou injetar polyfills em 00_header_and_logger.lua.",
    auto_fixable=False,
)

DOXLY_TREE.failure(
    "api_guard",
    id="doxly.api.patch_nil_target",
    name="Monkey-Patch em Alvo Inexistente",
    severity="high",
    symptoms=(
        r"Alvo do patch .* [eé] nil",
        r"ORIGINAL_METHOD_NIL",
        r"\[API GUARD\].*Patch ignorado",
        r"\[CHAOS\] API\.patch aplicado",
        r"\[STRESS_03\]",
    ),
    dev_comment="Tentativa de envolver método que não existe na versão atual do Lite XL.",
    mitigation="O API.patch aborta a operação e aciona o fallback com segurança.",
    auto_fixable=True,
)
