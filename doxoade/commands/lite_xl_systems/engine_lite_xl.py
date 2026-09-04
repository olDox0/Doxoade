# doxoade/commands/lite_xl_systems/engine_lite_xl.py
"""
Motor Soberano Lite XL - Ártemis/Apolo Engine.
V18.0: FACHADA de compatibilidade. A implementação foi dividida em 5 módulos por
responsabilidade (God Class original arquivada como referência):
  - lite_xl_paths.py        (LiteXLPaths)       Zeus    — caminhos e runtime Lua
  - lite_xl_init_builder.py (LiteXLInitBuilder) Hefesto — geração/validação do init.lua
  - lite_xl_snapshots.py    (LiteXLSnapshots)   Hades   — backup/restore de workspace
  - lite_xl_process.py      (LiteXLProcess)     Ares    — ciclo de vida do processo
  - lite_xl_diagnostics.py  (LiteXLDiagnostics) Anúbis  — health gate / shadow audit
Todo código externo que chama LiteXLEngine.<metodo>(...) continua funcionando sem
nenhuma alteração — esta classe apenas repassa a chamada ao módulo correto.
"""
from typing import Dict, List, Tuple, Any, Optional, Union
from pathlib import Path

from .lite_xl_paths import LiteXLPaths
from .lite_xl_init_builder import LiteXLInitBuilder
from .lite_xl_snapshots import LiteXLSnapshots
from .lite_xl_process import LiteXLProcess
from .lite_xl_diagnostics import LiteXLDiagnostics

# Constantes preservadas para compatibilidade (usadas fora desta classe)
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
    "ctrl+alt+y": "doxoade:toggle-litexl-in-tree",
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


