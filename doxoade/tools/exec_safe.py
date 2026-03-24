# -*- coding: utf-8 -*-
# doxoade/tools/exec_safe.py

ALLOWED_COMMANDS = {
    "termux-reload-settings",
}

def run_safe(command: str, capture=False):
    """
    Executa comando de forma segura e padronizada.
    """

    if command not in ALLOWED_COMMANDS:
        raise ValueError("Comando não permitido")
    import shutil
    path = shutil.which(command)

    if not path:
        print(f"⚠️ Comando não encontrado: {command}")
        return False

    from doxoade.tools.error_info import handle_error
    from subprocess import run as subprorun
    try:
        return subprorun(
            [path],
            check=True,
            capture_output=capture,
            text=True
        )
    except Exception as e:
        handle_error(e, context=f"execução de {command}")
        return False