# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_khonsu_gate.py
# -*- coding: utf-8 -*-
"""
Khonsu AOT Compiler Gatekeeper & Template Source Map (Typhon Doxly Edition).
Gerencia a pré-compilação AOT, mapeamento bidirecional de templates (Source Map)
e triangulação automática de erros de sintaxe antes do deploy em produção.
"""

from __future__ import annotations
import os
import re
import sys
import time
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

from .doxly_tree import DOXLY_TREE
from .doxly_triangulator import DoxlyTriangulator


@dataclass
class TemplateSegment:
    """Segmento mapeado de um template dentro do buffer unificado."""
    name: str
    file_path: Path
    start_line: int
    end_line: int
    line_count: int


class TemplateSourceMap:
    """Mapeador bidirecional de linhas do buffer unificado para o template original."""

    def __init__(self) -> None:
        self.segments: List[TemplateSegment] = []

    def register(self, name: str, file_path: Path, start_line: int, line_count: int) -> None:
        """Registra um template e seu intervalo de linhas no buffer unificado."""
        end_line = start_line + line_count - 1
        self.segments.append(TemplateSegment(name, file_path, start_line, end_line, line_count))

    def resolve(self, unified_line: int) -> Tuple[Optional[str], Optional[Path], int]:
        """Traduz o número de linha do buffer unificado para (nome_template, caminho, linha_relativa)."""
        for seg in self.segments:
            if seg.start_line <= unified_line <= seg.end_line:
                relative_line = unified_line - seg.start_line + 1
                return seg.name, seg.file_path, relative_line
        return None, None, unified_line


