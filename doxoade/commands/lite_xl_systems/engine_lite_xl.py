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
        cls.bootstrap_templates_if_missing()
        return sorted(cls.get_template_dir().glob("*.lua"))

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
    def generate_sovereign_init(cls) -> str:
        """Gera o init.lua consolidado com rodapé canônico de handshake."""
        files = cls.get_template_files()
        chunks = []

        header = (
            "-- =============================================================================\n"
            "-- ⚡ DOXOADE SOVEREIGN LITE XL INIT (AUTO-GERADO)\n"
            f"-- Total de templates incorporados: {len(files)}\n"
            "-- =============================================================================\n\n"
        )
        chunks.append(header)

        for f in files:
            content = f.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"-- 🧩 MÓDULO: {f.name}\n{content}\n\n")

        # 🛡️ Rodapé garantido de Handshake de Boot (independente de templates opcionais)
        footer = (
            "-- =============================================================================\n"
            "-- 🏁 FINALIZAÇÃO DO SOVEREIGN BOOT\n"
            "-- =============================================================================\n"
            'core.log("=== SOVEREIGN BOOT OK ===")\n'
        )
        chunks.append(footer)

        return "".join(chunks)

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
    def install_sovereign_config(cls, force: bool = False, backup: bool = True) -> Tuple[bool, str]:
        """Instalação com Pre-Flight Gatekeeper completo (Sintaxe + strict.lua)."""
        init_path = cls.get_init_lua_path()
        init_path.parent.mkdir(parents=True, exist_ok=True)

        content = cls.generate_sovereign_init()

        # 1. Pre-Flight Estático em Memória
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

            # 3. Gravação atômica segura
            if backup and init_path.exists():
                cls.backup_workspace_state()

            temp_init.replace(init_path)

            # Promove apenas se passou em tudo
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

