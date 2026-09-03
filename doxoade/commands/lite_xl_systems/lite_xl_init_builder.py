# doxoade/commands/lite_xl_systems/lite_xl_init_builder.py
"""
🔨 Hefesto — Geração e validação estática do init.lua (soberano e sandbox).
Parte do split de engine_lite_xl.py (God Class original V17.0) em módulos por responsabilidade.
"""
import os
import re
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""

from .lite_xl_paths import LiteXLPaths
from .lite_xl_snapshots import LiteXLSnapshots

class LiteXLInitBuilder:
    """🔨 Hefesto — Geração e validação estática do init.lua (soberano e sandbox)."""

    _LUA_NOISE = re.compile(
        r"--\[(=*)\[.*?\]\1\]|"  # 1. Comentário de bloco
        r"--[^\r\n]*|"           # 2. Comentário de linha
        r"\[(=*)\[.*?\]\2\]|"    # 3. String multilinha
        r'"(?:\\.|[^"\\])*"|'    # 4. String aspas duplas
        r"'(?:\\.|[^'\\])*'",    # 5. String aspas simples
        re.DOTALL,
    )

    def _clean_lua_source(source: str) -> str:
        """Lexer atômico de passagem única (elimina comentários e strings literais)."""
        lua_pattern = re.compile(
            r"--\[(=*)\[.*?\]\1\]|"  # 1. Comentário de bloco
            r"--[^\r\n]*|"           # 2. Comentário de linha
            r"\[(=*)\[.*?\]\2\]|"    # 3. String multilinha
            r'"(?:\\.|[^"\\])*"|'   # 4. String aspas duplas
            r"'(?:\\.|[^'\\])*'",    # 5. String aspas simples
            re.DOTALL,
        )
        return lua_pattern.sub(" ", source)

    @classmethod
    def get_template_files(cls) -> List[Path]:
        """Retorna a lista ordenada de templates, garantindo dependências visuais."""
        t_dir = LiteXLPaths.get_template_dir()
        if not t_dir.exists():
            return []
        
        # Descoberta dinâmica ordenada alfabeticamente (03b vem após 03, 16 após 15)
        templates = sorted(t_dir.glob("*.lua"))
        
        # 🛡️ SANITY CHECK DE MA'AT: Validação de Dependências Visuais
        names = {p.name for p in templates}
        critical_deps = {
            "03b_tab_compact_staircase.lua": "03_tab_colors.lua",
            "16_open_editors_dock.lua": "15_audit_highlighter.lua"
        }
        
        for child, parent in critical_deps.items():
            if child in names and parent not in names:
                templates = [t for t in templates if t.name != child]
                
        return templates

    @classmethod
    def generate_sovereign_init(cls) -> str:
        """Gera o init.lua com tolerância a falhas e abertura automática de aba de erro na tela."""
        init_buffer: List[str] = [
            "-- =============================================================================",
            "-- DOXOADE SOVEREIGN INIT — ACTIVE SHIELD & AUTO-QUARANTINE ENGINE",
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
            ""
        ]
        for tf in cls.get_template_files():
            init_buffer.append(f"-- >>> [TEMPLATE: {tf.name}] >>>")
            init_buffer.append(f'_doxoade_safe_boot("{tf.name}", function()')
            init_buffer.append(tf.read_text(encoding="utf-8"))
            init_buffer.append("end)")
            init_buffer.append(f"-- <<< [END TEMPLATE: {tf.name}] <<<\n")
        return "\n".join(init_buffer)

    @classmethod
    def generate_sandbox_init(cls, test_module: Optional[Path] = None) -> str:
        """Gera um init.lua focado em testes COM o logger soberano."""
        init_buffer: List[str] = [
            "-- =============================================================================",
            "-- DOXOADE SANDBOX INIT — ISOLATED TESTING HARNESS",
            f"-- Compilado em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "-- =============================================================================\n",
        ]
        
        # 🔧 CORREÇÃO: Inclui TODOS os templates, incluindo o logger
        templates = cls.get_template_files()
        for tf in templates:
            init_buffer.append(f"-- >>> [TEMPLATE: {tf.name}] >>>")
            init_buffer.append(f'_doxoade_safe_boot("{tf.name}", function()')
            init_buffer.append(tf.read_text(encoding="utf-8"))
            init_buffer.append("end)")
            init_buffer.append(f"-- <<< [END TEMPLATE: {tf.name}] <<<\n")
        
        return "\n".join(init_buffer)

    @classmethod
    def generate_chaos_init(cls) -> str:
       """Gera um init.lua específico para testes de caos (SEM safe_boot nos payloads)."""
       init_buffer: List[str] = [
          "-- =============================================================================",
          "-- DOXOADE CHAOS INIT — ISOLATED CHAOS HARNESS (NO SAFE BOOT FOR PAYLOADS)",
          f"-- Compilado em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          "-- =============================================================================\n",
       ]
       
       # 1. Inclui TODOS os templates COM safe_boot (para manter o sistema estável)
       for tf in cls.get_template_files():
          init_buffer.append(f"-- >>> [TEMPLATE: {tf.name}] >>>")
          init_buffer.append(f'_doxoade_safe_boot("{tf.name}", function()')
          init_buffer.append(tf.read_text(encoding="utf-8"))
          init_buffer.append("end)")
          init_buffer.append(f"-- <<< [END TEMPLATE: {tf.name}] <<<\n")
       
       # 2. Adiciona hooks de detecção de caos (será injetado pelo runner)
       init_buffer.append("-- >>> [CHAOS HOOKS] >>>")
       init_buffer.append("-- Hooks serão injetados aqui pelo chaos_deep_runner.py")
       init_buffer.append("-- <<< [END CHAOS HOOKS] <<<\n")
       
       return "\n".join(init_buffer)

    @classmethod
    def install_sovereign_config(cls, force: bool = False, backup: bool = True, **kwargs) -> Tuple[bool, str]:
        """Instalação soberana atômica com Pre-Flight Gatekeeper e snapshot promotion."""
        init_path = LiteXLPaths.get_init_lua_path()
        init_path.parent.mkdir(parents=True, exist_ok=True)

        # Garante a pasta de artefatos do API Guard
        guard_dir = LiteXLPaths.get_user_dir() / ".doxoade" / "api_guard"
        guard_dir.mkdir(parents=True, exist_ok=True)

        content = cls.generate_sovereign_init()

        # 1. Pre-Flight Estático
        scan_errs = cls.compile_scan_lua(content)
        if scan_errs and not force:
            return False, f"Pre-Flight rejeitou o init gerado: {'; '.join(scan_errs)}"

        temp_init = init_path.with_suffix(f".tmp_{os.getpid()}")
        try:
            temp_init.write_text(content, encoding="utf-8")

            # 2. Pre-Flight de Compilação Real
            compile_err = cls.true_compile_check(temp_init)
            if compile_err and compile_err != "NO_RUNTIME" and not force:
                temp_init.unlink(missing_ok=True)
                return False, f"Pre-Flight de compilação rejeitou o init: {compile_err}"

            if backup and init_path.exists():
                LiteXLSnapshots.backup_workspace_state()

            temp_init.replace(init_path)

            # 3. Promove para o snapshot estável oficial
            if not scan_errs and (not compile_err or compile_err == "NO_RUNTIME"):
                LiteXLSnapshots.promote_to_stable_snapshot()

            return True, f"Configuração soberana instalada e validada em {init_path}"
        except Exception as e:
            temp_init.unlink(missing_ok=True)
            return False, f"Falha durante a instalação: {e}"

    @staticmethod
    def get_code_snippet(
        lines: List[str], line_no: int, radius: int = 2
    ) -> List[Tuple[int, bool, str]]:
        """Retorna tuplas (numero_linha, is_target, texto) para renderização visual."""
        start = max(1, line_no - radius)
        end = min(len(lines), line_no + radius)
        return [
            (ln, ln == line_no, lines[ln - 1]) for ln in range(start, end + 1)
        ]

    @staticmethod
    def _blank_keep_lines(m) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    @classmethod
    def compile_scan_lua(cls, source: str) -> List[str]:
        """Tripwire léxico: detecta vararg fora de escopo e chamadas sem require."""
        errors: List[str] = []

        # 1. Checagem estática de strict.lua: uso de 'core.' sem require "core"
        clean = cls._LUA_NOISE.sub(cls._blank_keep_lines, source)
        if re.search(r"\bcore\.[a-zA-Z_]", clean):
            has_core_decl = (
                re.search(r"local\s+core\s*=", source)
                or re.search(r"require\s*\(?[\"']core[\"']\)?", source)
            )
            if not has_core_decl:
                errors.append(
                    "strict.lua: Chamadas para 'core.*' detectadas sem 'local core = require \"core\"'"
                )

        # 2. Tripwire de vararg (...)
        stack = [["f", True]]
        last_ctrl = None
        n = len(clean)
        tok = re.compile(
            r"\bfunction\b|\bif\b|\bfor\b|\bwhile\b|\brepeat\b|\bdo\b|\bend\b|\buntil\b|\.\.\."
        )

        for m in tok.finditer(clean):
            t = m.group(0)
            if t in ("if", "for", "while", "repeat"):
                stack.append(["b", False])
                last_ctrl = t
            elif t == "do":
                if last_ctrl not in ("for", "while"):
                    stack.append(["b", False])
                last_ctrl = None
            elif t == "function":
                depth = 0
                vararg = False
                j = m.end()
                while j < n:
                    c = clean[j]
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    elif c == "." and clean.startswith("...", j):
                        vararg = True
                        j += 2
                    j += 1
                stack.append(["f", vararg])
                last_ctrl = None
            elif t in ("end", "until"):
                if len(stack) > 1:
                    stack.pop()
                last_ctrl = None
            elif t == "...":
                for frame in reversed(stack):
                    if frame[0] == "f":
                        if not frame[1]:
                            line = clean.count("\n", 0, m.start()) + 1
                            errors.append(
                                f"linha {line}: cannot use '...' outside a vararg function"
                            )
                        break

        return errors

    @classmethod
    def true_compile_check(cls, path: Union[str, Path]) -> Optional[str]:
        """Compilação real via runtime Lua externo. None = OK."""
        manager = LiteXLPaths._get_lua_manager()
        if not manager:
            return "NO_RUNTIME"

        runtime = manager.find_lua_runtime()
        if not runtime:
            return "NO_RUNTIME"

        exe_path, version = runtime
        clean_path = str(path).replace("\\", "/").replace('"', '\\"')

        probe = (
            f'local f, err = loadfile("{clean_path}") '
            f'if not f then '
            f'  io.stderr:write(tostring(err)) '
            f'  os.exit(1) '
            f'else '
            f'  os.exit(0) '
            f'end'
        )

        try:
            res = subprocess.run(
                [str(exe_path), "-e", probe],
                capture_output=True,
                text=True,
                timeout=5,
                stdin=subprocess.DEVNULL,
            )
            if res.returncode != 0:
                err_msg = (res.stderr or res.stdout).strip()
                return err_msg or "Erro de compilação desconhecido"
            return None
        except Exception as e:
            return f"Falha na execução do probe de runtime: {e}"

    @classmethod
    def verify_templates(cls) -> Dict[str, Any]:
        """Audita todos os arquivos de template e retorna o laudo consolidado."""
        t_dir = LiteXLPaths.get_template_dir()
        files = cls.get_template_files()
        report: Dict[str, Any] = {
            "all_ok": True,
            "total_files": len(files),
            "files": {},
            "errors": [],
        }

        for f in files:
            raw = f.read_text(encoding="utf-8", errors="replace")
            lines = raw.splitlines()
            file_errors: List[str] = []
            findings: List[Dict[str, Any]] = []

            # 1. Scanner léxico (strict.lua + vararg)
            scan_errs = cls.compile_scan_lua(raw)
            for se in scan_errs:
                file_errors.append(se)
                m_ln = re.search(r"linha (\d+):", se)
                ln = min(int(m_ln.group(1)), len(lines)) if m_ln else len(lines)
                findings.append({
                    "line": ln,
                    "msg": se,
                    "type": "error",
                    "snippet": cls.get_code_snippet(lines, ln),
                })

            # 2. Compilação real individual
            real_err = cls.true_compile_check(f)
            if real_err and real_err != "NO_RUNTIME":
                file_errors.append(f"Erro de compilação: {real_err}")

            # 3. Balanceamento de blocos
            clean_code = _clean_lua_source(raw)
            opens = len(re.findall(r"\b(?:function|if|do)\b", clean_code))
            closes = len(re.findall(r"\b(?:end)\b", clean_code))
            if opens != closes:
                diff = opens - closes
                file_errors.append(
                    f"Escopo desbalanceado: {abs(diff)} bloco(s) '{'sem end' if diff > 0 else 'end excedente'}' "
                    f"(abertos: {opens}, fechados: {closes})"
                )
                findings.append({
                    "line": len(lines),
                    "msg": f"Desbalanceamento de blocos ({opens} vs {closes})",
                    "type": "error",
                    "snippet": cls.get_code_snippet(lines, len(lines)),
                })

            # Definição estrita de status
            status = "FAIL" if len(file_errors) > 0 else "PASS"
            if status == "FAIL":
                report["all_ok"] = False
                report["errors"].extend(file_errors)

            report["files"][f.name] = {
                "status": status,
                "lines": len(lines),
                "errors": file_errors,
                "findings": findings,
            }

        return report

    @classmethod
    def fix_templates(cls, dry_run: bool = True) -> Dict[str, Any]:
        """Inspeciona e corrige templates com suporte a Dry-Run e diff visual."""
        t_dir = LiteXLPaths.get_template_dir()
        report = {"dry_run": dry_run, "fixed_files": [], "total_fixes": 0}

        if not t_dir.exists():
            return report

        for tf in sorted(list(t_dir.glob("*.lua"))):
            raw_content = tf.read_text(encoding="utf-8", errors="replace")
            lines = raw_content.splitlines()
            modified_lines = []
            file_diffs = []

            for idx, line in enumerate(lines, 1):
                original_line = line
                repaired_line = line

                # 1. Polyfill universal do rencache
                if re.search(r"local\s+rencache\s*=\s*rencache\b", repaired_line) and not re.search(
                    r"rawget\(_G,\s*[\"']rencache[\"']\)", repaired_line
                ):
                    repaired_line = re.sub(
                        r"local\s+rencache\s*=\s*rencache\b",
                        UNIVERSAL_RENCACHE_POLYFILL,
                        repaired_line,
                    )
                    file_diffs.append({
                        "line": idx,
                        "type": "Polyfill Universal rencache",
                        "old": original_line.strip(),
                        "new": repaired_line.strip(),
                    })

                # 2. Correção de API C obsoleta
                if "system.execute(" in repaired_line:
                    repaired_line = repaired_line.replace("system.execute(", "system.exec(")
                    file_diffs.append({
                        "line": idx,
                        "type": "Correção de API C (system.exec)",
                        "old": original_line.strip(),
                        "new": repaired_line.strip(),
                    })

                # 3. Deduplicação de declaração de funções
                if repaired_line.count("local function ") > 1:
                    first_decl = re.findall(r"local function \w+\([^)]*\)", repaired_line)
                    if first_decl:
                        repaired_line = first_decl[0]
                        file_diffs.append({
                            "line": idx,
                            "type": "Deduplicação de declaração de função",
                            "old": original_line.strip(),
                            "new": repaired_line.strip(),
                        })

                modified_lines.append(repaired_line)

            if file_diffs:
                new_content = "\n".join(modified_lines)
                if not dry_run:
                    tf.write_text(new_content, encoding="utf-8")

                report["fixed_files"].append({
                    "file": tf.name,
                    "path": str(tf),
                    "fixes": len(file_diffs),
                    "diffs": file_diffs,
                })
                report["total_fixes"] += len(file_diffs)

        return report