class DoxlyKhonsuGate:
    """Portão de Validação e Compilação AOT Supervisionada do Khonsu."""

    @classmethod
    def assemble_unified_buffer(cls, templates: List[Path]) -> Tuple[str, TemplateSourceMap]:
        """Monta o buffer soberano unificado gerando o Source Map linha a linha."""
        source_map = TemplateSourceMap()
        buffer_lines: List[str] = [
            "-- =============================================================================",
            "-- DOXOADE SOVEREIGN INIT — KHONSU AOT UNIFIED RUNTIME",
            f"-- Compilado em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "-- =============================================================================\n",
            'local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)',
            "",
            "rawset(_G, '_DOXOADE_BOOT_REPORT', { total = 0, passed = 0, failed = 0, quarantined = 0, modules = {} })",
            "local function _doxoade_safe_boot(name, fn)",
            "  local report = rawget(_G, '_DOXOADE_BOOT_REPORT')",
            "  report.total = report.total + 1",
            "  local t0 = os.clock()",
            "  local ok, err = pcall(fn)",
            "  local elapsed = os.clock() - t0",
            "  if ok then",
            "    report.passed = report.passed + 1",
            "  else",
            "    report.failed = report.failed + 1",
            "    table.insert(report.modules, { name = name, error = err, time = elapsed })",
            "    if core and core.error then",
            "      core.error(string.format(\"[DOXOADE BOOT] Módulo '%s' falhou: %s\", name, err))",
            "    end",
            "  end",
            "end",
            "",
        ]

        for tf in templates:
            content = tf.read_text(encoding="utf-8", errors="replace")
            content_lines = content.splitlines()

            header_comment = f"-- >>> [TEMPLATE: {tf.name}] >>>"
            boot_open = f'_doxoade_safe_boot("{tf.name}", function()'

            buffer_lines.append(header_comment)
            buffer_lines.append(boot_open)

            # O início do código real do template no buffer unificado
            code_start_line = len(buffer_lines) + 1
            buffer_lines.extend(content_lines)

            # Registra no Source Map
            source_map.register(tf.name, tf, code_start_line, len(content_lines))

            buffer_lines.append("end)")
            buffer_lines.append(f"-- <<< [END TEMPLATE: {tf.name}] <<<\n")

        unified_source = "\n".join(buffer_lines)
        return unified_source, source_map

    @classmethod
    def render_culprit_snippet(cls, file_path: Path, relative_line: int, radius: int = 3) -> None:
        """Renderiza snippet visual forense com destaque na linha culpada."""
        if not file_path.exists():
            return
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, relative_line - radius)
        end = min(len(lines), relative_line + radius)

        print(f"\n    {Fore.CYAN}┌─ [{file_path.name}:{relative_line}]{Fore.RESET}")
        for ln in range(start, end + 1):
            is_target = (ln == relative_line)
            prefix = f"{Fore.RED}>>{Fore.RESET}" if is_target else "  "
            color = Fore.YELLOW if is_target else Fore.WHITE
            print(f"    {prefix} {color}{ln:4d} | {lines[ln - 1]}{Fore.RESET}")
        print(f"    {Fore.CYAN}└{'─' * 60}{Fore.RESET}\n")

    @classmethod
    def compile_aot_supervisioned(
        cls,
        target_mode: str = "production",
        templates: Optional[List[Path]] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa a compilação AOT com Pre-Flight Gatekeeper, Source Map e Triangulação.
        Retorna o dicionário de status da compilação.
        """
        from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths

        if templates is None:
            templates = LiteXLInitBuilder.get_template_files()

        if verbose:
            print(f"{Fore.CYAN}🛡️  [KHONSU GATE] Montando buffer unificado com Source Map ({len(templates)} templates)...{Fore.RESET}")

        unified_source, source_map = cls.assemble_unified_buffer(templates)

        # 1. Checagem de Runtime Lua
        lua_info = LiteXLPaths.lua_runtime_info()
        if not lua_info:
            if verbose:
                print(f"{Fore.YELLOW}⚠ [KHONSU GATE] Runtime LuaC não detectado. Acionando Plano B (Minificação Segura).{Fore.RESET}")
            return {
                "success": True,
                "opt_mode": "minified_text",
                "source": unified_source,
                "bytecode": None,
                "error": None,
            }

        lua_exe, lua_version = lua_info

        # 2. Teste de Compilação AOT em Memória / Temp
        temp_dir = LiteXLPaths.get_sandbox_dir() / ".khonsu_preflight"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_lua = temp_dir / "khonsu_aot.lua"
        temp_out = temp_dir / "khonsu_aot.luac"

        temp_lua.write_text(unified_source, encoding="utf-8")

        # Invoca o compilador Lua nativo (luac ou lua -e "string.dump(loadfile(...))")
        compile_cmd = [
            str(lua_exe),
            "-e",
            f'local f, err = loadfile({repr(str(temp_lua))}); '
            f'if not f then io.stderr:write(tostring(err)); os.exit(1) end; '
            f'local out = io.open({repr(str(temp_out))}, "wb"); '
            f'out:write(string.dump(f)); out:close();'
        ]

        res = subprocess.run(compile_cmd, capture_output=True, text=True)

        # 3. Análise de Veredito da Compilação
        if res.returncode == 0 and temp_out.exists():
            bytecode_bytes = temp_out.read_bytes()
            if verbose:
                print(f"{Fore.GREEN}✔ [KHONSU GATE] Compilação AOT Bytecode 100% Validada ({len(bytecode_bytes):,} bytes | {lua_version}).{Fore.RESET}")

            # Limpeza
            temp_lua.unlink(missing_ok=True)
            temp_out.unlink(missing_ok=True)

            return {
                "success": True,
                "opt_mode": "bytecode",
                "source": unified_source,
                "bytecode": bytecode_bytes,
                "error": None,
            }

        # 4. TRIANGULAÇÃO AUTOMÁTICA DE ERRO DE COMPILAÇÃO (Plano de Resgate)
        raw_error = res.stderr.strip() or "Erro de compilação AOT desconhecido"

        # Extrai número de linha unificada do erro (ex: (khonsu_aot):546: <eof> expected near 'end')
        match = re.search(r":(\d+):\s*(.*)", raw_error)
        unified_line = int(match.group(1)) if match else 0
        err_msg = match.group(2) if match else raw_error

        template_name, template_path, relative_line = source_map.resolve(unified_line)

        print(f"\n{Fore.RED}{Style.BRIGHT}✖ [KHONSU GATE REJECT] Falha na Compilação AOT Bytecode!{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Erro do Compilador:{Fore.RESET} {Fore.LIGHTRED_EX}{err_msg}{Fore.RESET}")

        if template_name and template_path:
            print(f"  {Fore.WHITE}Template Culpado:{Fore.RESET} {Fore.CYAN}{template_name}{Fore.RESET} (Linha {relative_line})")
            cls.render_culprit_snippet(template_path, relative_line)
        else:
            print(f"  {Fore.WHITE}Linha Unificada:{Fore.RESET} {unified_line}")

        # Limpeza
        temp_lua.unlink(missing_ok=True)
        temp_out.unlink(missing_ok=True)

        return {
            "success": False,
            "opt_mode": "fallback_minified",
            "source": unified_source,
            "bytecode": None,
            "error": err_msg,
            "template_culprit": template_name,
            "relative_line": relative_line,
        }
