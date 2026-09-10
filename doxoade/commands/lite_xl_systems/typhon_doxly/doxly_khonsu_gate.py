# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_khonsu_gate.py
# -*- coding: utf-8 -*-
"""
Khonsu AOT Compiler Gatekeeper & Template Source Map (Typhon Doxly Edition - V2.4 Zero-Freeze Staging).
Implementa montagem unificada escalonada com proteção de frame zero para o SDL2.
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

# Módulos pesados que são deferidos para não bloquear a criação da janela gráfica
DEFERRED_STAGE_TEMPLATES = {
    "10_forensic_engine.lua": 0.20,
    "14_doxnote_panel.lua": 0.35,
    "15_audit_highlighter.lua": 0.45,
    "16_open_editors_dock.lua": 0.60,
    "17_khonsu_coroutine.lua": 0.70,
    "18_search_results_dock.lua": 0.85,
    "19a_dox_image_inline.lua": 0.90,
    "19b_terminal_console.lua": 0.95,
    "19c_canvas_sdl2_studio.lua": 1.00,
    "19d_bottom_shelf_hub.lua": 1.05,
}

@dataclass
class TemplateSegment:
    name: str
    file_path: Path
    start_line: int
    end_line: int
    line_count: int

class TemplateSourceMap:
    def __init__(self) -> None:
        self.segments: List[TemplateSegment] = []

    def register(self, name: str, file_path: Path, start_line: int, line_count: int) -> None:
        end_line = start_line + line_count - 1
        self.segments.append(TemplateSegment(name, file_path, start_line, end_line, line_count))

    def resolve(self, unified_line: int) -> Tuple[Optional[str], Optional[Path], int]:
        for seg in self.segments:
            if seg.start_line <= unified_line <= (seg.end_line + 1):
                relative_line = min(seg.line_count, max(1, unified_line - seg.start_line + 1))
                return seg.name, seg.file_path, relative_line
        return None, None, unified_line

    # def resolve(self, unified_line: int) -> Tuple[Optional[str], Optional[Path], int]:
    #     """
    #     Traduz o número de linha do buffer unificado para (nome_template, caminho, linha_relativa).
    #     Possui tolerância para erros capturados no fechamento do wrapper (end)).
    #     """
    #     for seg in self.segments:
    #         # Tolerância de +1 linha para capturar erros de bloco não fechado no 'end)'
    #         if seg.start_line <= unified_line <= (seg.end_line + 1):
    #             relative_line = min(seg.line_count, max(1, unified_line - seg.start_line + 1))
    #             return seg.name, seg.file_path, relative_line

    #     # Fallback de proximidade mais próxima caso caia em comentários divisores
    #     closest_seg = None
    #     min_dist = 999999
    #     for seg in self.segments:
    #         dist = min(abs(unified_line - seg.start_line), abs(unified_line - seg.end_line))
    #         if dist < min_dist:
    #             min_dist = dist
    #             closest_seg = seg

    #     if closest_seg and min_dist <= 2:
    #         relative_line = min(closest_seg.line_count, max(1, unified_line - closest_seg.start_line + 1))
    #         return closest_seg.name, closest_seg.file_path, relative_line

    #     return None, None, unified_line

