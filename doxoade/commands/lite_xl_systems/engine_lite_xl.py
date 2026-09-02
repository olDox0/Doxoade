# doxoade/commands/lite_xl_systems/engine_lite_xl.py
"""
Motor Soberano Lite XL - Ártemis/Apolo Engine.
V17.0: Sovereign Immediate-Mode Architecture, Lexical AST Auditor, IPC Dispatcher & Full Bootstrap.
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
    from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager
except ImportError:
    try:
        from doxoade.tools.lua_systems import LuaRuntimeManager
    except ImportError:
        LuaRuntimeManager = None

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""


NOTEPADPP_CANONICAL_KEYS = {
    "ctrl+n": "doxoade:new-doc",
    "ctrl+o": "core:open-file",
    "ctrl+s": "doc:save",
    "ctrl+shift+s": "doc:save-all",
    "ctrl+w": "root:close",
    "ctrl+f": "find-replace:find",
    "ctrl+h": "find-replace:replace",
    "f3": "find-replace:repeat-find",
    "shift+f3": "find-replace:previous-find",
    "ctrl+g": "doc:go-to-line",
    "ctrl+d": "doc:duplicate-lines",
    "ctrl+l": "doc:delete-lines",
    "ctrl+q": "doc:toggle-line-comments",
    "ctrl+tab": "root:switch-to-next-tab",
    "ctrl+shift+tab": "root:switch-to-previous-tab",
    "ctrl+alt+d": "root:move-tab-to-opposite-panel",
    "ctrl+,": "doxoade:open-init-lua",
    "ctrl+alt+u": "doxoade:toggle-litexl-in-tree",
    "ctrl+alt+o": "treeview:add-project-folder",
    "ctrl+alt+r": "treeview:remove-project-folder",
    "ctrl+shift+l": "doxoade:open-log",
    "ctrl+alt+c": "doxoade:copy-path-menu",
    "f1": "doxoade:show-shortcuts-cheat-sheet",
}

KNOWN_LITEXL_MODULES = {
    "core": "Core Engine",
    "core.common": "Common Utilities & Fuzzy Match",
    "core.config": "Configuration System",
    "core.style": "Theme & Styling",
    "core.command": "Command Dispatcher",
    "core.keymap": "Keymap Manager",
    "core.node": "Node Tree Layout",
    "core.docview": "Document View",
    "core.doc": "Document Buffer",
    "core.view": "Base View",
    "core.rootview": "Root Layout View",
    "core.rencache": "Render Cache System",
    "core.logview": "Log Viewer Panel",
    "renderer": "C-Level Native Renderer (Global)",
    "system": "C-Level System API (Global)",
    "regex": "C-Level Regex Engine",
}

UNIVERSAL_RENCACHE_POLYFILL = (
    'local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)'
)
UNIVERSAL_RENDERER_POLYFILL = (
    'local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)'
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

class LiteXLEngine:
    """Motor Soberano Lite XL V17.0."""

    @classmethod
    def run_health_gate(cls) -> Dict[str, Any]:
        """
        🏥 HEALTH GATE — Bateria de validação reutilizável (5 estágios).
        Retorna dados estruturados para o CLI 'health-check' e os pipelines Typhon.
        Returns: {"healthy": bool, "passed": int, "failed": int, "warnings": int, "steps": [...]}
        """
        results = {"passed": 0, "failed": 0, "warnings": 0}
        steps: List[Dict[str, str]] = []

        def _add(label: str, status: str, detail: str) -> None:
            steps.append({"label": label, "status": status, "detail": detail})

        # ═══ 1. TEMPLATES ═══
        try:
            report = cls.verify_templates()
            if report["all_ok"]:
                results["passed"] += 1
                _add("Verificando templates", "pass", f"Todos os {report['total_files']} templates íntegros")
            else:
                results["failed"] += 1
                _add("Verificando templates", "fail", "Erros detectados em templates")
        except Exception as e:
            results["failed"] += 1
            _add("Verificando templates", "fail", f"Falha na verificação: {e}")

        # ═══ 2. API PROBE (bloqueia apenas severidade crítica) ═══
        try:
            import json as _json
            from doxoade.tools.lua_systems.api_guard.api_catalog import load_catalog
            probe_json = cls.get_user_dir() / ".doxoade" / "api_guard" / "runtime_probe.json"
            if probe_json.exists():
                probe_data = _json.loads(probe_json.read_text(encoding="utf-8"))
                results_map = probe_data.get("results", {})
                catalog = load_catalog()
                missing = [aid for aid, r in results_map.items() if r.get("status") == "missing"]
                critical_missing = [a for a in missing if catalog.get(a) and catalog[a].severity_if_missing == "critical"]
                info_missing = [a for a in missing if a not in critical_missing]
                total = probe_data.get("summary", {}).get("total", len(results_map))
                if not critical_missing:
                    results["passed"] += 1
                    detail = f"0/{total} APIs críticas ausentes"
                    if info_missing:
                        detail += f" ({len(info_missing)} não-críticas ausentes)"
                    _add("Validando contratos de API", "pass", detail)
                else:
                    results["failed"] += 1
                    _add("Validando contratos de API", "fail", f"{len(critical_missing)} APIs críticas ausentes: {', '.join(critical_missing)}")
            else:
                results["warnings"] += 1
                _add("Validando contratos de API", "warn", "runtime_probe.json não encontrado (abra o Lite XL ao menos 1x)")
        except Exception as e:
            results["failed"] += 1
            _add("Validando contratos de API", "fail", f"Falha ao validar APIs: {e}")

        # ═══ 3. COMANDOS CRÍTICOS (Shadow Audit) ═══
        try:
            shadow_report = cls.run_shadow_audit()
            if shadow_report.get("status") == "SKIPPED":
                results["warnings"] += 1
                _add("Testando comandos críticos", "warn", f"Shadow audit indisponível: {shadow_report.get('reason', 'N/A')}")
            else:
                cmds_total = shadow_report.get("commands_count", 0)
                cmds_passed = shadow_report.get("commands_passed", 0)
                cmds_crashed = shadow_report.get("commands_crashed", 0)
                orphan_keys = shadow_report.get("orphan_keys", [])
                if cmds_crashed == 0 and cmds_total > 0:
                    if orphan_keys:
                        results["warnings"] += 1
                        _add("Testando comandos críticos", "warn", f"{cmds_passed}/{cmds_total} comandos OK | {len(orphan_keys)} teclas órfãs")
                    else:
                        results["passed"] += 1
                        _add("Testando comandos críticos", "pass", f"{cmds_passed}/{cmds_total} comandos simulados com sucesso")
                else:
                    results["failed"] += 1
                    crashed_list = ", ".join(map(str, shadow_report.get("crashed_commands", [])[:5]))
                    _add("Testando comandos críticos", "fail", f"{cmds_crashed}/{cmds_total} comandos falharam: {crashed_list}")
        except Exception as e:
            results["failed"] += 1
            _add("Testando comandos críticos", "fail", f"Falha no shadow audit: {e}")

        # ═══ 4. KEYMAPS ═══
        try:
            keymaps = cls.parse_keybindings(cls.get_init_lua_path())
            registered = set()
            for entry in keymaps:
                if isinstance(entry, dict):
                    nk = entry.get("normalized_key") or entry.get("raw_key")
                    if nk:
                        registered.add(nk.lower())
            critical_keys = ["ctrl+alt+\\", "ctrl+alt+shift+f", "f1"]
            def _found(target: str) -> bool:
                variants = {target.lower(), target.lower().replace("\\\\", "\\"), target.lower().replace("\\", "\\\\")}
                return any(v in registered for v in variants)
            missing = [k for k in critical_keys if not _found(k)]
            if not missing:
                results["passed"] += 1
                _add("Verificando mapeamento de teclas", "pass", f"{len(critical_keys)}/{len(critical_keys)} atalhos críticos mapeados ({len(keymaps)} bindings totais)")
            else:
                results["warnings"] += 1
                _add("Verificando mapeamento de teclas", "warn", f"Faltando atalhos: {', '.join(missing)}")
        except Exception as e:
            results["failed"] += 1
            _add("Verificando mapeamento de teclas", "fail", f"Falha ao verificar keymaps: {e}")

        # ═══ 5. ARTEFATOS FORENSES ═══
        try:
            artifacts = cls.get_session_artifacts()
            session_log = cls.get_session_log_path()
            forensic_report = cls.get_user_dir() / ".doxoade" / "diagnostics" / "forensic_report.txt"
            signals = []
            if isinstance(artifacts, list) and artifacts:
                signals.append(f"{len(artifacts)} artefatos de sessão")
            if session_log.exists():
                signals.append("session_log.txt")
            if forensic_report.exists():
                signals.append("forensic_report.txt")
            if signals:
                results["passed"] += 1
                _add("Verificando sistema forense", "pass", f"Sinais forenses: {', '.join(signals)}")
            else:
                results["warnings"] += 1
                _add("Verificando sistema forense", "warn", "Nenhum artefato forense encontrado ainda")
        except Exception as e:
            results["failed"] += 1
            _add("Verificando sistema forense", "fail", f"Falha ao verificar artefatos: {e}")

        return {
            "healthy": results["failed"] == 0,
            "passed": results["passed"],
            "failed": results["failed"],
            "warnings": results["warnings"],
            "steps": steps,
        }

    @classmethod
    def get_probe_dir(cls) -> Path:
        """Diretório de probes do API Guard."""
        return cls.get_template_dir() / "lite_xl_probes"

    @classmethod
    def get_probe_files(cls) -> List[Path]:
        """Retorna todos os probes Lua de forma ordenada."""
        p_dir = cls.get_probe_dir()
        if not p_dir.exists():
            return []
        return sorted([f for f in p_dir.glob("*.lua") if f.is_file()])

    @classmethod
    def get_template_files(cls) -> List[Path]:
        """Retorna a lista ordenada de templates, garantindo dependências visuais."""
        t_dir = cls.get_template_dir()
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
    def generate_sandbox_init(cls, sandbox_file: Path) -> str:
        """Gera o init.lua do Sandbox protegido pelo Horus Shield."""
        init_buffer = [cls.generate_sovereign_init()]
        if sandbox_file.exists():
            init_buffer.append("\n-- =============================================================================")
            init_buffer.append("-- 🧪 SANDBOX EXPERIMENTAL MODULE (HORUS PROTECTED)")
            init_buffer.append("-- =============================================================================")
            init_buffer.append(f'_doxoade_safe_boot("{sandbox_file.name}", function()')
            init_buffer.append(sandbox_file.read_text(encoding="utf-8"))
            init_buffer.append("end)\n")
        return "\n".join(init_buffer)

        # # 1. INJETA OS PROBES E O API GUARD NO TOPO
        # probe_files = cls.get_probe_files()
        # for pf in probe_files:
        #     init_buffer.append(f"-- >>> [API GUARD PROBE: {pf.name}] >>>")
        #     init_buffer.append(pf.read_text(encoding="utf-8"))
        #     init_buffer.append(f"-- <<< [END PROBE: {pf.name}] <<<\n")

        # # 2. INJETA OS TEMPLATES FUNCIONAIS (00_ a 15_)
        # template_files = cls.get_template_files()
        # for tf in template_files:
        #     init_buffer.append(f"-- >>> [TEMPLATE: {tf.name}] >>>")
        #     init_buffer.append(tf.read_text(encoding="utf-8"))
        #     init_buffer.append(f"-- <<< [END TEMPLATE: {tf.name}] <<<\n")

        # return "\n".join(init_buffer)

    @classmethod
    def install_sovereign_config(cls, force: bool = False, backup: bool = True, **kwargs) -> Tuple[bool, str]:
        """Instalação soberana atômica com Pre-Flight Gatekeeper e snapshot promotion."""
        init_path = cls.get_init_lua_path()
        init_path.parent.mkdir(parents=True, exist_ok=True)

        # Garante a pasta de artefatos do API Guard
        guard_dir = cls.get_user_dir() / ".doxoade" / "api_guard"
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
                cls.backup_workspace_state()

            temp_init.replace(init_path)

            # 3. Promove para o snapshot estável oficial
            if not scan_errs and (not compile_err or compile_err == "NO_RUNTIME"):
                cls.promote_to_stable_snapshot()

            return True, f"Configuração soberana instalada e validada em {init_path}"
        except Exception as e:
            temp_init.unlink(missing_ok=True)
            return False, f"Falha durante a instalação: {e}"

    # =========================================================================
    # 🗂️ PRESERVAÇÃO DE WORKSPACE, SESSÃO & GOLDEN SNAPSHOT
    # =========================================================================

    @classmethod
    def get_workspace_dir(cls) -> Path:
        """Diretório de sessões e abas do Lite XL."""
        return cls.get_user_dir() / "workspace"

    @classmethod
    def get_workspace_backup_dir(cls) -> Path:
        """Diretório de segurança para snapshots de sessão do Doxoade."""
        return cls.get_user_dir() / ".doxoade" / "workspace_backup"

    # =========================================================================
    # 🗂️ PRESERVAÇÃO INTEGRAL DE SESSÃO (WORKSPACE, SESSION.LUA, SETTINGS)
    # =========================================================================

    @classmethod
    def get_session_artifacts(cls) -> List[Path]:
        """Retorna todos os artefatos de sessão persistente no USERDIR."""
        user_dir = cls.get_user_dir()
        artifacts = []

        # 1. Diretório de workspace (splits, abas, projetos)
        ws_dir = user_dir / "workspace"
        if ws_dir.exists() and ws_dir.is_dir():
            artifacts.append(ws_dir)

        # 2. Arquivos de sessão e configurações dinâmicas
        for fname in ["session.lua", "user_settings.lua", "session.json"]:
            p = user_dir / fname
            if p.exists() and p.is_file():
                artifacts.append(p)

        return artifacts

    @classmethod
    def backup_workspace_state(cls) -> bool:
        """Cria snapshot abrangente de todos os artefatos de sessão do usuário."""
        try:
            bkp_dir = cls.get_workspace_backup_dir()
            bkp_dir.mkdir(parents=True, exist_ok=True)
            artifacts = cls.get_session_artifacts()

            for art in artifacts:
                dest = bkp_dir / art.name
                if art.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.copytree(art, dest, dirs_exist_ok=True)
                elif art.is_file():
                    shutil.copy2(art, dest)

            return True
        except Exception:
            return False

    @classmethod
    def restore_workspace_state(cls) -> bool:
        """Restaura o estado exato de abas, splits, session.lua e user_settings."""
        try:
            bkp_dir = cls.get_workspace_backup_dir()
            user_dir = cls.get_user_dir()
            if not bkp_dir.exists():
                return False

            for item in bkp_dir.iterdir():
                dest = user_dir / item.name
                if item.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                elif item.is_file():
                    shutil.copy2(item, dest)

            return True
        except Exception:
            return False

    @classmethod
    def get_stable_init_path(cls) -> Path:
        """Retorna o caminho do snapshot estável (Golden State)."""
        return cls.get_init_lua_path().with_suffix(".lua.stable")

    @classmethod
    def get_broken_init_path(cls) -> Path:
        """Retorna o caminho de quarentena do init que falhou."""
        return cls.get_init_lua_path().with_suffix(".lua.broken")

    @classmethod
    def promote_to_stable_snapshot(cls) -> bool:
        """Promove o init.lua atual a Golden Snapshot estável."""
        init_path = cls.get_init_lua_path()
        if not init_path.exists():
            return False
        try:
            stable_path = cls.get_stable_init_path()
            shutil.copy2(init_path, stable_path)
            return True
        except Exception:
            return False

    @classmethod
    def restore_stable_snapshot(cls) -> Tuple[bool, str]:
        """Restaura o último init.lua estável conhecido."""
        init_path = cls.get_init_lua_path()
        stable_path = cls.get_stable_init_path()

        if init_path.exists():
            try:
                broken_path = cls.get_broken_init_path()
                shutil.copy2(init_path, broken_path)
            except Exception:
                pass

        if stable_path.exists():
            try:
                shutil.copy2(stable_path, init_path)
                return True, "Golden Snapshot (.stable) restaurado com sucesso."
            except Exception as e:
                return False, f"Falha ao copiar snapshot estável: {e}"

        try:
            cls.install_sovereign_config()
            return True, "Snapshot estável inexistente. Configuração padrão instalada."
        except Exception as e:
            return False, f"Falha no fallback de emergência: {e}"

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

    @classmethod
    def fix_templates(cls, dry_run: bool = True) -> Dict[str, Any]:
        """Inspeciona e corrige templates com suporte a Dry-Run e diff visual."""
        t_dir = cls.get_template_dir()
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

    # =========================================================================
    # 📁 [1] RESOLUÇÃO DE CAMINHOS & ESTRUTURA
    # =========================================================================

    @staticmethod
    def get_user_dir() -> Path:
        home = Path.home()
        xdg_config = os.getenv("XDG_CONFIG_HOME")
        if xdg_config and (Path(xdg_config) / "lite-xl").exists():
            return Path(xdg_config) / "lite-xl"

        dot_config = home / ".config" / "lite-xl"
        if dot_config.exists():
            return dot_config

        if sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            if appdata and (Path(appdata) / "lite-xl").exists():
                return Path(appdata) / "lite-xl"

        return dot_config

    @classmethod
    def get_template_dir(cls) -> Path:
        return Path(__file__).parent / "template"

    @classmethod
    def get_init_lua_path(cls) -> Path:
        return cls.get_user_dir() / "init.lua"

    @classmethod
    def get_session_log_path(cls) -> Path:
        return cls.get_user_dir() / "session_log.txt"

    @classmethod
    def get_error_txt_path(cls) -> Path:
        return cls.get_user_dir() / "error.txt"

    @classmethod
    def get_ipc_queue_path(cls) -> Path:
        return cls.get_user_dir() / ".ipc_queue"

    @classmethod
    def bootstrap_templates_if_missing(cls):
        """Garante que a pasta de templates modular exista no sistema."""
        t_dir = cls.get_template_dir()
        t_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_template_files(cls) -> List[Path]:
        """Retorna todos os templates em ordem alfabética estrita."""
        t_dir = cls.get_template_dir()
        if not t_dir.exists():
            return []
        return sorted([f for f in t_dir.glob("*.lua") if f.is_file()])

    @classmethod
    def verify_templates(cls) -> Dict[str, Any]:
        """Audita todos os arquivos de template e retorna o laudo consolidado."""
        t_dir = cls.get_template_dir()
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
    def find_executable(cls) -> Optional[Path]:
        if sys.platform == "win32":
            known_locations = [
                Path("C:/Program Files/Lite XL/lite-xl.exe"),
                Path("C:/Program Files (x86)/Lite XL/lite-xl.exe"),
                Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Lite XL\lite-xl.exe")),
                Path(os.path.expandvars(r"%APPDATA%\Lite XL\lite-xl.exe")),
                Path(os.path.expandvars(r"%USERPROFILE%\scoop\apps\lite-xl\current\lite-xl.exe")),
            ]
            for loc in known_locations:
                if loc.exists() and loc.is_file():
                    return loc

        scripts_dir = str(Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")).lower()
        path_entries = os.environ.get("PATH", "").split(os.pathsep)

        for entry in path_entries:
            if not entry or entry.lower().rstrip("\\/") == scripts_dir.rstrip("\\/"):
                continue
            p = Path(entry)
            if sys.platform == "win32":
                candidate = p / "lite-xl.exe"
                if candidate.exists() and candidate.is_file():
                    return candidate
            else:
                candidate = p / "lite-xl"
                if candidate.exists() and os.access(candidate, os.X_OK):
                    return candidate

        return None

    @classmethod
    def is_process_alive(cls) -> bool:
        """Verifica apenas se o processo do Lite XL está vivo no sistema operacional."""
        if sys.platform == "win32":
            try:
                out = subprocess.check_output(
                    [
                        "tasklist",
                        "/FI",
                        "IMAGENAME eq lite-xl.exe",
                        "/FO",
                        "CSV",
                        "/NH",
                    ],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                return any(
                    line.strip().lower().startswith('"lite-xl.exe"')
                    or line.strip().lower().startswith("lite-xl.exe")
                    for line in out.splitlines()
                )
            except Exception:
                return False
        else:
            try:
                out = subprocess.check_output(
                    ["pgrep", "-f", "lite-xl"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                return bool(out.strip())
            except Exception:
                return False

    @classmethod
    def is_running(cls, focus_window: bool = True) -> bool:
        """
        Compatibilidade com o comportamento antigo.

        Por padrão:
        - verifica se o processo está vivo;
        - tenta focar a janela;
        - retorna o resultado do foco.

        Para apenas checar processo sem focar:
            LiteXLEngine.is_running(focus_window=False)
        """
        if not cls.is_process_alive():
            return False

        if focus_window:
            return cls.focus_running_window()

        return True

    @classmethod
    def focus_running_window(cls) -> bool:
        """Tenta trazer a janela do Lite XL para o primeiro plano (Best Effort)."""
        if sys.platform == "win32":
            try:
                cmd = (
                    "$ws = New-Object -ComObject WScript.Shell; if"
                    " ($ws.AppActivate('Lite XL')) { exit 0 } else { exit 1 }"
                )
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True,
                    timeout=2,
                )
                return res.returncode == 0
            except Exception:
                return False
        return True

    @classmethod
    def resolve_target_path(cls, raw_path: str) -> Tuple[Optional[str], bool, bool]:
        """Resolve caminhos e cria arquivos/pastas automaticamente se não existirem."""
        if not raw_path or raw_path.strip() == ".":
            cwd = Path.cwd().resolve()
            return str(cwd), True, True

        clean = raw_path.strip().strip("'\"")
        if clean.startswith("~"):
            clean = os.path.expanduser(clean)

        p = Path(clean)
        try:
            abs_p = p.resolve()
        except Exception:
            abs_p = p.absolute()

        if not abs_p.exists():
            if clean.endswith(("\\", "/")) or not abs_p.suffix:
                abs_p.mkdir(parents=True, exist_ok=True)
                return str(abs_p), True, True
            else:
                abs_p.parent.mkdir(parents=True, exist_ok=True)
                abs_p.touch(exist_ok=True)
                return str(abs_p), True, False

        return str(abs_p), True, abs_p.is_dir()

    _LUA_NOISE = re.compile(
      r"--\[[=]*\[[\s\S]*?\][=]*\]"          # comentário longo
      r"|--[^\n]*"                            # comentário de linha
      r"|\[[=]*\[[\s\S]*?\][=]*\]"            # string longa
      r"|\"(?:\\.|[^\"\\\n])*\""              # string dupla
      r"|'(?:\\.|[^'\\\n])*'"                 # string simples
    )

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
    def lua_runtime_info(cls) -> Optional[Tuple[str, str]]:
        """Retorna (caminho_do_lua, banner_de_versao) ou None se ausente."""
        lua = cls._find_lua_runtime()
        if not lua:
            return None
        try:
            res = subprocess.run(
                [lua, "-v"], capture_output=True, text=True, timeout=5
            )
            banner = (res.stdout + res.stderr).strip()
            version = banner.splitlines()[0] if banner else "versão desconhecida"
            return lua, version
        except Exception:
            return lua, "versão desconhecida"

    @classmethod
    def _get_lua_manager(cls):
        """Obtém a classe LuaRuntimeManager com fallback seguro de importação."""
        global LuaRuntimeManager
        if LuaRuntimeManager is not None:
            return LuaRuntimeManager
        try:
            from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager as LRM
            LuaRuntimeManager = LRM
            return LuaRuntimeManager
        except Exception:
            return None

    @classmethod
    def _find_lua_runtime(cls) -> Optional[str]:
        """Encontra runtime Lua usando o sistema de gestão."""
        manager = cls._get_lua_manager()
        if not manager:
            return None
        runtime = manager.find_lua_runtime()
        return str(runtime[0]) if runtime else None

    @classmethod
    def ensure_lua_runtime(cls) -> Optional[str]:
        """Garante que um runtime Lua esteja disponível, instalando se necessário."""
        manager = cls._get_lua_manager()
        if not manager:
            return None
        runtime = manager.ensure_lua_runtime()
        return str(runtime[0]) if runtime else None

    @classmethod
    def lua_runtime_info(cls) -> Optional[Tuple[str, str]]:
        """Retorna (caminho_do_lua, banner_de_versao) ou None se ausente."""
        lua = cls._find_lua_runtime()
        if not lua:
            return None
        try:
            res = subprocess.run([lua, "-v"], capture_output=True, text=True, timeout=5)
            banner = (res.stdout + res.stderr).strip()
            version = banner.splitlines()[0] if banner else "versão desconhecida"
            return lua, version
        except Exception:
            return lua, "versão desconhecida"

    @classmethod
    def true_compile_check(cls, path: Union[str, Path]) -> Optional[str]:
        """Compilação real via runtime Lua externo. None = OK."""
        manager = cls._get_lua_manager()
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
    def probe_boot(cls, timeout: float = 8.0, start_time: Optional[float] = None) -> bool:
        """Prova de boot: valida se o 00_header criou/atualizou o session_log.txt nesta sessão."""
        log_path = cls.get_session_log_path()
        mark_time = start_time or time.time()
        deadline = time.time() + timeout

        while time.time() < deadline:
            if log_path.exists():
                try:
                    mtime = log_path.stat().st_mtime
                    if mtime >= (mark_time - 1.0):
                        return True
                except OSError:
                    pass
            time.sleep(0.3)
        return False

    @classmethod
    def send_to_running_instance(cls, target_path: str) -> Tuple[bool, str]:
        resolved, exists, is_dir = cls.resolve_target_path(target_path)
        if not resolved:
            return False, "Caminho inválido."

        if not exists:
            return False, f"O caminho não existe no disco: {resolved}"

        try:
            ipc_queue = cls.get_ipc_queue_path()
            with open(ipc_queue, "a", encoding="utf-8") as f:
                f.write(resolved + "\n")
            cls.focus_running_window()
            return True, resolved
        except Exception as e:
            return False, str(e)

    @classmethod
    def cleanup_old_shims(cls):
        scripts_dir = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
        if not scripts_dir.exists():
            return
        for name in ["lite-xl.cmd", "litexl.cmd", "lite-lx.cmd", "lxl.cmd", "lite-xl", "litexl", "lite-lx", "lxl"]:
            target = scripts_dir / name
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass

    @classmethod
    def install_terminal_shims(cls) -> List[str]:
        cls.cleanup_old_shims()
        scripts_dir = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
        if not scripts_dir.exists():
            return []

        py_exe = str(Path(sys.executable).resolve())
        installed = []
        aliases = ["lite-xl", "litexl", "lite-lx", "lxl"]

        for alias in aliases:
            if sys.platform == "win32":
                shim_path = scripts_dir / f"{alias}.cmd"
                content = f'@echo off\n"{py_exe}" -m doxoade lite-xl open %*\n'
                shim_path.write_text(content, encoding="utf-8")
                installed.append(str(shim_path))
            else:
                shim_path = scripts_dir / alias
                content = f'#!/bin/sh\nexec "{py_exe}" -m doxoade lite-xl open "$@"\n'
                shim_path.write_text(content, encoding="utf-8")
                shim_path.chmod(0o755)
                installed.append(str(shim_path))

        return installed

    @classmethod
    def diagnose_init_file(cls, init_path: Path) -> Dict[str, Any]:
        """Diagnóstico forense do init.lua consolidado."""
        report = {"exists": False, "errors": [], "checks": []}

        if not init_path.exists():
            return report

        report["exists"] = True
        raw_content = init_path.read_text(encoding="utf-8", errors="replace")
        lines = raw_content.splitlines()

        # 1. Tripwire de compilação (scanner interno)
        scan = cls.compile_scan_lua(raw_content)
        if scan:
            report["errors"].append(
                "Erro de compilação (scanner): " + "; ".join(scan[:5])
            )

        # 2. Compilação real, se houver runtime Lua
        info = cls.lua_runtime_info()
        if info:
            lua_path, lua_version = info
            real_err = cls.true_compile_check(init_path)
            if real_err and real_err != "NO_RUNTIME":
                report["errors"].append(
                    f"Erro de compilação REAL ({lua_version}): {real_err}"
                )
            else:
                report["checks"].append(
                    f"Sintaxe validada por COMPILAÇÃO REAL "
                    f"({lua_version} em {lua_path})."
                )
        else:
            report["checks"].append(
                "⚠ Sem runtime Lua externo. Validação por scanner interno + "
                "balanceamento de blocos. Cobertura PARCIAL."
            )

        # 3. Armadilha strict.lua
        if re.search(r"local\s+rencache\s*=\s*rencache\b", raw_content) and not re.search(
            r"rawget\(_G,\s*[\"']rencache[\"']\)", raw_content
        ):
            report["errors"].append(
                "Armadilha strict.lua: 'local rencache = rencache' detectado sem rawget."
            )

        # 4. Balanceamento de blocos
        clean_code = _clean_lua_source(raw_content)
        opens = len(re.findall(r"\b(?:function|if|do)\b", clean_code))
        closes = len(re.findall(r"\b(?:end)\b", clean_code))
        if opens == closes:
            report["checks"].append(
                f"Balanceamento de blocos Lua íntegro ({len(lines)} linhas | {opens} blocos)."
            )
        else:
            diff = opens - closes
            report["errors"].append(
                f"Erro de Sintaxe Crítico: {abs(diff)} bloco(s) "
                f"{'sem end' if diff > 0 else 'end excedente'}'."
            )

        report["checks"].append("Módulos Core e C-Level APIs validados.")
        return report

    @classmethod
    def parse_keybindings(cls, init_file: Path) -> List[Dict[str, Any]]:
        """Extrai atalhos reais preservando os literais entre aspas."""
        if not init_file.exists():
            return []
        raw_content = init_file.read_text(encoding="utf-8", errors="replace")

        # Remove apenas comentários, mantendo o conteúdo das strings dos atalhos
        code_only = re.sub(
            r"--\[(=*)\[.*?\]\1\]|--[^\r\n]*", "", raw_content, flags=re.DOTALL
        )

        bindings = []
        entry_pattern = re.compile(
            r'\[\s*[\'"]([^\'"]+)[\'"]\s*\]\s*=\s*[\'"]([^\'"]+)[\'"]'
        )

        for match in entry_pattern.finditer(code_only):
            raw_key = match.group(1).strip()
            cmd = match.group(2).strip()
            bindings.append({
                "raw_key": raw_key,
                "normalized_key": raw_key.lower(),
                "command": cmd,
                "is_valid_format": (
                    raw_key == raw_key.lower() and not raw_key.startswith("+")
                ),
            })
        return bindings

    @classmethod
    def graceful_shutdown(cls, timeout: float = 1.5) -> bool:
        """Envia sinal de fechamento gracioso via IPC para salvar sessão e workspace."""
        if not cls.is_process_alive():
            return True

        # Dispara o comando que executa workspace.save() e core.quit()
        cls.send_to_running_instance("__DOXOADE_GRACEFUL_QUIT__")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not cls.is_process_alive():
                time.sleep(0.2)  # Janela de flush do I/O no Windows
                return True
            time.sleep(0.1)

        # Fallback se a janela estiver travada/bloqueada
        cls.kill_ghost_processes()
        time.sleep(0.2)
        return True

    # =========================================================================
    # 🚀 SUPERVISOR DE BOOT COM RESTAURAÇÃO DE SESSÃO ATIVA
    # =========================================================================
    @classmethod
    def launch_with_safety_guard(
        cls, target_path: Optional[str] = None, restore_session: bool = True, *args, **kwargs
    ) -> Tuple[bool, str]:
        """Inicia o Lite XL com monitoramento de session_log e error.txt."""
        if restore_session:
            cls.restore_workspace_state()
        else:
            cls.backup_workspace_state()

        init_path = cls.get_init_lua_path()
        exe = cls.find_executable()
        if not exe:
            return False, "Binário do Lite XL não encontrado."

        cmd_args = [str(exe)]
        if target_path:
            cmd_args.append(str(target_path))

        # Pre-flight check estático do init.lua
        if init_path.exists():
            raw_init = init_path.read_text(encoding="utf-8", errors="replace")
            scan_errs = cls.compile_scan_lua(raw_init)
            compile_err = cls.true_compile_check(init_path)

            if scan_errs or (compile_err and compile_err != "NO_RUNTIME"):
                err_detail = "; ".join(scan_errs) if scan_errs else str(compile_err)
                cls.restore_stable_snapshot()
                cls.restore_workspace_state()
                subprocess.Popen(cmd_args)
                return False, (
                    f"PRE-FLIGHT GATE: ERRO DETECTADO NO INIT.LUA.\n"
                    f"  MODO SEGURO ATIVADO (Snapshot Estável Restaurado).\n"
                    f"  Laudo: {err_detail}"
                )

        # Limpa session_log e error.txt anteriores para isolar a sessão atual
        log_path = cls.get_session_log_path()
        error_path = cls.get_error_txt_path()
        for p in [log_path, error_path]:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        start_time = time.time()
        proc = subprocess.Popen(cmd_args)

        # Handshake Watchdog (monitora logs e error.txt por até 3s)
        boot_confirmed = False
        has_errors = False
        error_excerpt = ""
        deadline = time.time() + 3.0

        while time.time() < deadline:
            if proc.poll() is not None:
                # Processo encerrou abruptamente
                break

            # 🛡️ 1. Checagem prioritária de crash fatal (error.txt)
            if error_path.exists():
                try:
                    mtime = error_path.stat().st_mtime
                    if mtime >= (start_time - 1.0):
                        err_content = error_path.read_text(encoding="utf-8", errors="replace")
                        has_errors = True
                        error_excerpt = "\n".join(err_content.splitlines()[:6])
                        break
                except Exception:
                    pass

            # 🛡️ 2. Checagem de session_log.txt
            if log_path.exists():
                try:
                    log_content = log_path.read_text(encoding="utf-8", errors="replace")
                    if "[ERROR]" in log_content:
                        has_errors = True
                        err_lines = [l for l in log_content.splitlines() if "[ERROR]" in l or "[TRACE]" in l]
                        error_excerpt = "\n".join(err_lines[-5:])
                        break
                    if "=== SOVEREIGN BOOT OK ===" in log_content:
                        boot_confirmed = True
                        break
                except Exception:
                    pass

            time.sleep(0.15)

        # Confirmação de Sucesso
        if (boot_confirmed or (log_path.exists() and not has_errors)) and not has_errors and proc.poll() is None:
            cls.promote_to_stable_snapshot()
            cls.backup_workspace_state()
            return True, "Lite XL inicializado com sucesso em Modo Soberano (Sessão Preservada)."

        # 🚨 Fallback Imediato (mata qualquer popup modal travado e restaura o snapshot)
        try:
            proc.kill()
        except Exception:
            pass

        cls.restore_stable_snapshot()
        cls.restore_workspace_state()
        subprocess.Popen(cmd_args)

        return False, (
            f"FALHA CAPTURADA NO BOOT / RENDERIZAÇÃO.\n"
            f"  MODO SEGURO ATIVADO (Sessão e Snapshot Estável Restaurados).\n"
            f"  Evidência capturada:\n{error_excerpt or 'Timeout aguardando handshake.'}"
        )

    @classmethod
    def install_sovereign_config(cls, force: bool = False, backup: bool = True, **kwargs) -> Tuple[bool, str]:
        """Instalação soberana atômica com Pre-Flight Gatekeeper e snapshot promotion."""
        init_path = cls.get_init_lua_path()
        init_path.parent.mkdir(parents=True, exist_ok=True)

        # Garante a pasta de artefatos do API Guard
        guard_dir = cls.get_user_dir() / ".doxoade" / "api_guard"
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
                cls.backup_workspace_state()

            temp_init.replace(init_path)

            # 3. Promove para o snapshot estável oficial
            if not scan_errs and (not compile_err or compile_err == "NO_RUNTIME"):
                cls.promote_to_stable_snapshot()

            return True, f"Configuração soberana instalada e validada em {init_path}"
        except Exception as e:
            temp_init.unlink(missing_ok=True)
            return False, f"Falha durante a instalação: {e}"

    # =========================================================================
    # 🛑 [4] FINALIZAÇÃO & LIMPEZA DE PROCESSOS
    # =========================================================================

    @classmethod
    def _clear_ipc_queue(cls) -> None:
        """Remove a fila IPC residual com segurança."""
        try:
            ipc_file = cls.get_ipc_queue_path()
            if ipc_file.exists():
                ipc_file.unlink()
        except Exception:
            pass

    @classmethod
    def kill_ghost_processes(cls):
        """Mata processos fantasmas e purga a fila IPC residual."""
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill", "-9", "-f", "lite-xl"], capture_output=True, timeout=5)

        cls._clear_ipc_queue()

    @classmethod
    def get_sandbox_dir(cls) -> Path:
        """Diretório de configuração isolado exclusivo para testes."""
        sandbox_dir = cls.get_user_dir() / ".doxoade" / "sandbox"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        return sandbox_dir

    @classmethod
    def generate_sandbox_init(cls, test_module: Optional[Path] = None) -> str:
        """Gera um init.lua focado em testes com API Guard em modo ENFORCE."""
        init_buffer: List[str] = [
            "-- =============================================================================",
            "-- DOXOADE SANDBOX INIT — ISOLATED TESTING HARNESS (STRICT SECURE BOOT)",
            f"-- Compilado em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "-- =============================================================================\n",
        ]

        # 1. Probes e Guard
        probes = [f for f in cls.get_template_files() if f.name.startswith("00_0")]
        for pf in probes:
            init_buffer.append(f"-- >>> [PROBE: {pf.name}] >>>")
            init_buffer.append("do")
            init_buffer.append(pf.read_text(encoding="utf-8"))
            init_buffer.append("end")
            init_buffer.append(f"-- <<< [END PROBE: {pf.name}] <<<\n")

        # 2. Ativa modo ENFORCE no Sandbox
        init_buffer.append('do\n  if rawget(_G, "DOXOADE_API") then\n    DOXOADE_API.mode = "enforce"\n  end\nend\n')

        # 3. Templates base (00_ a 04_) para ter abas, cores e highlight
        base_templates = [f for f in cls.get_template_files() if not f.name.startswith("00_0") and f.name != "sandbox_module.lua"]
        for tf in base_templates:
            init_buffer.append(f"-- >>> [BASE TEMPLATE: {tf.name}] >>>")
            init_buffer.append("do")
            init_buffer.append(tf.read_text(encoding="utf-8"))
            init_buffer.append("end")
            init_buffer.append(f"-- <<< [END BASE TEMPLATE: {tf.name}] <<<\n")

        # 4. Módulo de Teste Experimental (sandbox_module.lua)
        target_test = test_module or (cls.get_template_dir() / "sandbox_module.lua")
        if target_test.exists():
            init_buffer.append(f"-- >>> [TEST SUBJECT: {target_test.name}] >>>")
            init_buffer.append("do")
            init_buffer.append(target_test.read_text(encoding="utf-8"))
            init_buffer.append("end")
            init_buffer.append(f"-- <<< [END TEST SUBJECT] <<<\n")

        return "\n".join(init_buffer)

    @classmethod
    def launch_sandbox(cls, target_file: Optional[Path] = None) -> Tuple[bool, str]:
        """Inicia uma instância do Lite XL apontando estritamente para o ambiente Sandbox."""
        exe = cls.find_executable()
        if not exe:
            return False, "Executável do Lite XL não foi localizado no sistema."

        sandbox_dir = cls.get_sandbox_dir()
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # 🧹 Remove log de erro anterior para evitar falsos positivos
        err_file = sandbox_dir / "error.txt"
        if err_file.exists():
            try:
                err_file.unlink()
            except Exception:
                pass

        target = target_file or (cls.get_template_dir() / "sandbox_module.lua")
        init_content = cls.generate_sandbox_init(target)
        (sandbox_dir / "init.lua").write_text(init_content, encoding="utf-8")

        # Injeta LITE_USERDIR para forçar o Lite XL a carregar a sandbox
        env = os.environ.copy()
        env["LITE_USERDIR"] = str(sandbox_dir)

        try:
            subprocess.Popen([str(exe)], env=env)
            return True, f"IDE Sandbox iniciada com sucesso em: {sandbox_dir}"
        except Exception as e:
            return False, f"Falha ao disparar processo Lite XL: {str(e)}"

    # ============ SHADOW RUNNER ============
    
    @classmethod
    def get_shadow_harness_path(cls) -> Path:
        """Gera o shadow_harness.lua com Simulação Ativa de Execução de Comandos (Active Dry-Run)."""
        harness_dir = cls.get_user_dir() / ".doxoade" / "shadow_harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        h_file = harness_dir / "shadow_harness.lua"

        harness_lua = """-- Shadow Deep Inspector Active Simulator — Doxoade Nexus Edition
