# -*- coding: utf-8 -*-
# doxoade/boot.py
"""
NEXUS BOOT MANAGER — Orquestrador Central de Sistemas de Background.
"""
import sys
import os
from doxoade.tools.error_info import formated_traceback


def clean_meta_path():
    """Limpa apenas o lixo do Doxoade, preservando o PathFinder do Python."""
    sys.meta_path = [
        f for f in sys.meta_path
        if "VulcanMetaFinder" not in str(f) and "ShadowFinder" not in str(f)
    ]


def ignite_background_systems(project_root: str):
    """Ordem estrita de inicialização Tier 1 → Tier 2."""
    clean_meta_path()

    # ═══════════════════════════════════════════════════════════════
    # FASE 0: HERMES INIT (Bootstrap Acelerado)
    # ═══════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.hermes_systems.hermes_init import init_hermes_bootstrap
        from pathlib import Path
        hermes_stats = init_hermes_bootstrap(
            Path(project_root), compile_if_missing=False)
        if os.environ.get('HERMES_VERBOSE') == '1':
            print(f"[BOOT] Hermes Init: "
                  f"{hermes_stats.get('loaded', 0)} módulos carregados")
    except Exception as e:
        if os.environ.get('HERMES_VERBOSE') == '1':
            print(f"[BOOT] Hermes Init falhou (não-fatal): {e}")

    # ═══════════════════════════════════════════════════════════════
    # FASE 0.1: METALCRAFT AUTO-BUILD (Sotéria Integrated)
    # ═══════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
        engine = NexusMetalEngine(project_root)
        verbose = os.environ.get('METALCRAFT_VERBOSE') == '1'
        stats = engine.ensure_targets(verbose=verbose)
        if verbose and stats['total'] > 0:
            print(f"[BOOT] Metalcraft: {stats['built']} built, "
                  f"{stats['skipped']} skipped, {stats['failed']} failed")
    except Exception as e:
        if os.environ.get('METALCRAFT_VERBOSE') == '1':
            print(f"[BOOT] Metalcraft Auto-Build falhou (não-fatal): {e}")

    # ═══════════════════════════════════════════════════════════════
    # FASE 0.5: HERMES DIAGNOSTIC (Crash Handler)
    # ═══════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.hermes_systems.hermes_diagnostic import (
            install_diagnostic_hooks)
        install_diagnostic_hooks(project_root)
        if os.environ.get('HERMES_VERBOSE') == '1':
            print("[BOOT] Hermes Diagnostic: hooks instalados")
    except Exception as e:
        if os.environ.get('HERMES_VERBOSE') == '1':
            print(f"[BOOT] Hermes Diagnostic falhou: {e}")

    # ═══════════════════════════════════════════════════════════════
    # FASE 0.6: HERMES ASYNC LOGGER
    # ═══════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.hermes_systems.hermes_logger import get_logger
        logger = get_logger()
        logger.info("Hermes Async Logger inicializado")
    except Exception as e:
        if os.environ.get('HERMES_VERBOSE') == '1':
            print(f"[BOOT] Hermes Logger falhou: {e}")

    # ═══════════════════════════════════════════════════════════════
    # FASE 1: ABI GATE
    # ═══════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        formated_traceback(e, "boot - run_abi_gate")

    clean_meta_path()

    # ═══════════════════════════════════════════════════════════════
    # FASE 2: VULCAN METAFINDER (Tier 1 — Índice 0)
    # ═══════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.vulcan.meta_finder import VulcanMetaFinder
        vulcan_finder = VulcanMetaFinder(project_root)
        sys.meta_path.insert(0, vulcan_finder)
    except Exception as e:
        print(f"⚠️ [BOOT] Falha no Vulcan: {e}")
        formated_traceback(e, "boot - VulcanMetaFinder")

    # ═══════════════════════════════════════════════════════════════
    # FASE 3: SHADOW RUNTIME / NSR (Índice 1)
    # ═══════════════════════════════════════════════════════════════
    try:
        if os.environ.get("DOXOADE_SHADOW") != "0":
            from doxoade.tools.vulcan.shadow_runtime import ShadowFinder
            shadow_finder = ShadowFinder(project_root)
            pos = 1 if len(sys.meta_path) > 0 else 0
            sys.meta_path.insert(pos, shadow_finder)
    except Exception as e:
        formated_traceback(e, "boot - ShadowFinder")

    # ═══════════════════════════════════════════════════════════════
    # FASE 4: HORUS SHADOW (Observabilidade)
    # ═══════════════════════════════════════════════════════════════
    try:
        if os.environ.get("DOXOADE_HORUS_ACTIVE") == "1":
            from doxoade.tools.horus_scribe import activate_horus_shadow
            activate_horus_shadow()
    except Exception as e:
        formated_traceback(e, "boot - Horus")

    # ═══════════════════════════════════════════════════════════════
    # FASE 5: SOTÉRIA / LAZARUS HOOK (Crash Handler)
    # ═══════════════════════════════════════════════════════════════
    os.environ["DOXOADE_RESCUE"] = "1"
    try:
        from doxoade.tools.aegis.lazarus_hook import install_shield
        install_shield()
    except Exception as e:
        formated_traceback(e, "boot - Lazarus")

    # ═══════════════════════════════════════════════════════════════
    # FASE 6: HERMES v2 NATIVE BRIDGE
    # ═══════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.hermes_systems.native.hermes_bridge_builder import (
            ensure_bridge_built)
        if ensure_bridge_built(project_root):
            if os.environ.get("HERMES_VERBOSE") == "1":
                print("\x1b[90m[HERMES] Bridge v2 Nativo (SSE 4.2) pronto."
                      "\x1b[0m")
    except Exception:
        if os.environ.get("HERMES_VERBOSE") == "1":
            print("\x1b[90m[HERMES] Bridge v2 não disponível "
                  "(fallback Python ativo)\x1b[0m")

    # ═══════════════════════════════════════════════════════════════
    # FASE 7: HBC6 METAPATHFINDER
    # ═══════════════════════════════════════════════════════════════
    os.environ["DOXOADE_HERMES_ACTIVE"] = "1"
    try:
        from pathlib import Path
        build_dir = Path(project_root) / '.doxoade' / 'hermes' / 'build'
        hbc6_count = (len(list(build_dir.glob('*.hbc6')))
                      if build_dir.exists() else 0)
        if hbc6_count > 0:
            from doxoade.tools.hermes_systems.hbc6_meta_finder import (
                install_hbc6_hook)
            install_hbc6_hook(project_root)
            if os.environ.get("HERMES_VERBOSE") == "1":
                print(f"\x1b[90m[HERMES HBC6] MetaFinder ativo: "
                      f"{hbc6_count} módulos redirecionáveis.\x1b[0m")
        else:
            from doxoade.tools.hermes_systems.hermes_hook_v2 import (
                install_hook as hermes_v2_install)
            hermes_v2_install(project_root)
            if os.environ.get("HERMES_VERBOSE") == "1":
                print("\x1b[90m[HERMES v2] Hook V2 legado ativado "
                      "(Modo .hermes).\x1b[0m")
    except Exception as e:
        if os.environ.get("HERMES_VERBOSE") == "1":
            print(f"\x1b[90m[HERMES] Falha na ativação: {e}\x1b[0m")
            
    # ═══════════════════════════════════════════════════════════════
    # FASE 8: HBC6 AUDITIOTIA
    # ═══════════════════════════════════════════════════════════════
    import atexit
    if os.environ.get("HERMES_HBC6_AUDIT", "0") == "1":
        def _dump_audit_on_exit():
            try:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Auditor
                auditor = HBC6Auditor.get_instance()
                auditor.print_report()
                path = auditor.dump_json()
                print(f"  💾 [HBC6-AUDIT] Dossiê salvo em: {path}")
            except Exception:
                pass
        atexit.register(_dump_audit_on_exit)
        print("  🔬 [HBC6-AUDIT] Auditor ativo. Relatório ao final.")