class DoxlyKhonsuGate:
    """Portão de Validação e Compilação AOT Supervisionada do Khonsu."""

    @classmethod
    def assemble_unified_buffer(cls, templates: List[Path]) -> Tuple[str, TemplateSourceMap]:
        source_map = TemplateSourceMap()
        buffer_lines: List[str] = [
            "-- =============================================================================",
            "-- DOXOADE SOVEREIGN INIT — KHONSU AOT UNIFIED RUNTIME (STAGED ZERO-FREEZE)",
            f"-- Compilado em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "-- =============================================================================",
            "",
            'local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)',
            "",
            "rawset(_G, '_DOXOADE_BOOT_REPORT', { total = 0, passed = 0, failed = 0, quarantined = 0, modules = {} })",
            "local function _doxoade_safe_boot(name, fn)",
            "  local report = rawget(_G, '_DOXOADE_BOOT_REPORT')",
            "  report.total = report.total + 1",
            "  local t0 = os.clock()",
            "  local mem0 = collectgarbage('count')",
            "  local ok, err = pcall(fn)",
            "  local elapsed_ms = (os.clock() - t0) * 1000",
            "  local mem_delta_kb = math.max(0, collectgarbage('count') - mem0)",
            "  if ok then",
            "    report.passed = report.passed + 1",
            "  else",
            "    report.failed = report.failed + 1",
            "    if core and core.error then",
            "      core.error(string.format(\"[DOXOADE BOOT] Módulo '%s' falhou: %s\", name, err))",
            "    end",
            "  end",
            "  table.insert(report.modules, {",
            "    name = name,",
            "    status = ok and 'PASS' or 'FAIL',",
            "    time_ms = math.floor(elapsed_ms * 100) / 100,",
            "    mem_kb = math.floor(mem_delta_kb * 10) / 10,",
            "    error = err and tostring(err) or nil",
            "  })",
            "end",
            "",
            "local function _doxoade_staged_boot(name, delay_sec, fn)",
            "  if core and core.add_thread then",
            "    core.add_thread(function()",
            "      if delay_sec and delay_sec > 0 then coroutine.yield(delay_sec) end",
            "      _doxoade_safe_boot(name, fn)",
            "    end)",
            "  else",
            "    _doxoade_safe_boot(name, fn)",
            "  end",
            "end",
            "",
        ]

        for tf in templates:
            content = tf.read_text(encoding="utf-8", errors="replace")
            content_lines = content.splitlines()
            header_comment = f"-- >>> [TEMPLATE: {tf.name}] >>>"
            
            # Aplica staging assíncrono para templates secundários pesados
            if tf.name in DEFERRED_STAGE_TEMPLATES:
                delay = DEFERRED_STAGE_TEMPLATES[tf.name]
                boot_open = f'_doxoade_staged_boot("{tf.name}", {delay}, function()'
            else:
                boot_open = f'_doxoade_safe_boot("{tf.name}", function()'

            buffer_lines.append(header_comment)
            buffer_lines.append(boot_open)
            code_start_line = len(buffer_lines) + 1
            buffer_lines.extend(content_lines)
            source_map.register(tf.name, tf, code_start_line, len(content_lines))
            buffer_lines.append("end)")
            buffer_lines.append(f"-- <<< [END TEMPLATE: {tf.name}] <<<")
            buffer_lines.append("")

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
        """Executa a compilação AOT com Pre-Flight Gatekeeper, Source Map e Triangulação."""
        from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths

        if templates is None:
            templates = LiteXLInitBuilder.get_template_files()

        if verbose:
            print(f"{Fore.CYAN}🛡️  [KHONSU GATE] Montando buffer unificado com Source Map ({len(templates)} templates)...{Fore.RESET}")

        unified_source, source_map = cls.assemble_unified_buffer(templates)
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
        temp_dir = LiteXLPaths.get_sandbox_dir() / ".khonsu_preflight"
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_lua = temp_dir / "khonsu_aot.lua"
        temp_out = temp_dir / "khonsu_aot.luac"
        temp_lua.write_text(unified_source, encoding="utf-8")

        posix_src = temp_lua.as_posix()
        posix_out = temp_out.as_posix()

        compile_cmd = [
            str(lua_exe),
            "-e",
            f'local f, err = loadfile("{posix_src}"); '
            f'if not f then io.stderr:write("LOADFILE_ERR: " .. tostring(err)); os.exit(1) end; '
            f'local dump_ok, code = pcall(string.dump, f); '
            f'if not dump_ok then io.stderr:write("DUMP_ERR: " .. tostring(code)); os.exit(2) end; '
            f'local out = io.open("{posix_out}", "wb"); '
            f'if not out then io.stderr:write("WRITE_ERR: cannot open output file"); os.exit(3) end; '
            f'out:write(code); out:flush(); out:close();'
        ]

        res = subprocess.run(compile_cmd, capture_output=True, text=True)

        if res.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 0:
            bytecode_bytes = temp_out.read_bytes()
            if verbose:
                print(f"{Fore.GREEN}✔ [KHONSU GATE] Compilação AOT Bytecode 100% Validada ({len(bytecode_bytes):,} bytes | {lua_version}).{Fore.RESET}")
            temp_lua.unlink(missing_ok=True)
            temp_out.unlink(missing_ok=True)
            return {
                "success": True,
                "opt_mode": "bytecode",
                "source": unified_source,
                "bytecode": bytecode_bytes,
                "error": None,
            }

        raw_error = res.stderr.strip() or "Erro de compilação AOT desconhecido"

        diag_log = LiteXLPaths.get_user_dir() / ".doxoade" / "diagnostics" / "khonsu_compile_error.log"
        try:
            diag_log.parent.mkdir(parents=True, exist_ok=True)
            diag_log.write_text(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n{raw_error}\n", encoding="utf-8")
        except Exception:
            pass

        # Extrai a linha do arquivo unificado (suporta formatos do Lua 5.4)
        match = re.search(r"(?:khonsu_aot\.lua|string):(\d+):\s*(.*)", raw_error)
        if not match:
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
