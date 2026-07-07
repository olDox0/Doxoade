# -*- coding: utf-8 -*-
# doxoade/boot.py
"""
NEXUS BOOT MANAGER - Orquestrador Central de Sistemas de Background.
Garante a hierarquia, evita colisões e preserva os importadores nativos do Python.
"""
import sys
import os
from doxoade.tools.error_info import formated_traceback

def clean_meta_path():
    """Limpa apenas o lixo do Doxoade, PRESERVANDO o PathFinder do Python."""
    sys.meta_path = [
        f for f in sys.meta_path
        if "VulcanMetaFinder" not in str(f) and "ShadowFinder" not in str(f)
    ]

def ignite_background_systems(project_root: str):
    """Ordem estrita de inicialização Tier 1 -> Tier 2."""
    clean_meta_path()
    
    # ═══════════════════════════════════════════════════════════════════
    # FASE 0: HERMES INIT (Bootstrap Acelerado)
    # Carrega módulos críticos como binários nativos (.pyd)
    # ═══════════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.hermes_systems.hermes_init import init_hermes_bootstrap
        from pathlib import Path
        
        hermes_stats = init_hermes_bootstrap(
            Path(project_root),
            compile_if_missing=False  # Não compila automaticamente
        )
        
        if os.environ.get('HERMES_VERBOSE') == '1':
            print(f"[BOOT] Hermes Init: {hermes_stats['bootstrap']['loaded']} módulos nativos, "
                  f"{hermes_stats['total_time_ms']:.2f}ms")
    except Exception as e:
        # Não falha o boot se Hermes Init falhar
        if os.environ.get('HERMES_VERBOSE') == '1':
            print(f"[BOOT] Hermes Init falhou: {e}")
    
    # 1. ABI Gate (Move os arquivos compilados para o local correto)
    try:
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        formated_traceback(e, "boot - ignite_background_systems - run_abi_gate")

    clean_meta_path()
    
    # 1. ABI Gate (Move os arquivos compilados para o local correto)
    try:
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        formated_traceback(e, "boot - ignite_background_systems - run_abi_gate")
    
    # 2. Vulcan MetaFinder (Tier 1 - Índice 0)
    try:
        from doxoade.tools.vulcan.meta_finder import VulcanMetaFinder
        vulcan_finder = VulcanMetaFinder(project_root)
        sys.meta_path.insert(0, vulcan_finder)
    except Exception as e:
        print(f"⚠️ [BOOT] Falha no Vulcan: {e}")
        formated_traceback(e, "boot - ignite_background_systems - VulcanMetaFinder")
    
    # 3. Shadow Runtime / NSR (Vigilância - Índice 1)
    try:
        if os.environ.get("DOXOADE_SHADOW") != "0":
            from doxoade.tools.vulcan.shadow_runtime import ShadowFinder
            shadow_finder = ShadowFinder(project_root)
            pos = 1 if len(sys.meta_path) > 0 else 0
            sys.meta_path.insert(pos, shadow_finder)
    except Exception as e:
        formated_traceback(e, "boot - ignite_background_systems - DOXOADE_SHADOW")
    
    # 4. Horus Shadow (Observabilidade - após Vulcan e Shadow)
    try:
        if os.environ.get("DOXOADE_HORUS_ACTIVE") == "1":
            from doxoade.tools.horus_scribe import activate_horus_shadow
            activate_horus_shadow()
    except Exception as e:
        formated_traceback(e, "boot - ignite_background_systems - DOXOADE_HORUS_ACTIVE")
    
    # 5. Sotéria / Lazarus Hook (Crash Handler)
    os.environ["DOXOADE_RESCUE"] = "1"
    try:
        from doxoade.tools.aegis.lazarus_hook import install_shield
        install_shield()
    except Exception as e:
        formated_traceback(e, "boot - ignite_background_systems - DOXOADE_RESCUE")
    
    # 6. Hermes v2 Native Bridge (Auto-Build via Metalcraft)
    try:
        from doxoade.tools.hermes_systems.native.hermes_bridge_builder import ensure_bridge_built
        if ensure_bridge_built(project_root):
            if os.environ.get("HERMES_VERBOSE") == "1":
                print(f"\x1b[90m[HERMES] Bridge v2 Nativo (SSE 4.2) pronto.\x1b[0m")
    except Exception as e:
        if os.environ.get("HERMES_VERBOSE") == "1":
            print(f"\x1b[90m[HERMES] Bridge v2 não disponível (fallback Python ativo)\x1b[0m")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 7. HERMES SYSTEMS v2 (C-Native Dual-Dictionary) — Índice 2
    # ═══════════════════════════════════════════════════════════════════════════════
    os.environ["DOXOADE_HERMES_ACTIVE"] = "1"
    try:
        if os.environ.get("DOXOADE_HERMES_ACTIVE") == "1":
            # 7.1. Auto-Build do Motor C via Metalcraft
            from doxoade.tools.hermes_systems.native.hermes_bridge_builder import ensure_bridge_built
            if ensure_bridge_built(project_root):
                if os.environ.get("HERMES_VERBOSE") == "1":
                    print(f"\x1b[90m[HERMES v2] Bridge C-Native (SSE 4.2) pronto.\x1b[0m")
            
            # 7.2. Instala o Hook v2 (Intercepta imports e usa o C-Bridge)
            from doxoade.tools.hermes_systems.hermes_hook_v2 import install as hermes_v2_install
            hermes_v2_install(project_root)
            
            if os.environ.get("HERMES_VERBOSE") == "1":
                print(f"\x1b[90m[HERMES v2] Hook instalado no sys.meta_path (Cold/Warm Start ativo)\x1b[0m")
    except Exception as e:
        # Fallback gracioso: se o Hermes v2 falhar, o Python puro continua funcionando
        if os.environ.get("HERMES_VERBOSE") == "1":
            print(f"\x1b[90m[HERMES v2] Falha na inicialização: {e}\x1b[0m")
            
    # ═══════════════════════════════════════════════════════════════════════════════
    # FASE 8: HERMES AUTO-PRELOAD (Inteligente)
    # Pré-carrega módulos críticos com cache de performance
    # ═══════════════════════════════════════════════════════════════════════════════
    try:
        from doxoade.tools.hermes_systems.hermes_auto_preload import auto_preload
        
        preload_stats = auto_preload(
            project_root,
            modules=None,  # Usa cache inteligente
            verbose=os.environ.get("HERMES_VERBOSE") == "1"
        )
        
        if os.environ.get("HERMES_VERBOSE") == "1":
            print(f"[BOOT] Hermes Auto-Preload: {len(preload_stats['loaded'])} loaded, "
                  f"{preload_stats['cache_hits']} cached, "
                  f"{preload_stats['total_time_ms']:.1f}ms")
    except Exception as e:
        # Não falha o boot se preload falhar
        if os.environ.get("HERMES_VERBOSE") == "1":
            print(f"[BOOT] Hermes Auto-Preload falhou: {e}")
