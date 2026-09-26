# -*- coding: utf-8 -*-
# doxoade/boot.py
""" NEXUS BOOT MANAGER — Orquestrador Central de Sistemas de Background.
Controlável via 'doxoade engine' através de .doxoade/engine_config.json. """
from __future__ import annotations

import sys
import os
import json
import time
from pathlib import Path
from doxoade.tools.error_info import formated_traceback
from doxoade.tools.soteria_systems.lazarus_hook import install_shield

DEFAULT_ENGINES = {
    "hermes_init": True,
    "metalcraft": True,
    "hermes_diag": True,
    "abi_gate": True,
    "vulcan_meta": True,
    "shadow_runtime": True,
    "horus": False,       # Desativado por padrão para reduzir consumo
    "lazarus": True,
    "hermes_bridge": True,
    "hbc6": True,
}


def get_engine_config_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / ".doxoade" / "engine_config.json"


def load_engine_config(project_root: str | Path) -> dict:
    """Carrega configuração de motores do projeto ou usa padrões seguros."""
    conf_file = get_engine_config_path(project_root)
    if conf_file.exists():
        try:
            with open(conf_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = DEFAULT_ENGINES.copy()
                merged.update(saved)
                return merged
        except Exception:
            pass
    return DEFAULT_ENGINES.copy()


def save_engine_config(project_root: str | Path, config: dict):
    conf_file = get_engine_config_path(project_root)
    conf_file.parent.mkdir(parents=True, exist_ok=True)
    with open(conf_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def clean_meta_path():
    """Limpa apenas os finders do Doxoade, preservando os do Python."""
    sys.meta_path = [
        f for f in sys.meta_path
        if "VulcanMetaFinder" not in str(f) and "ShadowFinder" not in str(f) and "HBC6Finder" not in str(f)
    ]


def ignite_background_systems(project_root: str) -> dict:
    """Orquestrador condicional de background. Respeita 'doxoade engine'."""
    t_global = time.perf_counter()
    phases = {}
    clean_meta_path()

    cfg = load_engine_config(project_root)

    def _track(phase_key, func):
        t0 = time.perf_counter()
        try:
            func()
        finally:
            phases[phase_key] = round((time.perf_counter() - t0) * 1000.0, 2)

    # 1. HERMES INIT
    if cfg.get("hermes_init"):
        def _phase_hermes_init():
            try:
                from doxoade.tools.hermes_systems.hermes_init import init_hermes_bootstrap
                init_hermes_bootstrap(Path(project_root), compile_if_missing=False)
            except Exception:
                pass
        _track("hermes_init", _phase_hermes_init)

    # 2. METALCRAFT AUTO-BUILD
    if cfg.get("metalcraft"):
        def _phase_metalcraft():
            try:
                conf_file = Path(project_root) / "metalcraft.toml"
                if conf_file.exists():
                    from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
                    engine = NexusMetalEngine(project_root)
                    engine.ensure_targets(verbose=False)
            except Exception:
                pass
        _track("metalcraft", _phase_metalcraft)

    # 3. HERMES DIAGNOSTIC & ASYNC LOGGER
    if cfg.get("hermes_diag"):
        def _phase_hermes_diag():
            try:
                from doxoade.tools.hermes_systems.hermes_diagnostic import install_diagnostic_hooks
                install_diagnostic_hooks(project_root)
                from doxoade.tools.hermes_systems.hermes_logger import get_logger
                get_logger().info("Hermes Async Logger inicializado")
            except Exception:
                pass
        _track("hermes_diag", _phase_hermes_diag)

    # 4. ABI GATE
    if cfg.get("abi_gate"):
        def _phase_abi():
            try:
                from doxoade.tools.vulcan.abi_gate import run_abi_gate
                run_abi_gate(project_root)
            except Exception:
                pass
        _track("abi_gate", _phase_abi)

    clean_meta_path()

    # 5. VULCAN METAFINDER & SHADOWFINDER
    if cfg.get("vulcan_meta") or cfg.get("shadow_runtime"):
        def _phase_finders():
            if cfg.get("vulcan_meta"):
                try:
                    from doxoade.tools.vulcan.meta_finder import VulcanMetaFinder
                    sys.meta_path.insert(0, VulcanMetaFinder(project_root))
                except Exception:
                    pass

            if cfg.get("shadow_runtime") and os.environ.get("DOXOADE_SHADOW") != "0":
                try:
                    from doxoade.tools.vulcan.shadow_runtime import ShadowFinder
                    pos = 1 if len(sys.meta_path) > 0 else 0
                    sys.meta_path.insert(pos, ShadowFinder(project_root))
                except Exception:
                    pass
        _track("finders", _phase_finders)

    # 6. HORUS SHADOW
    if cfg.get("horus") and os.environ.get("DOXOADE_HORUS_ACTIVE") == "1":
        def _phase_horus():
            try:
                from doxoade.tools.horus_scribe import activate_horus_shadow
                activate_horus_shadow()
            except Exception:
                pass
        _track("horus", _phase_horus)

    # 7. SOTÉRIA / LAZARUS HOOK
    if cfg.get("lazarus"):
        def _phase_lazarus():
            os.environ["DOXOADE_RESCUE"] = "1"
            try:
                install_shield()
            except Exception:
                pass
        _track("lazarus", _phase_lazarus)

    # 8. HERMES BRIDGE & HBC6
    if cfg.get("hermes_bridge") or cfg.get("hbc6"):
        def _phase_hermes_bridge():
            if cfg.get("hermes_bridge"):
                try:
                    from doxoade.tools.hermes_systems.native.hermes_bridge_builder import ensure_bridge_built
                    ensure_bridge_built(project_root)
                except Exception:
                    pass

            if cfg.get("hbc6"):
                os.environ["DOXOADE_HERMES_ACTIVE"] = "1"
                try:
                    build_dir = Path(project_root) / '.doxoade' / 'hermes' / 'build'
                    hbc6_count = len(list(build_dir.glob('*.hbc6'))) if build_dir.exists() else 0
                    if hbc6_count > 0:
                        from doxoade.tools.hermes_systems.hbc6_meta_finder import install_hbc6_hook
                        install_hbc6_hook(project_root)
                    else:
                        from doxoade.tools.hermes_systems.hermes_hook_v2 import install_hook as hermes_v2_install
                        hermes_v2_install(project_root)
                except Exception:
                    pass
        _track("hermes_bridge", _phase_hermes_bridge)

    total_ignite_ms = round((time.perf_counter() - t_global) * 1000.0, 2)

    # 🛑 RETORNO GARANTIDO DE TELEMETRIA
    return {
        "phases": phases,
        "total_ms": total_ignite_ms,
        "config": cfg
    }
