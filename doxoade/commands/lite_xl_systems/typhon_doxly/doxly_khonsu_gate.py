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

SHADOW_WEIGHTS = {
    "00_header_and_logger.lua": 0.0,
    "00_01_api_probe.lua": 0.1,
    "00_02_api_guard.lua": 0.1,
    "01_ipc_dispatcher.lua": 0.2,
    "04_color_and_search_highlight.lua": 0.3,
    "10_forensic_engine.lua": 0.6,      # Pesado: Telemetria
    "15_audit_highlighter.lua": 0.7,    # Pesado: I/O de arquivo
    "16_open_editors_dock.lua": 0.8,    # Luxo: UI
    "19b_terminal_console.lua": 0.9,    # Luxo: Terminal
    "19c_canvas_sdl2_studio.lua": 0.95, # Luxo: Canvas
    "19d_bottom_shelf_hub.lua": 1.0,    # Luxo: Hub
}

def generate_shadow_boot_call(template_name: str) -> str:
    weight = SHADOW_WEIGHTS.get(template_name, 0.5)
    if weight <= 0.3:
        return f'_doxoade_safe_boot("{template_name}", function()'
    else:
        return f'_doxoade_shadow_boot("{template_name}", {weight}, function()'

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

def resolve_compiler_error_to_template(error_msg: str, source_map, templates_dir: Path) -> str:
    """
    🔍 TRADUTOR DE ERROS: Converte 'init.lua:1535: erro' em '01_ipc_dispatcher.lua:42: erro'
    """
    # Tenta encontrar "init.lua:NUMERO" ou "algo.lua:NUMERO" na mensagem de erro
    match = re.search(r"(?:init\.lua|khonsu_aot\.lua):(\d+):", error_msg)
    if not match:
        # Fallback: tenta achar qualquer número de linha no erro
        match = re.search(r":(\d+):", error_msg)
        
    if not match:
        return f"{Fore.RED}✖ Erro de compilação não mapeável:\n{error_msg}{Fore.RESET}"

    unified_line = int(match.group(1))
    
    # Usa o Source Map para encontrar o arquivo original
    template_name, template_path, original_line = source_map.resolve(unified_line)

    if not template_path or not template_path.exists():
        return (
            f"{Fore.RED}✖ Erro na linha {unified_line} do init.lua unificado, "
            f"mas o mapeamento para o template falhou.{Fore.RESET}\n"
            f"Erro bruto: {error_msg}"
        )

    # Extrai o snippet do arquivo original
    try:
        lines = template_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, original_line - 3)
        end = min(len(lines), original_line + 2)
        
        snippet_lines = []
        for i in range(start, end):
            prefix = f"{Fore.RED} >> {Fore.RESET}" if i == original_line else "    "
            line_num = f"{Fore.YELLOW}{i + 1:4d}{Fore.RESET}"
            snippet_lines.append(f"{prefix}{line_num} | {lines[i]}")
            
        snippet = "\n".join(snippet_lines)
    except Exception:
        snippet = f"{Fore.YELLOW}  [Falha ao ler o snippet do arquivo]{Fore.RESET}"

    # Limpa a mensagem de erro para exibição
    clean_error = error_msg.split(":", 2)[-1].strip() if ":" in error_msg else error_msg

    return (
        f"\n{Fore.RED}{Style.BRIGHT}🚨 ERRO DE SINTAXE DETECTADO NO TEMPLATE{Style.RESET_ALL}"
        f"\n  {Fore.WHITE}📄 Arquivo:{Fore.RESET} {Fore.CYAN}{template_name}{Fore.RESET}"
        f"\n  {Fore.WHITE}📍 Linha Original:{Fore.RESET} {Fore.YELLOW}{original_line}{Fore.RESET} (Linha {unified_line} no init.lua unificado)"
        f"\n  {Fore.WHITE}⚠️ Mensagem:{Fore.RESET} {Fore.LIGHTRED_EX}{clean_error}{Fore.RESET}"
        f"\n\n  {Fore.WHITE}Trecho do código:{Fore.RESET}"
        f"\n{snippet}\n"
        f"{Fore.RED}{'─' * 75}{Fore.RESET}\n"
    )

