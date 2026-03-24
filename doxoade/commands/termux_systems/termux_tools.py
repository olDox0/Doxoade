# -*- coding: utf-8 -*-
# doxoade/commands/termux_systems/termux_tools.py
"""
Ferramentas de modificação de arquivos de configuração (Micro e Termux).
Arquétipo: Hefesto (Engenharia e Construção).
"""
import os
import json
import re
import shutil

from doxoade.tools.error_info import handle_error
from doxoade.commands.termux_systems.termux_tools import (
    setup_micro_settings,
    setup_micro_bindings,
)

def setup_extra_keys():
    """Configura o teclado do Termux limpando comentários antigos e forçando a aplicação."""
    termux_dir = os.path.expanduser("~/.termux")
    prop_file = os.path.join(termux_dir, "termux.properties")
    os.makedirs(termux_dir, exist_ok=True)
    
    extra_keys_value = "extra-keys = [['ESC','/','-','HOME','UP','END','PGUP'],['TAB','CTRL','ALT','SHIFT','LEFT','DOWN','RIGHT','PGDN']]"
    
    lines =[]
    if os.path.exists(prop_file):
        with open(prop_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    import re
    # Remove qualquer linha antiga que defina extra-keys (comentada ou não)
    new_lines =[line for line in lines if not re.match(r'^\s*#?\s*extra-keys\s*=', line)]
            
    # Adiciona a versão oficial e segura no final do arquivo
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines.append('\n')
    new_lines.append(extra_keys_value + '\n')
    
    with open(prop_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        
    # Recarrega as configurações diretamente na API do Termux
    from subprocess import run as subprorun
    try:
        subprorun(["termux-reload-settings"], check=True, capture_output=True)
    except FileNotFoundError:
        pass # Silencia se rodar fora do ambiente mobile original
    except Exception as e:
        handle_error(e, context="termux-reload-settings")


def setup_micro_settings():
    """Configurações gerais do Micro com indentação em espaços."""
    micro_dir = os.path.expanduser("~/.config/micro")
    settings_file = os.path.join(micro_dir, "settings.json")
    os.makedirs(micro_dir, exist_ok=True)

    settings = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}

    settings.update({
        "colorscheme": "meutema",
        "cursorline": True,
        "truecolor": True,
        "autoindent": True,
        "tabstospaces": True,
        "tabsize": 4,
        "smartpaste": False,
        "diffgutter": True,
        "savehistory": True,
        "relativeruler": False,
        "ruler": True,
    })

    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)


def setup_micro_bindings():
    """Bindings do Micro, preservando inserção de espaços no Tab."""
    micro_dir = os.path.expanduser("~/.config/micro")
    bindings_file = os.path.join(micro_dir, "bindings.json")
    os.makedirs(micro_dir, exist_ok=True)

    bindings = {}
    if os.path.exists(bindings_file):
        try:
            with open(bindings_file, "r", encoding="utf-8") as f:
                bindings = json.load(f)
        except json.JSONDecodeError:
            bindings = {}

    bindings["Alt-s"] = "HSplit"
    bindings["Alt-v"] = "VSplit"
    bindings["Ctrl-w"] = "NextSplit"
    bindings["Alt-w"] = "NextSplit"

    # Com tabstospaces=True, InsertTab insere espaços em vez de TAB real
    bindings["Tab"] = "IndentSelection|InsertTab"
    bindings["Backtab"] = "OutdentSelection|OutdentLine"

    bindings["Ctrl-z"] = "Undo"
    bindings["Ctrl-y"] = "Redo"
    bindings["Alt-d"] = "command:diff"

    with open(bindings_file, "w", encoding="utf-8") as f:
        json.dump(bindings, f, indent=4)