class LiteXLEngine:
    """Fachada V18.0 — delega para os 5 módulos especializados (ver docstring do arquivo)."""

    @classmethod
    def run_health_gate(cls) -> Dict[str, Any]:
        """Delegado para LiteXLDiagnostics.run_health_gate."""
        return LiteXLDiagnostics.run_health_gate()

    @classmethod
    def get_probe_dir(cls) -> Path:
        """Delegado para LiteXLPaths.get_probe_dir."""
        return LiteXLPaths.get_probe_dir()

    @classmethod
    def get_probe_files(cls) -> List[Path]:
        """Delegado para LiteXLPaths.get_probe_files."""
        return LiteXLPaths.get_probe_files()

    @classmethod
    def get_template_files(cls) -> List[Path]:
        """Delegado para LiteXLInitBuilder.get_template_files."""
        return LiteXLInitBuilder.get_template_files()

    @classmethod
    def generate_sovereign_init(cls) -> str:
        """Delegado para LiteXLInitBuilder.generate_sovereign_init."""
        return LiteXLInitBuilder.generate_sovereign_init()

    @classmethod
    def get_workspace_dir(cls) -> Path:
        """Delegado para LiteXLPaths.get_workspace_dir."""
        return LiteXLPaths.get_workspace_dir()

    @classmethod
    def get_workspace_backup_dir(cls) -> Path:
        """Delegado para LiteXLPaths.get_workspace_backup_dir."""
        return LiteXLPaths.get_workspace_backup_dir()

    @classmethod
    def get_session_artifacts(cls) -> List[Path]:
        """Delegado para LiteXLSnapshots.get_session_artifacts."""
        return LiteXLSnapshots.get_session_artifacts()

    @classmethod
    def backup_workspace_state(cls) -> bool:
        """Delegado para LiteXLSnapshots.backup_workspace_state."""
        return LiteXLSnapshots.backup_workspace_state()

    @classmethod
    def restore_workspace_state(cls) -> bool:
        """Delegado para LiteXLSnapshots.restore_workspace_state."""
        return LiteXLSnapshots.restore_workspace_state()

    @classmethod
    def get_stable_init_path(cls) -> Path:
        """Delegado para LiteXLPaths.get_stable_init_path."""
        return LiteXLPaths.get_stable_init_path()

    @classmethod
    def get_broken_init_path(cls) -> Path:
        """Delegado para LiteXLPaths.get_broken_init_path."""
        return LiteXLPaths.get_broken_init_path()

    @classmethod
    def promote_to_stable_snapshot(cls) -> bool:
        """Delegado para LiteXLSnapshots.promote_to_stable_snapshot."""
        return LiteXLSnapshots.promote_to_stable_snapshot()

    @classmethod
    def restore_stable_snapshot(cls) -> Tuple[bool, str]:
        """Delegado para LiteXLSnapshots.restore_stable_snapshot."""
        return LiteXLSnapshots.restore_stable_snapshot()

    @staticmethod
    def get_code_snippet(line_no, radius=2) -> List[Tuple[int, bool, str]]:
        """Delegado para LiteXLInitBuilder.get_code_snippet."""
        return LiteXLInitBuilder.get_code_snippet(line_no, radius)

    @classmethod
    def fix_templates(cls, dry_run=True) -> Dict[str, Any]:
        """Delegado para LiteXLInitBuilder.fix_templates."""
        return LiteXLInitBuilder.fix_templates(dry_run)

    @staticmethod
    def get_user_dir() -> Path:
        """Delegado para LiteXLPaths.get_user_dir."""
        return LiteXLPaths.get_user_dir()

    @classmethod
    def get_template_dir(cls) -> Path:
        """Delegado para LiteXLPaths.get_template_dir."""
        return LiteXLPaths.get_template_dir()

    @classmethod
    def get_init_lua_path(cls) -> Path:
        """Delegado para LiteXLPaths.get_init_lua_path."""
        return LiteXLPaths.get_init_lua_path()

    @classmethod
    def get_session_log_path(cls) -> Path:
        """Delegado para LiteXLPaths.get_session_log_path."""
        return LiteXLPaths.get_session_log_path()

    @classmethod
    def get_error_txt_path(cls) -> Path:
        """Delegado para LiteXLPaths.get_error_txt_path."""
        return LiteXLPaths.get_error_txt_path()

    @classmethod
    def get_ipc_queue_path(cls) -> Path:
        """Delegado para LiteXLPaths.get_ipc_queue_path."""
        return LiteXLPaths.get_ipc_queue_path()

    @classmethod
    def bootstrap_templates_if_missing(cls):
        """Delegado para LiteXLPaths.bootstrap_templates_if_missing."""
        return LiteXLPaths.bootstrap_templates_if_missing()

    @classmethod
    def verify_templates(cls) -> Dict[str, Any]:
        """Delegado para LiteXLInitBuilder.verify_templates."""
        return LiteXLInitBuilder.verify_templates()

    @classmethod
    def find_executable(cls) -> Optional[Path]:
        """Delegado para LiteXLProcess.find_executable."""
        return LiteXLProcess.find_executable()

    @classmethod
    def is_process_alive(cls) -> bool:
        """Delegado para LiteXLProcess.is_process_alive."""
        return LiteXLProcess.is_process_alive()

    @classmethod
    def is_running(cls, focus_window=True) -> bool:
        """Delegado para LiteXLProcess.is_running."""
        return LiteXLProcess.is_running(focus_window)

    @classmethod
    def focus_running_window(cls) -> bool:
        """Delegado para LiteXLProcess.focus_running_window."""
        return LiteXLProcess.focus_running_window()

    @classmethod
    def resolve_target_path(cls, raw_path) -> Tuple[Optional[str], bool, bool]:
        """Delegado para LiteXLProcess.resolve_target_path."""
        return LiteXLProcess.resolve_target_path(raw_path)

    @staticmethod
    def _blank_keep_lines() -> str:
        """Delegado para LiteXLInitBuilder._blank_keep_lines."""
        return LiteXLInitBuilder._blank_keep_lines()

    @classmethod
    def compile_scan_lua(cls, source) -> List[str]:
        """Delegado para LiteXLInitBuilder.compile_scan_lua."""
        return LiteXLInitBuilder.compile_scan_lua(source)

    @classmethod
    def _get_lua_manager(cls):
        """Delegado para LiteXLPaths._get_lua_manager."""
        return LiteXLPaths._get_lua_manager()

    @classmethod
    def _find_lua_runtime(cls) -> Optional[str]:
        """Delegado para LiteXLPaths._find_lua_runtime."""
        return LiteXLPaths._find_lua_runtime()

    @classmethod
    def ensure_lua_runtime(cls) -> Optional[str]:
        """Delegado para LiteXLPaths.ensure_lua_runtime."""
        return LiteXLPaths.ensure_lua_runtime()

    @classmethod
    def lua_runtime_info(cls) -> Optional[Tuple[str, str]]:
        """Delegado para LiteXLPaths.lua_runtime_info."""
        return LiteXLPaths.lua_runtime_info()

    @classmethod
    def true_compile_check(cls, path) -> Optional[str]:
        """Delegado para LiteXLInitBuilder.true_compile_check."""
        return LiteXLInitBuilder.true_compile_check(path)

    @classmethod
    def probe_boot(cls, timeout=8.0, start_time=None) -> bool:
        """Delegado para LiteXLProcess.probe_boot."""
        return LiteXLProcess.probe_boot(timeout, start_time)

    @classmethod
    def send_to_running_instance(cls, target_path) -> Tuple[bool, str]:
        """Delegado para LiteXLProcess.send_to_running_instance."""
        return LiteXLProcess.send_to_running_instance(target_path)

    @classmethod
    def cleanup_old_shims(cls):
        """Delegado para LiteXLProcess.cleanup_old_shims."""
        return LiteXLProcess.cleanup_old_shims()

    @classmethod
    def install_terminal_shims(cls) -> List[str]:
        """Delegado para LiteXLProcess.install_terminal_shims."""
        return LiteXLProcess.install_terminal_shims()

    @classmethod
    def diagnose_init_file(cls, init_path) -> Dict[str, Any]:
        """Delegado para LiteXLDiagnostics.diagnose_init_file."""
        return LiteXLDiagnostics.diagnose_init_file(init_path)

    @classmethod
    def parse_keybindings(cls, init_file) -> List[Dict[str, Any]]:
        """Delegado para LiteXLDiagnostics.parse_keybindings."""
        return LiteXLDiagnostics.parse_keybindings(init_file)

    @classmethod
    def graceful_shutdown(cls, timeout=1.5) -> bool:
        """Delegado para LiteXLProcess.graceful_shutdown."""
        return LiteXLProcess.graceful_shutdown(timeout)

    @classmethod
    def launch_with_safety_guard(cls, target_path=None, restore_session=True, *args, **kwargs) -> Tuple[bool, str]:
        """Delegado para LiteXLProcess.launch_with_safety_guard."""
        return LiteXLProcess.launch_with_safety_guard(target_path, restore_session, *args, **kwargs)

    @classmethod
    def install_sovereign_config(cls, force=False, backup=True, **kwargs) -> Tuple[bool, str]:
        """Delegado para LiteXLInitBuilder.install_sovereign_config."""
        return LiteXLInitBuilder.install_sovereign_config(force, backup, **kwargs)

    @classmethod
    def _clear_ipc_queue(cls) -> None:
        """Delegado para LiteXLProcess._clear_ipc_queue."""
        return LiteXLProcess._clear_ipc_queue()

    @classmethod
    def kill_ghost_processes(cls):
        """Delegado para LiteXLProcess.kill_ghost_processes."""
        return LiteXLProcess.kill_ghost_processes()

    @classmethod
    def get_sandbox_dir(cls) -> Path:
        """Delegado para LiteXLPaths.get_sandbox_dir."""
        return LiteXLPaths.get_sandbox_dir()

    @classmethod
    def generate_sandbox_init(cls, test_module=None) -> str:
        """Delegado para LiteXLInitBuilder.generate_sandbox_init."""
        return LiteXLInitBuilder.generate_sandbox_init(test_module)

    @classmethod
    def launch_sandbox(cls, target_file=None) -> Tuple[bool, str]:
        """Delegado para LiteXLProcess.launch_sandbox."""
        return LiteXLProcess.launch_sandbox(target_file)

    @classmethod
    def get_shadow_harness_path(cls) -> Path:
        """Delegado para LiteXLDiagnostics.get_shadow_harness_path."""
        return LiteXLDiagnostics.get_shadow_harness_path()

    @classmethod
    def run_shadow_audit(cls) -> Dict[str, Any]:
        """Delegado para LiteXLDiagnostics.run_shadow_audit."""
        return LiteXLDiagnostics.run_shadow_audit()
