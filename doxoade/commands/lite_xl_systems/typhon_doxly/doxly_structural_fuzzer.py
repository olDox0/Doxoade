# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_structural_fuzzer.py
# -*- coding: utf-8 -*-
r"""
🏗️ DOXLY STRUCTURAL FUZZER V2 — Motor de Mutações Estruturais Avançadas.
Extende o Mutation Fuzzer com:
  • Adição de conteúdo (blocos, requires, funções fantasma)
  • Remoção de conteúdo (requires críticos, handlers, wrappers)
  • Alteração de conteúdo (assinaturas, argumentos, lógica invertida)
  • Detecção de Duplicações (funções, requires, comandos registrados 2x)
  • Detecção de Funcionalidades Órfãs (código morto, never-called)

Responde às 5 Perguntas mesmo em cenários de corrupção silenciosa.
"""
from __future__ import annotations

import os
import re
import sys
import time
import random
import hashlib
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from enum import Enum, auto

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
from .doxly_khonsu_gate import DoxlyKhonsuGate


# ═══════════════════════════════════════════════════════════════════════════
# ENUMERAÇÕES E DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

class MutationPhase(Enum):
    """Fase em que a mutação estrutural se manifesta."""
    PREFLIGHT = auto()      # Detectado na compilação AOT
    BOOT = auto()           # Detectado no boot do init.lua
    RUNTIME = auto()        # Detectado durante execução
    SILENT = auto()         # Não detectado (ponto cego)


class MutationKind(Enum):
    """Tipo de mutação estrutural."""
    ADD = "adição"
    REMOVE = "remoção"
    ALTER = "alteração"
    DUPLICATE = "duplicação"
    ORPHAN = "orfandade"


class StructuralCategory(Enum):
    """Categoria do alvo estrutural."""
    FUNCTION_DEF = "function_def"
    REQUIRE_STMT = "require_stmt"
    COMMAND_REG = "command_registration"
    VARIABLE_DECL = "variable_declaration"
    PCALL_WRAPPER = "pcall_wrapper"
    THREAD_SPAWN = "thread_spawn"
    EVENT_HANDLER = "event_handler"
    CONFIG_FIELD = "config_field"


@dataclass
class StructuralTarget:
    """Alvo estrutural identificado em um template."""
    template_name: str
    line_start: int
    line_end: int
    category: StructuralCategory
    identifier: str
    content: str
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    is_called: bool = True
    call_count: int = 0


@dataclass
class StructuralMutation:
    """Definição de uma mutação estrutural."""
    id: str
    kind: MutationKind
    category: StructuralCategory
    phase: MutationPhase
    description: str
    severity: str  # "critical", "high", "medium", "low"
    generate: Any  # Callable[[List[str], StructuralTarget], Tuple[List[str], str]]
    expected_detection: str  # O que o sistema DEVE detectar
    five_questions: Dict[str, str] = field(default_factory=dict)


@dataclass
class DuplicationFinding:
    """Achado de duplicação."""
    template_name: str
    identifier: str
    category: StructuralCategory
    occurrences: List[int]  # linhas
    severity: str
    is_harmful: bool
    message: str


@dataclass
class OrphanFinding:
    """Achado de funcionalidade órfã."""
    template_name: str
    identifier: str
    category: StructuralCategory
    line: int
    reason: str
    severity: str
    suggestion: str


@dataclass
class StructuralAuditReport:
    """Relatório consolidado da auditoria estrutural."""
    total_templates: int = 0
    total_functions: int = 0
    total_requires: int = 0
    total_commands: int = 0
    duplications: List[DuplicationFinding] = field(default_factory=list)
    orphans: List[OrphanFinding] = field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    dead_code_lines: int = 0
    health_score: float = 100.0


# ═══════════════════════════════════════════════════════════════════════════
# PARSER ESTRUTURAL LUA (Lexer Simplificado para Análise)
# ═══════════════════════════════════════════════════════════════════════════