class DoxlyKhonsuGate:
    """Portão de Validação e Compilação AOT Supervisionada do Khonsu."""

    # ✅ CORREÇÃO: Dicionário movido para DENTRO da classe como atributo de classe
   # DEFERRED_STAGE_TEMPLATES = {
   #    "10_forensic_engine.lua": 0.15,
   #    "14_doxnote_panel.lua": 0.30,
   #    "15_audit_highlighter.lua": 0.45,
   #    "16_open_editors_dock.lua": 0.60,
   #    "17_khonsu_coroutine.lua": 0.75,
   #    "18_search_results_dock.lua": 0.85,
   #    "19a_dox_image_inline.lua": 0.90,
   #    "19b_terminal_console.lua": 0.95,
   #    "19c_canvas_sdl2_studio.lua": 1.00,
   #    "19d_bottom_shelf_hub.lua": 1.05,
   #    "20_split_comparator_and_tools.lua": 1.10,
   # }
    DEFERRED_STAGE_TEMPLATES = {}
    
    @classmethod
    def resolve_unified_trace(cls, raw_file: str, line_no: int) -> Tuple[Path, int, str]:
        """
        🧭 SOURCE MAP RESOLVER: Mapeia uma linha do buffer compilado (khonsu_aot.lua ou init.lua)
        de volta para o arquivo de template .lua original e sua linha relativa.
        Retorna: (caminho_do_template, linha_relativa, nome_do_template)
        """
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        t_dir = LiteXLPaths.get_template_dir()
        templates = sorted([t for t in t_dir.glob("*.lua") if t.is_file()])
        
        # Se o arquivo citado já for um template real existente no disco:
        target_path = Path(raw_file)
        if target_path.exists() and target_path.suffix == ".lua":
            return target_path, line_no, target_path.name

        # Caso contrário, reconstruímos o Source Map para localizar a fatia exata
        _, source_map = cls.assemble_unified_buffer(templates)
        name, file_path, rel_line = source_map.resolve(line_no)
        
        if file_path and file_path.exists():
            return file_path, rel_line, name or file_path.name
        
        return target_path, line_no, raw_file

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
            "rawset(_G, '_CURRENT_BOOT_MODULE', 'init')",
            "",
            "-- Hook para o Ghost Tracer saber qual módulo está carregando",
            "rawset(_G, '_DOXOADE_SET_CURRENT_MODULE', function(name)",
            "  rawset(_G, '_CURRENT_BOOT_MODULE', name)",
            "end)",
            "",
            "local function _doxoade_safe_boot(name, fn)",
            "  rawset(_G, '_DOXOADE_SET_CURRENT_MODULE', name)",
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
            
            # ✅ Agora acessa corretamente via cls.
            if tf.name in cls.DEFERRED_STAGE_TEMPLATES:
                delay = cls.DEFERRED_STAGE_TEMPLATES[tf.name]
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

        map_lines = ["rawset(_G, '_DOXOADE_SOURCE_MAP', {"]
        for seg in source_map.segments:
            map_lines.append(f'  {{ name = "{seg.name}", start_line = {seg.start_line}, end_line = {seg.end_line} }},')
        map_lines.append("})\n")
        buffer_lines.extend(map_lines)
        
        unified_source = "\n".join(buffer_lines)
        
        # 💾 Snapshot Persistente para o mody show não dar "does not exist":
        try:
            from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
            diag_dir = LiteXLPaths.get_user_dir() / ".doxoade" / "diagnostics"
            diag_dir.mkdir(parents=True, exist_ok=True)
            (diag_dir / "last_preflight_aot.lua").write_text(unified_source, encoding="utf-8")
        except Exception:
            pass

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
        target_mode: str = "test",
        templates: Optional[List[Path]] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Compilação AOT supervisionada com Mapeador Forense de Erros.
        Retorna dict com: success, source, error, template_culprit, relative_line, snippet
        """
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        
        if templates is None:
            t_dir = LiteXLPaths.get_template_dir()
            templates = sorted([t for t in t_dir.glob("*.lua") if t.is_file()])
        
        # 1. Monta o buffer unificado com Source Map
        unified_source, source_map = cls.assemble_unified_buffer(templates)
        
        # 2. Validação estática rápida (scanner de balanceamento)
        from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
        scan_errors = LiteXLInitBuilder.compile_scan_lua(unified_source)
        if scan_errors:
            # Tenta mapear o primeiro erro via Source Map
            first_err = scan_errors[0]
            mapped = cls._resolve_scan_error(first_err, source_map, templates)
            return {
                "success": False,
                "error": mapped["display"],
                "raw_error": first_err,
                "template_culprit": mapped.get("template"),
                "relative_line": mapped.get("line"),
                "snippet": mapped.get("snippet"),
                "source": unified_source,
            }
        
        # 3. Compilação AOT real (se houver runtime Lua)
        lua_info = LiteXLPaths.lua_runtime_info()
        if not lua_info:
            return {
                "success": True,
                "source": unified_source,
                "opt_mode": "plain_no_runtime",
            }
        
        lua_exe, lua_version = lua_info
        
        # Grava em arquivo temporário para compilação
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".lua", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(unified_source)
            tmp_path = Path(tmp.name)
        
        try:
            # Compila para bytecode (validação real)
            result = subprocess.run(
                [lua_exe, "-e", f"local f, err = loadfile({repr(str(tmp_path))}); if not f then io.stderr:write(tostring(err)); os.exit(1) end"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            
            if result.returncode != 0:
                raw_error = result.stderr.strip()
                # 🧩 MÁGICA: Traduz init.lua:L1535 → 01_ipc_dispatcher.lua:42
                mapped = cls._resolve_compiler_error(raw_error, source_map, templates)
                
                if verbose:
                    print(f"\n{Fore.RED}{Style.BRIGHT}🚨 ERRO DE COMPILAÇÃO AOT DETECTADO{Style.RESET_ALL}")
                    print(mapped["display"])
                
                return {
                    "success": False,
                    "error": mapped["display"],
                    "raw_error": raw_error,
                    "template_culprit": mapped.get("template"),
                    "relative_line": mapped.get("line"),
                    "snippet": mapped.get("snippet"),
                    "source": unified_source,
                }
            
            # Sucesso: lê o bytecode gerado
            bytecode_path = tmp_path.with_suffix(".luac")
            subprocess.run(
                [lua_exe, "-e", f"local f = assert(loadfile({repr(str(tmp_path))})); local bf = io.open({repr(str(bytecode_path))}, 'wb'); bf:write(string.dump(f)); bf:close()"],
                capture_output=True,
                timeout=10,
            )
            
            bytecode = bytecode_path.read_bytes() if bytecode_path.exists() else b""
            
            if verbose:
                print(f"{Fore.GREEN}✔ [KHONSU GATE] Compilação AOT Bytecode 100% Validada "
                      f"({len(bytecode):,} bytes | {lua_version}).{Fore.RESET}")
            
            return {
                "success": True,
                "source": unified_source,
                "bytecode": bytecode,
                "opt_mode": "bytecode",
                "lua_version": lua_version,
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout na compilação AOT (>10s)",
                "source": unified_source,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Falha inesperada na compilação: {e}",
                "source": unified_source,
            }
        finally:
            tmp_path.unlink(missing_ok=True)
            tmp_path.with_suffix(".luac").unlink(missing_ok=True)


    # =============================================================================
    # 🧩 MAPEADOR FORENSE DE ERROS (Apolo UX)
    # =============================================================================
    @classmethod
    def _resolve_compiler_error(
        cls,
        error_msg: str,
        source_map: "TemplateSourceMap",
        templates: List[Path],
    ) -> Dict[str, Any]:
        """
        Traduz 'init.lua:1535: cannot use ...' em '01_ipc_dispatcher.lua:42: cannot use ...'
        com snippet do código original.
        """
        # Extrai número da linha do init.lua unificado
        m = re.search(r"(?:init\.lua|khonsu_aot\.lua|tmp\w+\.lua):(\d+):", error_msg)
        if not m:
            m = re.search(r":(\d+):", error_msg)
        
        if not m:
            return {
                "display": f"{Fore.RED}✖ Erro de compilação não mapeável:\n{error_msg}{Fore.RESET}",
                "template": None,
                "line": 0,
                "snippet": "",
            }
        
        unified_line = int(m.group(1))
        template_name, template_path, original_line = source_map.resolve(unified_line)
        
        # Limpa a mensagem (remove prefixo de arquivo)
        clean_error = re.sub(r"^[^:]+:\d+:\s*", "", error_msg).strip()
        
        # Extrai snippet do arquivo original
        snippet = ""
        if template_path and template_path.exists():
            try:
                lines = template_path.read_text(encoding="utf-8", errors="replace").splitlines()
                # Pula comentários para encontrar código executável real
                target_line = original_line
                for offset in range(0, 8):
                    check = original_line + offset
                    if check <= len(lines):
                        content = lines[check - 1].strip()
                        if content and not content.startswith("--"):
                            target_line = check
                            break
                
                start = max(1, target_line - 2)
                end = min(len(lines), target_line + 2)
                snippet_lines = []
                for ln in range(start, end + 1):
                    prefix = f"{Fore.RED} >> {Fore.RESET}" if ln == target_line else "    "
                    num = f"{Fore.YELLOW}{ln:4d} |{Fore.RESET}"
                    snippet_lines.append(f"{prefix}{num} {lines[ln - 1]}")
                snippet = "\n".join(snippet_lines)
            except Exception:
                snippet = f"{Fore.YELLOW}  [Falha ao ler snippet]{Fore.RESET}"
        
        display = (
            f"\n{Fore.RED}{Style.BRIGHT}🚨 ERRO DE SINTAXE NO TEMPLATE{Style.RESET_ALL}"
            f"\n  {Fore.WHITE}📄 Arquivo:{Fore.RESET} {Fore.CYAN}{template_name or 'desconhecido'}{Fore.RESET}"
            f"\n  {Fore.WHITE}📍 Linha:{Fore.RESET} {Fore.YELLOW}{original_line}{Fore.RESET} "
            f"({Fore.LIGHTBLACK_EX}linha {unified_line} no init.lua unificado{Fore.RESET})"
            f"\n  {Fore.WHITE}⚠️ Erro:{Fore.RESET} {Fore.LIGHTRED_EX}{clean_error}{Fore.RESET}"
            f"\n\n  {Fore.WHITE}Trecho do código:{Fore.RESET}"
            f"\n{snippet}"
            f"\n{Fore.RED}{'─' * 75}{Fore.RESET}\n"
        )
        
        return {
            "display": display,
            "template": template_name,
            "line": original_line,
            "snippet": snippet,
        }


    @classmethod
    def _resolve_scan_error(
        cls,
        error_msg: str,
        source_map: "TemplateSourceMap",
        templates: List[Path],
    ) -> Dict[str, Any]:
        """Versão simplificada para erros do scanner estático (compile_scan_lua)."""
        return cls._resolve_compiler_error(error_msg, source_map, templates)
