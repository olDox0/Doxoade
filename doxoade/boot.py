# doxoade/boot.py
"""
NEXUS BOOT MANAGER - Orquestrador Central de Sistemas de Background.
Garante a hierarquia, evita colisões e preserva os importadores nativos do Python.
"""
import sys
import os

def clean_meta_path():
    """Limpa apenas o lixo do Doxoade, PRESERVANDO o PathFinder do Python."""
    sys.meta_path = [
        f for f in sys.meta_path 
        if "VulcanMetaFinder" not in str(f) and "ShadowFinder" not in str(f)
    ]

def ignite_background_systems(project_root: str):
    """Ordem estrita de inicialização Tier 1 -> Tier 2."""
    clean_meta_path()
    
    # 1. ABI Gate (Move os arquivos compilados para o local correto)
    try:
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        from doxoade.tools.error_info import formated_traceback
        format_traceback(e, "boot - ignite_background_systems - run_abi_gate")

    # 2. Vulcan MetaFinder (Tier 1 - Índice 0)
    try:
        from doxoade.tools.vulcan.meta_finder import VulcanMetaFinder
        vulcan_finder = VulcanMetaFinder(project_root)
        sys.meta_path.insert(0, vulcan_finder)
    except Exception as e:
        print(f"⚠️ [BOOT] Falha no Vulcan: {e}")
        from doxoade.tools.error_info import formated_traceback
        format_traceback(e, "boot - ignite_background_systems - VulcanMetaFinder")

    # 3. Shadow Runtime / NSR (Vigilância - Índice 1)
    try:
        if os.environ.get("DOXOADE_SHADOW") != "0":
            from doxoade.tools.vulcan.shadow_runtime import ShadowFinder
            shadow_finder = ShadowFinder(project_root)
            pos = 1 if len(sys.meta_path) > 0 else 0
            sys.meta_path.insert(pos, shadow_finder)
    except Exception as e:
        from doxoade.tools.error_info import formated_traceback
        format_traceback(e, "boot - ignite_background_systems - DOXOADE_SHADOW")

    # 4. Horus Shadow (Observabilidade - após Vulcan e Shadow)
    try:
        if os.environ.get("DOXOADE_HORUS_ACTIVE") == "1":
            from doxoade.tools.horus_scribe import activate_horus_shadow
            activate_horus_shadow()
    except Exception as e:
        from doxoade.tools.error_info import formated_traceback
        format_traceback(e, "boot - ignite_background_systems - DOXOADE_HORUS_ACTIVE")

    # 5. Sotéria / Lazarus Hook (Crash Handler) — era item 4
    os.environ["DOXOADE_RESCUE"] = "1"
    try:
        from doxoade.tools.aegis.lazarus_hook import install_shield
        install_shield()
    except Exception as e:
        from doxoade.tools.error_info import formated_traceback
        format_traceback(e, "boot - ignite_background_systems - DOXOADE_RESCUE")