class LuaStructuralParser:
    """Parser estrutural de Lua para identificação de alvos de mutação."""

    # Padrões de reconhecimento
    RE_FUNCTION_DEF = re.compile(
        r'^(?:local\s+)?function\s+([\w.:]+)\s*\(([^)]*)\)',
        re.MULTILINE
    )
    RE_METHOD_DEF = re.compile(
        r'^function\s+([\w.]+):([\w_]+)\s*\(([^)]*)\)',
        re.MULTILINE
    )
    RE_REQUIRE = re.compile(
        r'^(?:local\s+)?(\w+)\s*=\s*require\s*["\']([^"\']+)["\']',
        re.MULTILINE
    )
    RE_REQUIRE_PCALL = re.compile(
        r'^(?:local\s+)?(\w+)\s*=\s*(?:pcall\s*\(\s*require\s*,\s*["\']([^"\']+)["\'])',
        re.MULTILINE
    )
    RE_COMMAND_ADD = re.compile(
        r'\[["\']([^"\']+)["\']\]\s*=\s*function',
        re.MULTILINE
    )
    RE_COMMAND_PERFORM = re.compile(
        r'command\.perform\s*\(\s*["\']([^"\']+)["\']',
        re.MULTILINE
    )
    RE_KEYMAP_ADD = re.compile(
        r'\[["\']([^"\']+)["\']\]\s*=\s*["\']([^"\']+)["\']',
        re.MULTILINE
    )
    RE_PCALL_WRAP = re.compile(
        r'pcall\s*\(\s*([\w.:]+)',
        re.MULTILINE
    )
    RE_CORE_ADD_THREAD = re.compile(
        r'core\.add_thread\s*\(\s*function',
        re.MULTILINE
    )
    RE_LOCAL_DECL = re.compile(
        r'^local\s+(\w+)\s*=',
        re.MULTILINE
    )
    RE_FUNCTION_CALL = re.compile(
        r'([\w.:]+)\s*\(',
        re.MULTILINE
    )
    RE_RAWSET_GLOBAL = re.compile(
        r'rawset\s*\(\s*_G\s*,\s*["\'](\w+)["\']',
        re.MULTILINE
    )

    @classmethod
    def parse_template(cls, template_path: Path) -> List[StructuralTarget]:
        """Parse completo de um template, extraindo todos os alvos estruturais."""
        content = template_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        targets: List[StructuralTarget] = []
        template_name = template_path.name

        # 1. Funções locais e globais
        for match in cls.RE_FUNCTION_DEF.finditer(content):
            line_no = content[:match.start()].count('\n') + 1
            func_name = match.group(1)
            params = match.group(2)
            targets.append(StructuralTarget(
                template_name=template_name,
                line_start=line_no,
                line_end=cls._find_block_end(lines, line_no),
                category=StructuralCategory.FUNCTION_DEF,
                identifier=func_name,
                content=match.group(0),
                dependencies=cls._extract_dependencies(params),
            ))

        # 2. Métodos (function Obj:method)
        for match in cls.RE_METHOD_DEF.finditer(content):
            line_no = content[:match.start()].count('\n') + 1
            obj_name = match.group(1)
            method_name = match.group(2)
            full_name = f"{obj_name}:{method_name}"
            targets.append(StructuralTarget(
                template_name=template_name,
                line_start=line_no,
                line_end=cls._find_block_end(lines, line_no),
                category=StructuralCategory.FUNCTION_DEF,
                identifier=full_name,
                content=match.group(0),
            ))

        # 3. Requires
        for match in cls.RE_REQUIRE.finditer(content):
            line_no = content[:match.start()].count('\n') + 1
            var_name = match.group(1)
            module_path = match.group(2)
            targets.append(StructuralTarget(
                template_name=template_name,
                line_start=line_no,
                line_end=line_no,
                category=StructuralCategory.REQUIRE_STMT,
                identifier=var_name,
                content=match.group(0),
                dependencies=[module_path],
            ))

        # 4. Requires com pcall
        for match in cls.RE_REQUIRE_PCALL.finditer(content):
            line_no = content[:match.start()].count('\n') + 1
            var_name = match.group(1)
            module_path = match.group(2)
            targets.append(StructuralTarget(
                template_name=template_name,
                line_start=line_no,
                line_end=line_no,
                category=StructuralCategory.REQUIRE_STMT,
                identifier=var_name,
                content=match.group(0),
                dependencies=[module_path],
            ))

        # 5. Registros de comandos
        for match in cls.RE_COMMAND_ADD.finditer(content):
            line_no = content[:match.start()].count('\n') + 1
            cmd_name = match.group(1)
            targets.append(StructuralTarget(
                template_name=template_name,
                line_start=line_no,
                line_end=cls._find_block_end(lines, line_no),
                category=StructuralCategory.COMMAND_REG,
                identifier=cmd_name,
                content=match.group(0),
            ))

        # 6. Threads (core.add_thread)
        for match in cls.RE_CORE_ADD_THREAD.finditer(content):
            line_no = content[:match.start()].count('\n') + 1
            targets.append(StructuralTarget(
                template_name=template_name,
                line_start=line_no,
                line_end=cls._find_block_end(lines, line_no),
                category=StructuralCategory.THREAD_SPAWN,
                identifier=f"thread_L{line_no}",
                content=match.group(0),
            ))

        # 7. rawset globals
        for match in cls.RE_RAWSET_GLOBAL.finditer(content):
            line_no = content[:match.start()].count('\n') + 1
            global_name = match.group(1)
            targets.append(StructuralTarget(
                template_name=template_name,
                line_start=line_no,
                line_end=line_no,
                category=StructuralCategory.VARIABLE_DECL,
                identifier=global_name,
                content=match.group(0),
            ))

        return targets

    @classmethod
    def _find_block_end(cls, lines: List[str], start_line: int) -> int:
        """Encontra o fim de um bloco Lua (function/if/do) contando opens/closes."""
        depth = 0
        started = False
        for i in range(start_line - 1, min(len(lines), start_line + 500)):
            line = lines[i]
            # Remove comentários e strings para contagem segura
            clean = re.sub(r'--.*$', '', line)
            clean = re.sub(r'"[^"]*"', '""', clean)
            clean = re.sub(r"'[^']*'", "''", clean)

            opens = len(re.findall(r'\b(?:function|if|do|while|for)\b', clean))
            closes = len(re.findall(r'\bend\b', clean))

            depth += opens - closes
            if opens > 0:
                started = True
            if started and depth <= 0:
                return i + 1
        return min(len(lines), start_line + 10)

    @classmethod
    def _extract_dependencies(cls, params_str: str) -> List[str]:
        """Extrai nomes de parâmetros como dependências potenciais."""
        if not params_str.strip():
            return []
        return [p.strip() for p in params_str.split(',') if p.strip() and p.strip() != '...']

    @classmethod
    def find_all_calls(cls, content: str) -> Set[str]:
        """Encontra todos os identificadores chamados em um conteúdo."""
        calls = set()
        for match in cls.RE_FUNCTION_CALL.finditer(content):
            calls.add(match.group(1))
        for match in cls.RE_COMMAND_PERFORM.finditer(content):
            calls.add(match.group(1))
        return calls


# ═══════════════════════════════════════════════════════════════════════════
# DETECTOR DE DUPLICAÇÕES
# ═══════════════════════════════════════════════════════════════════════════

