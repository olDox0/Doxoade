# -*- coding: utf-8 -*-
# doxoade/tools/soteria_systems/lazarus_hook.py
"""
🛡️ SOTÉRIA / LAZARUS — Escudo Central de Resgate e Crash Handler.
Captura exceções não-tratadas, emite envelopes para o Typhon e aciona o Protocolo Lázaro.
"""
from __future__ import annotations

import sys
import os
import traceback


def lazarus_crash_handler(etype, value, tb):
    """Captura falhas fatais que escaparam do fluxo principal."""
    # 1. Proteção anti-recursão infinita
    if "maximum recursion depth" in str(value):
        print("\x1b[31m[!] ERRO DE RECURSÃO NO MOTOR. BLOQUEANDO VIGILÂNCIA.\x1b[0m")
        return

    error_data = "".join(traceback.format_exception(etype, value, tb))

    # 2. Persistência de emergência da caixa preta
    try:
        dump_path = os.path.abspath("FATAL_CRASH_DUMP.txt")
        with open(dump_path, "w", encoding="utf-8") as f:
            f.write(error_data)
        print("\n\x1b[41;1m 🔥 CRASH FATAL DETECTADO \x1b[0m")
        print(f"Evidência bruta salva em: {dump_path}")
    except Exception:
        pass

    # 3. Consulta rápida na Árvore Typhon (Diagnóstico direto sem AST pesada)
    try:
        from doxoade.commands.typhon_systems.typhon_tree import TREE
        err_msg = str(value)
        matched_fm = None
        for fm in TREE.failures.values():
            if any(symptom in error_data or symptom in err_msg for symptom in fm.symptoms):
                matched_fm = fm
                break

        if matched_fm:
            print(f"\n\x1b[1;36m🌀 [TYPHON DIAGNÓSTICO]: {matched_fm.name} (Severidade: {matched_fm.severity})\x1b[0m")
            print(f"   💬 \x1b[90m{matched_fm.dev_comment}\x1b[0m")
            if matched_fm.mitigation:
                print(f"   🛠️  \x1b[1;32mMitigação:\x1b[0m {matched_fm.mitigation}\n")
    except Exception:
        pass

    # 4. Aciona o Protocolo Lázaro completo se disponível
    try:
        from doxoade.rescue import activate_protocol
        activate_protocol(error_data)
    except Exception as e:
        import logging as _dox_log
        _dox_log.error(f"[INFRA] lazarus_crash_handler: {e}")
        _, exc_obj, exc_tb = sys.exc_info()
        traceback.print_tb(exc_tb)


def install_shield():
    """Instala o escudo na captura global de exceções."""
    sys.excepthook = lazarus_crash_handler


# 🛑 Alias para compatibilidade com injeções legadas de sitecustomize
install = install_shield