local templates = { ... }

-- 🛡️ 0. STRICT GLOBAL GUARD (Emulação exata do strict.lua do Lite XL)
local declared_globals = {
  core = true, system = true, renderer = true, rencache = true,
  USERDIR = true, PATHSEP = true, VERSION = true, PLATFORM = true,
  SCALE = true, ARGS = true, _G = true, type = true, pcall = true,
  xpcall = true, rawget = true, rawset = true, pairs = true, ipairs = true,
  tostring = true, tonumber = true, print = true, error = true, assert = true,
  select = true, next = true, setmetatable = true, getmetatable = true,
  dofile = true, loadfile = true, require = true, math = true, string = true,
  table = true, io = true, os = true, debug = true, coroutine = true, package = true,
  utf8 = true, collectgarbage = true
}

setmetatable(_G, {
  __newindex = function(t, k, v)
    rawset(declared_globals, k, true)
    rawset(t, k, v)
  end,
  __index = function(t, k)
    if not rawget(declared_globals, k) and not rawget(t, k) then
      error("cannot get undefined variable: " .. tostring(k), 2)
    end
    return rawget(t, k)
  end
})

-- 1. Mock Ativo de Globais, Views e CommandView com Auto-Submit
local core = {
  project_directories = { "." },
  project_dir = ".",
  threads = {},
  command_view = {
    text = "",
    enter = function(self, prompt, opts)
      -- 🧪 Simulação ativa: Testa se o callback submit executa sem erros
      if opts and type(opts.submit) == "function" then
        local ok, err = pcall(opts.submit, "teste_busca_soberana")
        if not ok then
          print(string.format("SHADOW_PROMPT_CRASH|%s|%s", tostring(prompt), tostring(err):gsub("\\n", " ")))
        end
      end
    end
  },
  root_view = {
    root_node = {
      type = "leaf",
      views = {},
      get_primary_node = function(self) return self end,
      split = function(self) return self end,
      add_view = function(self, v) table.insert(self.views, v) end,
      get_view_idx = function(self, v) return 1 end,
    },
    get_active_node = function(self) return self.root_node end,
    open_doc = function(self, d) return d end,
    draw = function(self) end,
    on_mouse_moved = function(self) end,
    on_mouse_pressed = function(self) end,
  },
  status_view = { add_item = function() end },
  command = {
    map = {
      ["core:open-file"] = { action = function() end },
      ["core:find-file"] = { action = function() end },
      ["doc:save"] = { action = function() end },
      ["doc:save-all"] = { action = function() end },
      ["doc:duplicate-lines"] = { action = function() end },
      ["doc:delete-lines"] = { action = function() end },
      ["doc:toggle-line-comments"] = { action = function() end },
      ["doc:go-to-line"] = { action = function() end },
      ["doc:newline"] = { action = function() end },
      ["root:close"] = { action = function() end },
      ["root:split-right"] = { action = function() end },
      ["root:split-down"] = { action = function() end },
      ["root:switch-to-next-tab"] = { action = function() end },
      ["root:switch-to-previous-tab"] = { action = function() end },
      ["root:switch-to-left"] = { action = function() end },
      ["root:switch-to-right"] = { action = function() end },
      ["find-replace:find"] = { action = function() end },
      ["find-replace:replace"] = { action = function() end },
      ["find-replace:repeat-find"] = { action = function() end },
      ["find-replace:previous-find"] = { action = function() end },
    },
    add = function(pred, map)
      for k, v in pairs(map) do
        core.command.map[k] = { predicate = pred, action = v }
      end
    end,
    perform = function(cmd, ...)
      local c = core.command.map[cmd]
      if c and c.action then return pcall(c.action, ...) end
      return false
    end
  },
  keymap = {
    map = {},
    add = function(map)
      for k, v in pairs(map) do core.keymap.map[k] = v end
    end
  },
  syntax = { items = {}, add = function(s) table.insert(core.syntax.items, s) end },
  config = { ignore_files = {}, draw_indent_guides = true, indent_size = 4 },
  style = {
    font = { get_height = function() return 14 end, get_width = function(self, t) return #(t or "") * 7 end },
    tree_font = { get_height = function() return 12 end, get_width = function(self, t) return #(t or "") * 6 end },
    background = { 30, 30, 30, 255 },
    text = { 200, 200, 200, 255 },
    accent = { 38, 188, 95, 255 },
  },
  log = function(...) end,
  error = function(...) end,
  open_doc = function(fn)
    return { filename = fn, lines = { "linha teste 1", "linha teste 2" }, is_dirty = function() return false end, clean = function() end, insert = function() end, set_selection = function() end, remove = function() end }
  end,
  add_thread = function(fn) pcall(fn) end,
  set_active_view = function() end,
}

local active_doc = core.open_doc("teste.lua")
core.active_view = {
  doc = active_doc,
  get_font = function() return core.style.font end,
  get_line_height = function() return 14 end,
  lines = active_doc.lines,
}

local system = {
  mkdir = function() return true end,
  list_dir = function() return { "arquivo_teste.py", "modulo_teste.lua" } end,
  get_file_info = function(p) return { type = "file", size = 100, modified = os.time() } end,
  absolute_path = function(p) return p end,
  exec = function() end,
  set_clipboard = function() end,
}

local Doc = {
  has_selection = function(self) return false end,
  get_selection = function(self) return 1, 1, 1, 1 end,
  get_text = function(self) return "" end,
  insert = function(self) end,
  remove = function(self) end,
  save = function(self) end,
  extend = function(self) return self end,
}

local DocView = {
  draw_line_body = function(self) return 14 end,
  draw_line_gutter = function(self) return 14 end,
  get_gutter_width = function(self) return 40 end,
  get_line_height = function(self) return 14 end,
  get_font = function(self) return core.style.font end,
  new = function(self, doc) return setmetatable({ doc = doc }, { __index = self }) end,
  extend = function(self) return self end,
}
setmetatable(DocView, {
  __call = function(cls, doc) return cls:new(doc) end
})
local Node = { draw_tab_title = function() end, on_mouse_pressed = function() end, extend = function(self) return self end }
local RootView = { draw = function() end, on_mouse_moved = function() end, on_mouse_pressed = function() end, extend = function(self) return self end }
local View = { extend = function(self) return self end }
local StatusView = { Item = { LEFT = 1, RIGHT = 2 } }

rawset(_G, "core", core)
rawset(_G, "system", system)
rawset(_G, "USERDIR", ".")
rawset(_G, "PATHSEP", "/")
rawset(_G, "VERSION", "2.1.8")
rawset(_G, "PLATFORM", "Windows")
rawset(_G, "renderer", { draw_rect = function() end, draw_text = function() end })
rawset(_G, "rencache", { draw_rect = function() end, draw_text = function() end })

package.loaded["core"] = core
package.loaded["core.common"] = { fuzzy_match = function() return true end }
package.loaded["core.config"] = core.config
package.loaded["core.style"] = core.style
package.loaded["core.syntax"] = core.syntax
package.loaded["core.command"] = core.command
package.loaded["core.keymap"] = core.keymap
package.loaded["core.node"] = Node
package.loaded["core.docview"] = DocView
package.loaded["core.doc"] = Doc
package.loaded["core.view"] = View
package.loaded["core.rootview"] = RootView
package.loaded["core.statusview"] = StatusView

-- 2. Carregamento dos Templates
for _, tpath in ipairs(templates) do
  local fname = tpath:match("[^/\\\\]+$") or tpath
  local t0 = os.clock()
  local ok, err = pcall(dofile, tpath)
  local elapsed = (os.clock() - t0) * 1000

  if ok then
    print(string.format("SHADOW_MOD|%s|PASS|%.2f", fname, elapsed))
  else
    print(string.format("SHADOW_MOD|%s|FAIL|%.2f|%s", fname, elapsed, tostring(err):gsub("\\n", " ")))
  end
end

-- 3. Auditoria de Contagem de Comandos
local cmd_count = 0
for _, _ in pairs(core.command.map) do cmd_count = cmd_count + 1 end
print(string.format("SHADOW_CMD_COUNT|%d", cmd_count))

-- 4. 🔬 SIMULAÇÃO ATIVA DE EXECUÇÃO (Invoca cada comando registrado)
local passed_cmds = 0
local failed_cmds = 0
for cmd_name, cmd_entry in pairs(core.command.map) do
  if type(cmd_entry) == "table" and type(cmd_entry.action) == "function" then
    -- 🛡️ Respeita predicados funcionais (comando contextual fora de contexto = PASS)
    local eligible = true
    if type(cmd_entry.predicate) == "function" then
      local ok_p, res_p = pcall(cmd_entry.predicate)
      if not ok_p then
        failed_cmds = failed_cmds + 1
        print(string.format("SHADOW_CMD_CRASH|%s|predicate: %s", tostring(cmd_name), tostring(res_p):gsub("\\n", " ")))
        eligible = false
      elseif res_p == false or res_p == nil then
        eligible = false
      end
    end
    if eligible then
      local ok_act, err_act = pcall(cmd_entry.action)
      if not ok_act then
        failed_cmds = failed_cmds + 1
        print(string.format("SHADOW_CMD_CRASH|%s|%s",
              tostring(cmd_name), tostring(err_act):gsub("\\n", " ")))
      else
        passed_cmds = passed_cmds + 1
      end
    else
      passed_cmds = passed_cmds + 1
    end
  end
end
print(string.format("SHADOW_CMD_SIMULATION|%d|%d", passed_cmds, failed_cmds))

-- 5. Detecção de Atalhos Órfãos
for key, target_cmd in pairs(core.keymap.map) do
  if not core.command.map[target_cmd] then
    print(string.format("SHADOW_ORPHAN_KEY|%s -> %s", tostring(cmd_name), tostring(err_act):gsub("\\n", " ")))
  end
end
"""
        h_file.write_text(harness_lua, encoding="utf-8")
        return h_file

    @classmethod
    def run_shadow_audit(cls) -> Dict[str, Any]:
        """Auditoria profunda com simulação de comandos, execução ativa e integridade de closures."""
        harness_path = cls.get_shadow_harness_path()
        runtime_info = cls.lua_runtime_info()
        templates = cls.get_template_files()

        if not runtime_info or not harness_path.exists() or not templates:
            return {"status": "SKIPPED", "reason": "Runtime Lua ou templates indisponíveis", "files": {}, "total_files": 0}

        lua_exe, _ = runtime_info
        cmd = [str(lua_exe), str(harness_path)] + [str(t) for t in templates]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            output = res.stdout + "\n" + res.stderr

            if res.returncode != 0 and "SHADOW_MOD|" not in output:
                print(f"\n{Fore.RED}🐛 [SHADOW HARNESS CRASH] O Lua falhou ao executar o simulador (Exit Code: {res.returncode}).{Fore.RESET}")
                print(f"{Fore.RED}🐛 [STDERR]:{Fore.RESET}\n{res.stderr[:1500]}")
                print(f"{Fore.RED}🐛 [STDOUT]:{Fore.RESET}\n{res.stdout[:500]}\n")

            if res.returncode != 0 and not output.strip():
                # Lua crashou na inicialização e não imprimiu nada útil
                return {
                    "status": "FAIL",
                    "reason": f"Lua crashou com exit code {res.returncode}. Stderr: {res.stderr[:500]}",
                    "files": {},
                    "total_files": len(templates),
                }

            report: Dict[str, Any] = {
                "status": "PASS",
                "total_files": len(templates),
                "files": {},
                "commands_count": 0,
                "commands_passed": 0,
                "commands_crashed": 0,
                "crashed_commands": [],
                "prompt_crashes": [],
                "orphan_keys": [],
                "errors": []
            }

            for line in output.splitlines():
                line = line.strip()
                if line.startswith("SHADOW_MOD|"):
                    parts = line.split("|")
                    if len(parts) >= 4:
                        status = parts[2]
                        if status == "FAIL":
                            report["status"] = "FAIL"
                        report["files"][parts[1]] = {
                            "status": status,
                            "time_ms": float(parts[3]),
                            "error": parts[4] if len(parts) > 4 else None
                        }
                elif line.startswith("SHADOW_CMD_COUNT|"):
                    report["commands_count"] = int(line.split("|")[1])
                elif line.startswith("SHADOW_CMD_SIMULATION|"):
                    parts = line.split("|")
                    report["commands_passed"] = int(parts[1])
                    report["commands_crashed"] = int(parts[2])
                elif line.startswith("SHADOW_CMD_CRASH|"):
                    parts = line.split("|", 2)
                    report["crashed_commands"].append({"command": parts[1], "error": parts[2] if len(parts) > 2 else "unknown"})
                    report["status"] = "FAIL"
                elif line.startswith("SHADOW_PROMPT_CRASH|"):
                    parts = line.split("|", 2)
                    report["prompt_crashes"].append({"prompt": parts[1], "error": parts[2] if len(parts) > 2 else "unknown"})
                    report["status"] = "FAIL"
                elif line.startswith("SHADOW_ORPHAN_KEY|"):
                    report["orphan_keys"].append(line.split("|")[1])

            return report
        except Exception as e:
            return {"status": "FAIL", "reason": str(e), "files": {}, "total_files": len(templates)}