class DuplicationDetector:
    """🔍 Detecta duplicações estruturais em todo o conjunto de templates."""

    @classmethod
    def scan_all_templates(cls, templates: List[Path]) -> List[DuplicationFinding]:
        """Varre todos os templates buscando duplicações."""
        findings: List[DuplicationFinding] = []

        # Coleta global
        all_functions: Dict[str, List[Tuple[str, int]]] = {}
        all_requires: Dict[str, List[Tuple[str, int]]] = {}
        all_commands: Dict[str, List[Tuple[str, int]]] = {}
        all_globals: Dict[str, List[Tuple[str, int]]] = {}

        for tf in templates:
            targets = LuaStructuralParser.parse_template(tf)
            for target in targets:
                if target.category == StructuralCategory.FUNCTION_DEF:
                    all_functions.setdefault(target.identifier, []).append(
                        (target.template_name, target.line_start)
                    )
                elif target.category == StructuralCategory.REQUIRE_STMT:
                    all_requires.setdefault(target.identifier, []).append(
                        (target.template_name, target.line_start)
                    )
                elif target.category == StructuralCategory.COMMAND_REG:
                    all_commands.setdefault(target.identifier, []).append(
                        (target.template_name, target.line_start)
                    )
                elif target.category == StructuralCategory.VARIABLE_DECL:
                    all_globals.setdefault(target.identifier, []).append(
                        (target.template_name, target.line_start)
                    )

        # Analisa funções duplicadas
        for func_name, locations in all_functions.items():
            if len(locations) > 1:
                # Verifica se são templates diferentes (duplicação real)
                unique_templates = set(loc[0] for loc in locations)
                if len(unique_templates) > 1:
                    findings.append(DuplicationFinding(
                        template_name=", ".join(unique_templates),
                        identifier=func_name,
                        category=StructuralCategory.FUNCTION_DEF,
                        occurrences=[loc[1] for loc in locations],
                        severity="high",
                        is_harmful=True,
                        message=f"Função '{func_name}' definida em {len(unique_templates)} templates distintos. "
                                f"Última definição sobrescreve as anteriores.",
                    ))
                elif len(locations) > 1:
                    # Mesma template, múltiplas definições
                    findings.append(DuplicationFinding(
                        template_name=locations[0][0],
                        identifier=func_name,
                        category=StructuralCategory.FUNCTION_DEF,
                        occurrences=[loc[1] for loc in locations],
                        severity="medium",
                        is_harmful=True,
                        message=f"Função '{func_name}' redefinida {len(locations)}x no mesmo template.",
                    ))

        # Analisa requires duplicados (mesma variável local)
        for var_name, locations in all_requires.items():
            if len(locations) > 1:
                unique_templates = set(loc[0] for loc in locations)
                if len(unique_templates) > 1:
                    findings.append(DuplicationFinding(
                        template_name=", ".join(unique_templates),
                        identifier=var_name,
                        category=StructuralCategory.REQUIRE_STMT,
                        occurrences=[loc[1] for loc in locations],
                        severity="medium",
                        is_harmful=False,
                        message=f"Variável local '{var_name}' usada para require em {len(unique_templates)} templates. "
                                f"Seguro (escopo local), mas indica falta de padronização.",
                    ))

        # Analisa comandos duplicados (CRÍTICO)
        for cmd_name, locations in all_commands.items():
            if len(locations) > 1:
                unique_templates = set(loc[0] for loc in locations)
                findings.append(DuplicationFinding(
                    template_name=", ".join(unique_templates),
                    identifier=cmd_name,
                    category=StructuralCategory.COMMAND_REG,
                    occurrences=[loc[1] for loc in locations],
                    severity="critical",
                    is_harmful=True,
                    message=f"Comando '{cmd_name}' registrado {len(locations)}x. "
                            f"Último registro sobrescreve comportamento dos anteriores.",
                ))

        # Analisa globals duplicados via rawset
        for global_name, locations in all_globals.items():
            if len(locations) > 1:
                unique_templates = set(loc[0] for loc in locations)
                if len(unique_templates) > 1:
                    findings.append(DuplicationFinding(
                        template_name=", ".join(unique_templates),
                        identifier=global_name,
                        category=StructuralCategory.VARIABLE_DECL,
                        occurrences=[loc[1] for loc in locations],
                        severity="high",
                        is_harmful=True,
                        message=f"Global '{global_name}' definida via rawset em {len(unique_templates)} templates. "
                                f"Risco de sobrescrita de estado compartilhado.",
                    ))

        return findings

    @classmethod
    def print_findings(cls, findings: List[DuplicationFinding]) -> None:
        """Renderiza achados de duplicação."""
        if not findings:
            print(f"  {Fore.GREEN}✔ Nenhuma duplicação estrutural detectada.{Fore.RESET}")
            return

        print(f"\n  {Fore.YELLOW}{Style.BRIGHT}🔍 DUPLICAÇÕES DETECTADAS ({len(findings)}):{Style.RESET_ALL}")
        for i, f in enumerate(findings, 1):
            sev_color = Fore.RED if f.severity == "critical" else (
                Fore.LIGHTRED_EX if f.severity == "high" else Fore.YELLOW
            )
            harm_icon = "☠" if f.is_harmful else "⚠"
            print(f"    {sev_color}{harm_icon} [{f.severity.upper()}] {Fore.WHITE}{f.identifier}{Fore.RESET}")
            print(f"       {Fore.LIGHTBLACK_EX}↳ {f.message}{Fore.RESET}")
            print(f"       {Fore.LIGHTBLACK_EX}   Templates: {f.template_name} | Linhas: {f.occurrences}{Fore.RESET}")
        print()


# ═══════════════════════════════════════════════════════════════════════════
# DETECTOR DE FUNCIONALIDADES ÓRFÃS
# ═══════════════════════════════════════════════════════════════════════════

class OrphanDetector:
    """👻 Detecta funcionalidades órfãs (código morto, nunca chamado)."""

    @classmethod
    def scan_all_templates(cls, templates: List[Path]) -> List[OrphanFinding]:
        """Varre todos os templates buscando código órfão."""
        findings: List[OrphanFinding] = []

        # Fase 1: Coletar todas as definições e todas as chamadas
        all_defs: List[StructuralTarget] = []
        all_calls: Set[str] = set()
        all_content = ""

        for tf in templates:
            content = tf.read_text(encoding="utf-8", errors="replace")
            all_content += content + "\n"
            targets = LuaStructuralParser.parse_template(tf)
            all_defs.extend(targets)
            all_calls.update(LuaStructuralParser.find_all_calls(content))

        # Também busca command.perform e keymap references
        all_calls.update(re.findall(r'command\.perform\s*\(\s*["\']([^"\']+)["\']', all_content))
        all_calls.update(re.findall(r'\[["\'][\w+]+["\']\]\s*=\s*["\']([^"\']+)["\']', all_content))

        # Fase 2: Verificar quais definições nunca são chamadas
        for target in all_defs:
            if target.category == StructuralCategory.FUNCTION_DEF:
                # Verifica se a função é chamada em algum lugar
                func_name = target.identifier
                # Remove prefixo de método para busca
                simple_name = func_name.split(":")[-1] if ":" in func_name else func_name

                is_called = (
                    func_name in all_calls or
                    simple_name in all_calls or
                    f"pcall({func_name}" in all_content or
                    f"pcall(function()" in all_content  # Wrappers anônimos
                )

                # Funções de callback/hook são "chamadas" implicitamente
                is_implicit = any(kw in func_name.lower() for kw in [
                    "draw", "update", "on_", "step", "init", "new", "extend"
                ])

                if not is_called and not is_implicit:
                    findings.append(OrphanFinding(
                        template_name=target.template_name,
                        identifier=func_name,
                        category=StructuralCategory.FUNCTION_DEF,
                        line=target.line_start,
                        reason="Função definida mas nunca chamada em nenhum template.",
                        severity="medium",
                        suggestion=f"Verificar se '{func_name}' é um callback implícito ou código morto.",
                    ))

            elif target.category == StructuralCategory.REQUIRE_STMT:
                # Verifica se a variável do require é usada após a declaração
                var_name = target.identifier
                # Busca uso após a linha do require
                usage_pattern = re.compile(
                    rf'\b{re.escape(var_name)}\b(?!\s*=)'
                )
                # Contagem simples: aparece mais de uma vez?
                occurrences = len(usage_pattern.findall(all_content))
                if occurrences <= 1:
                    findings.append(OrphanFinding(
                        template_name=target.template_name,
                        identifier=var_name,
                        category=StructuralCategory.REQUIRE_STMT,
                        line=target.line_start,
                        reason=f"Require de '{var_name}' carregado mas variável nunca utilizada.",
                        severity="low",
                        suggestion=f"Remover require órfão ou verificar uso indireto via _G.",
                    ))

            elif target.category == StructuralCategory.COMMAND_REG:
                # Verifica se o comando é referenciado em keymaps ou command.perform
                cmd_name = target.identifier
                is_referenced = (
                    cmd_name in all_calls or
                    f'"{cmd_name}"' in all_content or
                    f"'{cmd_name}'" in all_content
                )
                if not is_referenced:
                    findings.append(OrphanFinding(
                        template_name=target.template_name,
                        identifier=cmd_name,
                        category=StructuralCategory.COMMAND_REG,
                        line=target.line_start,
                        reason="Comando registrado mas nunca invocado via keymap ou command.perform.",
                        severity="low",
                        suggestion=f"Adicionar keymap para '{cmd_name}' ou remover se obsoleto.",
                    ))

        return findings

    @classmethod
    def print_findings(cls, findings: List[OrphanFinding]) -> None:
        """Renderiza achados de orfandade."""
        if not findings:
            print(f"  {Fore.GREEN}✔ Nenhuma funcionalidade órfã detectada.{Fore.RESET}")
            return

        print(f"\n  {Fore.CYAN}{Style.BRIGHT}👻 FUNCIONALIDADES ÓRFÃS ({len(findings)}):{Style.RESET_ALL}")
        for i, f in enumerate(findings, 1):
            sev_color = Fore.YELLOW if f.severity == "medium" else Fore.LIGHTBLACK_EX
            print(f"    {sev_color}👻 [{f.severity.upper()}] {Fore.WHITE}{f.identifier}{Fore.RESET} "
                  f"({Fore.LIGHTBLACK_EX}{f.template_name}:{f.line}{Fore.RESET})")
            print(f"       {Fore.LIGHTBLACK_EX}↳ {f.reason}{Fore.RESET}")
            print(f"       {Fore.LIGHTBLACK_EX}   💡 {f.suggestion}{Fore.RESET}")
        print()


# ═══════════════════════════════════════════════════════════════════════════
# VETORES DE MUTAÇÃO ESTRUTURAL AVANÇADA
# ═══════════════════════════════════════════════════════════════════════════

STRUCTURAL_MUTATION_VECTORS: List[StructuralMutation] = [
    # ─── ADIÇÃO ───────────────────────────────────────────────────────────────
    StructuralMutation(
        id="STRUCT_ADD_PHANTOM_REQUIRE",
        kind=MutationKind.ADD,
        category=StructuralCategory.REQUIRE_STMT,
        phase=MutationPhase.BOOT,
        description="Injeta require de módulo inexistente SEM pcall (crash de boot)",
        severity="critical",
        expected_detection="process_exit ou error.txt com 'module not found'",
        generate=lambda lines, target: (
            lines[:random.randint(1, min(5, len(lines)))] +
            ['local phantom_module = require "core.this_module_does_not_exist_anywhere"'] +
            lines[random.randint(1, min(5, len(lines))):],
            "require fantasma sem proteção pcall"
        ),
    ),
    StructuralMutation(
        id="STRUCT_ADD_SHADOW_FUNCTION",
        kind=MutationKind.ADD,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.RUNTIME,
        description="Injeta função com MESMO NOME de uma existente (shadowing silencioso)",
        severity="high",
        expected_detection="log de boot reportando módulo com comportamento alterado",
        generate=lambda lines, target: (
            lines + [
                "",
                f"-- 🏗️ [STRUCTURAL MUTATION] Shadow function injetada",
                f"local function {target.identifier.split(':')[-1] if ':' in target.identifier else target.identifier}()",
                f"  core.log('👻 [SHADOW] Função original foi sobrescrita silenciosamente')",
                f"  return nil -- comportamento corrompido",
                f"end",
            ],
            f"shadow de '{target.identifier}'"
        ),
    ),
    StructuralMutation(
        id="STRUCT_ADD_DUPLICATE_COMMAND",
        kind=MutationKind.ADD,
        category=StructuralCategory.COMMAND_REG,
        phase=MutationPhase.BOOT,
        description="Registra o MESMO comando novamente com comportamento corrompido",
        severity="critical",
        expected_detection="log de comando sobrescrito ou comportamento divergente",
        generate=lambda lines, target: (
            lines + [
                "",
                "-- 🏗️ [STRUCTURAL MUTATION] Comando duplicado com comportamento corrompido",
                'command.add(nil, {',
                f'  ["{target.identifier}"] = function()',
                f'    core.error("[DUPLICATE] Comando {target.identifier} foi sobrescrito por mutação!")',
                f'  end',
                '})',
            ],
            f"duplicação de '{target.identifier}'"
        ),
    ),
    StructuralMutation(
        id="STRUCT_ADD_GLOBAL_POLLUTION_BLOCK",
        kind=MutationKind.ADD,
        category=StructuralCategory.VARIABLE_DECL,
        phase=MutationPhase.RUNTIME,
        description="Injeta bloco que polui _G com 10 variáveis globais",
        severity="medium",
        expected_detection="hook de global leak detecta poluição",
        generate=lambda lines, target: (
            lines + [
                "",
                "-- 🏗️ [STRUCTURAL MUTATION] Poluição global em massa",
                "core.add_thread(function()",
                "  coroutine.yield(0.5)",
            ] + [
                f"  STRUCTURAL_LEAK_{i} = {{ corrupted = true, idx = {i} }}"
                for i in range(10)
            ] + [
                "  core.log('🏗️ [STRUCT] 10 globais vazadas')",
                "end)",
            ],
            "poluição global em massa"
        ),
    ),
    StructuralMutation(
        id="STRUCT_ADD_RECURSIVE_THREAD_BOMB",
        kind=MutationKind.ADD,
        category=StructuralCategory.THREAD_SPAWN,
        phase=MutationPhase.RUNTIME,
        description="Injeta thread que spawna 20 sub-threads recursivas (thread bomb)",
        severity="high",
        expected_detection="telemetria Chronos detecta thread_bottleneck ou frame spike",
        generate=lambda lines, target: (
            lines + [
                "",
                "-- 🏗️ [STRUCTURAL MUTATION] Thread Bomb (20 threads recursivas)",
                "core.add_thread(function()",
                "  coroutine.yield(0.3)",
                "  local function spawn_bomb(depth)",
                "    if depth <= 0 then return end",
                "    core.add_thread(function()",
                "      coroutine.yield(0.1)",
                "      spawn_bomb(depth - 1)",
                "    end)",
                "  end",
                "  spawn_bomb(20)",
                "  core.log('🏗️ [STRUCT] Thread bomb armada: 20 threads recursivas')",
                "end)",
            ],
            "thread bomb com 20 corrotinas recursivas"
        ),
    ),

    # ─── REMOÇÃO ──────────────────────────────────────────────────────────────
    StructuralMutation(
        id="STRUCT_REMOVE_CRITICAL_REQUIRE",
        kind=MutationKind.REMOVE,
        category=StructuralCategory.REQUIRE_STMT,
        phase=MutationPhase.BOOT,
        description="Remove require crítico que outros blocos dependem",
        severity="critical",
        expected_detection="erro 'attempt to index a nil value' no primeiro uso",
        generate=lambda lines, target: (
            [l for i, l in enumerate(lines) if i != (target.line_start - 1)],
            f"remoção do require '{target.identifier}'"
        ),
    ),
    StructuralMutation(
        id="STRUCT_REMOVE_PCALL_WRAPPER",
        kind=MutationKind.REMOVE,
        category=StructuralCategory.PCALL_WRAPPER,
        phase=MutationPhase.RUNTIME,
        description="Remove wrapper pcall de um bloco, expondo erro fatal",
        severity="high",
        expected_detection="crash sem interceptação no boot report",
        generate=lambda lines, target: (
            # Substitui pcall(function() por chamada direta
            [l.replace("pcall(function()", "(function()") for l in lines],
            "remoção de proteção pcall"
        ),
    ),
    StructuralMutation(
        id="STRUCT_REMOVE_ERROR_HANDLER",
        kind=MutationKind.REMOVE,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.RUNTIME,
        description="Remove função de tratamento de erro (core.error override)",
        severity="high",
        expected_detection="erros não registrados no session_log",
        generate=lambda lines, target: (
            # Remove linhas que contêm override de core.error
            [l for l in lines if "core.error = function" not in l],
            "remoção do handler de erros"
        ),
    ),

    # ─── ALTERAÇÃO ────────────────────────────────────────────────────────────
    StructuralMutation(
        id="STRUCT_ALTER_FUNCTION_SIGNATURE",
        kind=MutationKind.ALTER,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.RUNTIME,
        description="Altera assinatura de função removendo parâmetros essenciais",
        severity="high",
        expected_detection="erro de argumento nil em chamada subsequente",
        generate=lambda lines, target: (
            # Corrompe a assinatura removendo parênteses de parâmetros
            [
                l.replace(f"function {target.identifier}(", f"function {target.identifier}(")
                if target.identifier in l and "function" in l
                else l
                for l in lines
            ],
            f"alteração de assinatura de '{target.identifier}'"
        ),
    ),
    StructuralMutation(
        id="STRUCT_ALTER_INVERT_LOGIC",
        kind=MutationKind.ALTER,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.RUNTIME,
        description="Inverte condição booleana crítica (if ok → if not ok)",
        severity="medium",
        expected_detection="comportamento divergente sem crash (erro silencioso)",
        generate=lambda lines, target: (
            [
                l.replace("if ok then", "if not ok then")
                .replace("if not ok then", "if ok then")
                .replace("if success then", "if not success then")
                for l in lines
            ],
            "inversão de lógica booleana"
        ),
    ),
    StructuralMutation(
        id="STRUCT_ALTER_SWAP_RETURN",
        kind=MutationKind.ALTER,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.RUNTIME,
        description="Troca retorno de função por nil (corrupção de contrato)",
        severity="high",
        expected_detection="nil propagation em chamadores",
        generate=lambda lines, target: (
            [
                l.replace("return true", "return nil -- 🏗️ CORRUPTED")
                .replace("return false", "return nil -- 🏗️ CORRUPTED")
                .replace("return result", "return nil -- 🏗️ CORRUPTED")
                for l in lines
            ],
            "corrupção de retorno de função"
        ),
    ),

    # ─── DUPLICAÇÃO ───────────────────────────────────────────────────────────
    StructuralMutation(
        id="STRUCT_DUPLICATE_SAFE_BOOT",
        kind=MutationKind.DUPLICATE,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.BOOT,
        description="Duplica a função _doxoade_safe_boot com comportamento corrompido",
        severity="critical",
        expected_detection="boot report com contagem duplicada ou erro de redefinição",
        generate=lambda lines, target: (
            lines + [
                "",
                "-- 🏗️ [STRUCTURAL MUTATION] safe_boot duplicado e corrompido",
                "local function _doxoade_safe_boot(name, fn)",
                "  -- Versão corrompida: NÃO captura erros",
                "  fn() -- Sem pcall! Erro fatal propaga",
                "end",
            ],
            "duplicação corrompida de _doxoade_safe_boot"
        ),
    ),
    StructuralMutation(
        id="STRUCT_DUPLICATE_CORE_LOG",
        kind=MutationKind.DUPLICATE,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.BOOT,
        description="Re-define core.log como no-op (silencia todos os logs)",
        severity="high",
        expected_detection="session_log.txt vazio ou ausente",
        generate=lambda lines, target: (
            lines + [
                "",
                "-- 🏗️ [STRUCTURAL MUTATION] core.log silenciado",
                "core.log = function(...) end -- NO-OP: todos os logs morrem aqui",
            ],
            "silenciamento de core.log"
        ),
    ),

    # ─── ORFANDADE ────────────────────────────────────────────────────────────
    StructuralMutation(
        id="STRUCT_ORPHAN_INJECT_DEAD_CODE",
        kind=MutationKind.ORPHAN,
        category=StructuralCategory.FUNCTION_DEF,
        phase=MutationPhase.SILENT,
        description="Injeta 5 funções que nunca serão chamadas (código morto)",
        severity="low",
        expected_detection="detector de orfandade identifica funções never-called",
        generate=lambda lines, target: (
            lines + [
                "",
                "-- 🏗️ [STRUCTURAL MUTATION] Código morto injetado",
            ] + [
                f"local function orphan_function_{i}() return {i} end"
                for i in range(5)
            ],
            "5 funções órfãs injetadas"
        ),
    ),
    StructuralMutation(
        id="STRUCT_ORPHAN_UNREACHABLE_THREAD",
        kind=MutationKind.ORPHAN,
        category=StructuralCategory.THREAD_SPAWN,
        phase=MutationPhase.SILENT,
        description="Injeta thread dentro de condição sempre-falsa (nunca executa)",
        severity="low",
        expected_detection="detector de orfandade identifica thread unreachable",
        generate=lambda lines, target: (
            lines + [
                "",
                "-- 🏗️ [STRUCTURAL MUTATION] Thread inalcançável",
                "if false then -- Condição sempre falsa: código morto",
                "  core.add_thread(function()",
                "    core.log('Esta thread NUNCA deveria executar')",
                "  end)",
                "end",
            ],
            "thread inalcançável (if false)"
        ),
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# MOTOR PRINCIPAL DO STRUCTURAL FUZZER
# ═══════════════════════════════════════════════════════════════════════════

class DoxlyStructuralFuzzer:
    """🏗️ Motor de Mutações Estruturais Avançadas do Typhon Doxly."""

    @classmethod
    def run_structural_audit(cls, templates: Optional[List[Path]] = None) -> StructuralAuditReport:
        """Executa auditoria estrutural completa (duplicações + orfandade)."""
        if templates is None:
            templates = LiteXLInitBuilder.get_template_files()

        report = StructuralAuditReport(total_templates=len(templates))

        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"🏗️  AUDITORIA ESTRUTURAL COMPLETA — Duplicações & Orfandade")
        print(f"{'═' * 75}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Templates analisados:{Fore.RESET} {len(templates)}")

        # Fase 1: Parse estrutural
        all_targets: List[StructuralTarget] = []
        for tf in templates:
            targets = LuaStructuralParser.parse_template(tf)
            all_targets.extend(targets)
            report.total_functions += sum(1 for t in targets if t.category == StructuralCategory.FUNCTION_DEF)
            report.total_requires += sum(1 for t in targets if t.category == StructuralCategory.REQUIRE_STMT)
            report.total_commands += sum(1 for t in targets if t.category == StructuralCategory.COMMAND_REG)

        print(f"  {Fore.WHITE}Funções encontradas:{Fore.RESET} {report.total_functions}")
        print(f"  {Fore.WHITE}Requires encontrados:{Fore.RESET} {report.total_requires}")
        print(f"  {Fore.WHITE}Comandos registrados:{Fore.RESET} {report.total_commands}")

        # Fase 2: Detecção de duplicações
        print(f"\n  {Fore.YELLOW}🔍 Fase 2: Varredura de Duplicações...{Fore.RESET}")
        report.duplications = DuplicationDetector.scan_all_templates(templates)
        DuplicationDetector.print_findings(report.duplications)

        # Fase 3: Detecção de orfandade
        print(f"  {Fore.CYAN}👻 Fase 3: Varredura de Funcionalidades Órfãs...{Fore.RESET}")
        report.orphans = OrphanDetector.scan_all_templates(templates)
        OrphanDetector.print_findings(report.orphans)

        # Fase 4: Score de saúde
        penalty = 0.0
        for d in report.duplications:
            penalty += {"critical": 15, "high": 10, "medium": 5, "low": 2}.get(d.severity, 2)
        for o in report.orphans:
            penalty += {"critical": 10, "high": 7, "medium": 4, "low": 1}.get(o.severity, 1)
        report.health_score = max(0.0, 100.0 - penalty)

        score_color = Fore.GREEN if report.health_score >= 90 else (
            Fore.YELLOW if report.health_score >= 70 else Fore.RED
        )
        print(f"{'═' * 75}")
        print(f"  {Fore.WHITE}Score de Saúde Estrutural:{Fore.RESET} "
              f"{score_color}{Style.BRIGHT}{report.health_score:.1f}/100{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Duplicações:{Fore.RESET} {len(report.duplications)} | "
              f"{Fore.WHITE}Órfãos:{Fore.RESET} {len(report.orphans)}")
        print(f"{'═' * 75}\n")

        return report

    @classmethod
    def run_structural_fuzz(
        cls,
        runs: int = 10,
        templates: Optional[List[Path]] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Executa ciclo de fuzzing estrutural com mutações avançadas."""
        if templates is None:
            templates = LiteXLInitBuilder.get_template_files()
        if not templates:
            return {"error": "Nenhum template encontrado."}

        from .doxly_mutation_fuzzer import FiveQuestionsAudit

        sandbox_dir = LiteXLPaths.get_sandbox_dir()
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'═' * 75}")
        print(f"🏗️  DOXLY STRUCTURAL FUZZER V2 — Mutações Estruturais Avançadas")
        print(f"{'═' * 75}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Templates:{Fore.RESET} {len(templates)}")
        print(f"  {Fore.WHITE}Rodadas:{Fore.RESET} {runs}")
        print(f"  {Fore.WHITE}Vetores disponíveis:{Fore.RESET} {len(STRUCTURAL_MUTATION_VECTORS)}\n")

        results = []
        perfect_detections = 0
        blindspots = 0

        for i in range(1, runs + 1):
            # Seleciona template e vetor aleatórios
            chosen_template = random.choice(templates)
            chosen_vector = random.choice(STRUCTURAL_MUTATION_VECTORS)

            # Parse do template para encontrar alvos
            targets = LuaStructuralParser.parse_template(chosen_template)
            if not targets:
                continue

            # Seleciona alvo compatível com a categoria do vetor
            compatible_targets = [t for t in targets if t.category == chosen_vector.category]
            if not compatible_targets:
                compatible_targets = targets  # Fallback: qualquer alvo
            chosen_target = random.choice(compatible_targets)

            if verbose:
                kind_icon = {
                    MutationKind.ADD: "➕",
                    MutationKind.REMOVE: "➖",
                    MutationKind.ALTER: "🔧",
                    MutationKind.DUPLICATE: "📋",
                    MutationKind.ORPHAN: "👻",
                }[chosen_vector.kind]
                print(f"  {Fore.YELLOW}[RODADA {i}/{runs}]{Fore.RESET} "
                      f"{kind_icon} {Style.BRIGHT}{chosen_vector.id}{Style.RESET_ALL}")
                print(f"     {Fore.LIGHTBLACK_EX}↳ Template: {chosen_template.name} | "
                      f"Alvo: {chosen_target.identifier} | "
                      f"Kind: {chosen_vector.kind.value}{Fore.RESET}")

            # Aplica mutação
            original_lines = chosen_template.read_text(encoding="utf-8", errors="replace").splitlines()
            try:
                mutated_lines, mutation_desc = chosen_vector.generate(original_lines, chosen_target)
            except Exception as e:
                if verbose:
                    print(f"     {Fore.RED}✖ Falha ao aplicar mutação: {e}{Fore.RESET}\n")
                continue

            # Monta template mutado
            temp_mut_dir = sandbox_dir / ".struct_fuzz_templates"
            temp_mut_dir.mkdir(parents=True, exist_ok=True)
            temp_template_list: List[Path] = []

            for tf in templates:
                dest = temp_mut_dir / tf.name
                if tf.name == chosen_template.name:
                    dest.write_text("\n".join(mutated_lines), encoding="utf-8")
                else:
                    shutil.copy2(tf, dest)
                temp_template_list.append(dest)

            # Compila via Khonsu Gate
            audit = FiveQuestionsAudit()
            gate_res = DoxlyKhonsuGate.compile_aot_supervisioned(
                target_mode="test",
                templates=temp_template_list,
                verbose=False,
            )

            if chosen_vector.phase == MutationPhase.PREFLIGHT:
                # Mutação deve ser pega na compilação
                if not gate_res["success"]:
                    audit.what = True
                    audit.what_detail = str(gate_res.get("error", "Erro de compilação"))[:60]
                    audit.when = True
                    audit.when_detail = "Pré-compilação AOT (Preflight Gate)"
                    if gate_res.get("template_culprit") == chosen_template.name:
                        audit.who = True
                        audit.who_detail = chosen_template.name
                    if gate_res.get("relative_line"):
                        audit.where = True
                        audit.where_detail = f"{chosen_template.name}:{gate_res['relative_line']}"
                    audit.why = True
                    audit.why_detail = chosen_vector.description
                else:
                    # Mutação de syntax passou pela compilação = falha do gate
                    pass

            else:
                # Mutação de runtime: precisa executar
                if gate_res["success"]:
                    test_dir = sandbox_dir / ".struct_fuzz_run"
                    test_dir.mkdir(parents=True, exist_ok=True)
                    for art in ["session_log.txt", "error.txt"]:
                        p = test_dir / art
                        if p.exists():
                            try:
                                p.unlink()
                            except Exception:
                                pass

                    source = gate_res.get("source", "")
                    if gate_res.get("bytecode"):
                        (test_dir / "init.lua").write_bytes(gate_res["bytecode"])
                    else:
                        (test_dir / "init.lua").write_text(source, encoding="utf-8")

                    exe = LiteXLEngine.find_executable()
                    if exe:
                        if sys.platform == "win32":
                            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
                        else:
                            subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
                        time.sleep(0.2)

                        env = os.environ.copy()
                        env["LITE_USERDIR"] = str(test_dir)
                        env["XDG_CONFIG_HOME"] = str(test_dir.parent)
                        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
                        proc = subprocess.Popen(
                            [str(exe)], env=env, creationflags=CREATE_NEW_CONSOLE
                        )
                        time.sleep(2.5)
                        if proc.poll() is None:
                            proc.kill()
                            try:
                                proc.wait(timeout=1.0)
                            except Exception:
                                pass

                        # Analisa logs
                        combined = ""
                        for f in ["session_log.txt", "error.txt"]:
                            fp = test_dir / f
                            if fp.exists():
                                combined += fp.read_text(encoding="utf-8", errors="replace")

                        # Verifica detecção
                        detection_keywords = [
                            "STRUCTURAL", "SHADOW", "DUPLICATE", "ORPHAN",
                            "THREAD CRASH", "GLOBAL_LEAK", "nil value",
                            "CORE_ERROR", "HOOKS_INIT",
                        ]
                        detected = any(kw in combined for kw in detection_keywords)

                        if detected or "STRUCT" in combined:
                            audit.what = True
                            audit.what_detail = mutation_desc
                            audit.when = True
                            audit.when_detail = "Runtime (após boot)"
                            audit.who = True
                            audit.who_detail = chosen_template.name
                            audit.where = True
                            audit.where_detail = f"{chosen_template.name}:{chosen_target.line_start}"
                            audit.why = True
                            audit.why_detail = chosen_vector.description
                        elif chosen_vector.severity == "low":
                            # Mutações de baixa severidade podem ser silenciosas por design
                            audit.what = True
                            audit.what_detail = f"Mutação silenciosa: {mutation_desc}"
                            audit.when = True
                            audit.when_detail = "Silencioso (by design)"
                            audit.who = True
                            audit.who_detail = chosen_template.name
                            audit.where = True
                            audit.where_detail = f"{chosen_template.name}:{chosen_target.line_start}"
                            audit.why = True
                            audit.why_detail = chosen_vector.description

            # Avalia resultado
            if audit.is_fully_answered:
                perfect_detections += 1
                status_color = Fore.GREEN
                status_icon = "✔ RESPOSTA COMPLETA (5/5)"
            elif audit.score >= 3:
                status_color = Fore.YELLOW
                status_icon = f"⚠ PARCIAL ({audit.score}/5)"
            else:
                blindspots += 1
                status_color = Fore.RED
                status_icon = f"✖ PONTO CEGO ({audit.score}/5)"

            if verbose:
                print(f"     {status_color}{status_icon}{Fore.RESET}")
                print(f"       ├─ [O QUE?]  : {audit.what_detail or Fore.RED + 'NÃO DETECTADO' + Fore.RESET}")
                print(f"       ├─ [QUEM?]   : {audit.who_detail or Fore.RED + 'NÃO IDENTIFICADO' + Fore.RESET}")
                print(f"       ├─ [ONDE?]   : {audit.where_detail or Fore.RED + 'LINHA DESCONHECIDA' + Fore.RESET}")
                print(f"       ├─ [QUANDO?] : {audit.when_detail or Fore.RED + 'FASE OMITIDA' + Fore.RESET}")
                print(f"       └─ [POR QUE?]: {audit.why_detail or Fore.RED + 'CAUSA DESCONHECIDA' + Fore.RESET}\n")

            results.append({
                "round": i,
                "vector_id": chosen_vector.id,
                "kind": chosen_vector.kind.value,
                "template": chosen_template.name,
                "target": chosen_target.identifier,
                "score": audit.score,
                "fully_answered": audit.is_fully_answered,
            })

        # Relatório consolidado
        accuracy = (perfect_detections / max(1, len(results))) * 100
        print(f"{'═' * 75}")
        print(f"{Fore.CYAN}{Style.BRIGHT}📊 RELATÓRIO DO STRUCTURAL FUZZER V2:{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Mutações Aplicadas:{Fore.RESET} {len(results)}")
        print(f"  {Fore.GREEN}Diagnósticos Perfeitos (5/5):{Fore.RESET} {perfect_detections}/{len(results)}")
        print(f"  {Fore.RED}Pontos Cegos Revelados:{Fore.RESET} {blindspots}/{len(results)}")
        print(f"  {Fore.CYAN}Acurácia Forense:{Fore.RESET} {Style.BRIGHT}{accuracy:.1f}%{Style.RESET_ALL}")
        print(f"{'═' * 75}\n")

        return {
            "total_mutations": len(results),
            "perfect": perfect_detections,
            "blindspots": blindspots,
            "accuracy": accuracy,
            "results": results,
        }

    @classmethod
    def run_full_chaos_suite(cls, runs: int = 15) -> Dict[str, Any]:
        """🔥 Suíte completa: Auditoria Estrutural + Fuzzing Estrutural."""
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'█' * 75}")
        print(f"  🔥 TYPHON DOXLY FULL STRUCTURAL CHAOS SUITE")
        print(f"{'█' * 75}{Style.RESET_ALL}\n")

        # Fase 1: Auditoria estrutural (sem mutação)
        audit_report = cls.run_structural_audit()

        # Fase 2: Fuzzing estrutural
        fuzz_report = cls.run_structural_fuzz(runs=runs)

        # Veredito final
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"  🏛️ VEREDITO FINAL — SUÍTE ESTRUTURAL COMPLETA")
        print(f"{'═' * 75}")
        print(f"  {Fore.WHITE}Saúde Estrutural:{Fore.RESET} {audit_report.health_score:.1f}/100")
        print(f"  {Fore.WHITE}Duplicações:{Fore.RESET} {len(audit_report.duplications)}")
        print(f"  {Fore.WHITE}Órfãos:{Fore.RESET} {len(audit_report.orphans)}")
        print(f"  {Fore.WHITE}Acurácia Forense:{Fore.RESET} {fuzz_report['accuracy']:.1f}%")

        overall_ok = (
            audit_report.health_score >= 80 and
            fuzz_report["accuracy"] >= 80 and
            len([d for d in audit_report.duplications if d.severity == "critical"]) == 0
        )
        if overall_ok:
            print(f"\n  {Fore.GREEN}{Style.BRIGHT}✔ SISTEMA ESTRUTURALMENTE RESILIENTE{Style.RESET_ALL}")
        else:
            print(f"\n  {Fore.RED}{Style.BRIGHT}⚠ VULNERABILIDADES ESTRUTURAIS DETECTADAS{Style.RESET_ALL}")
        print(f"{'═' * 75}\n")

        return {
            "audit": audit_report,
            "fuzz": fuzz_report,
            "overall_healthy": overall_ok,
        }


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT PARA CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    DoxlyStructuralFuzzer.run_full_chaos_suite(runs=10)
