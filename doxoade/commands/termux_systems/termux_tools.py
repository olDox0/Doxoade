# -*- coding: utf-8 -*-
# doxoade/commands/termux_systems/termux_tools.py
"""
Ferramentas de modificação de arquivos de configuração.
Arquétipo: Hefesto (Engenharia e Construção).
"""
import os
import json
import re

def setup_extra_keys():
    """Configura o teclado do Termux para ter as teclas vitais (Shift, Ctrl, Tab, setas)."""
    termux_dir = os.path.expanduser("~/.termux")
    prop_file = os.path.join(termux_dir, "termux.properties")
    
    os.makedirs(termux_dir, exist_ok=True)
    
    # 2. Extra keys com Shift incluído e formato robusto
    extra_keys_value = "extra-keys = [['ESC','/','-','HOME','UP','END','PGUP'],['TAB','CTRL','ALT','SHIFT','LEFT','DOWN','RIGHT','PGDN']]"
    
    content = ""
    if os.path.exists(prop_file):
        with open(prop_file, "r", encoding="utf-8") as f:
            content = f.read()

    if "extra-keys" in content:
        # Substitui a configuração existente para evitar duplicatas
        content = re.sub(r"^extra-keys\s*=.*$", extra_keys_value, content, flags=re.MULTILINE)
    else:
        content += f"\n{extra_keys_value}\n"
        
    with open(prop_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    # Recarrega configurações nativamente (silencioso)
    os.system("termux-reload-settings > /dev/null 2>&1")


def setup_micro_settings():
    """Configurações gerais do Micro (Número da linha, tabulações)."""
    micro_dir = os.path.expanduser("~/.config/micro")
    settings_file = os.path.join(micro_dir, "settings.json")
    
    os.makedirs(micro_dir, exist_ok=True)
    
    settings = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            pass
            
    # 1. Configurar para exibir numero da linha
    settings["ruler"] = True
    settings["tabsize"] = 4
    settings["tabstospaces"] = True
    settings["autoindent"] = True
    settings["diffgutter"] = True
    
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)


def setup_micro_bindings():
    """Configura os atalhos de transição, undo/redo, diff, identação."""
    micro_dir = os.path.expanduser("~/.config/micro")
    bindings_file = os.path.join(micro_dir, "bindings.json")
    
    os.makedirs(micro_dir, exist_ok=True)
    
    bindings = {}
    if os.path.exists(bindings_file):
        try:
            with open(bindings_file, "r", encoding="utf-8") as f:
                bindings = json.load(f)
        except Exception:
            pass
            
    # 3. Dividir a tela (Premier e Pot) e transitar
    bindings["Alt-s"] = "hsplit"        # Alt + S -> Abre a Pot (Bandeja Horizontal)
    bindings["Alt-v"] = "vsplit"        # Alt + V -> Abre bandeja Vertical
    bindings["Ctrl-w"] = "NextSplit"    # Transita focando entre a Premier e Pot
    
    # 4. Aplicar ou diminuir a identação de múltiplas linhas
    bindings["Tab"] = "IndentSelection,InsertTab"
    bindings["Backtab"] = "OutdentSelection,OutdentLine" # Backtab = Shift-Tab no terminal Android
    
    # 5. Ctrl + Z e Ctrl + Y
    bindings["Ctrl-z"] = "Undo"
    bindings["Ctrl-y"] = "Redo"
    
    # 6. Diff entre a tela principal e a bandeja
    # Micro permite invocar comandos. Quando invocado, ele usará a engine de diff.
    bindings["Alt-d"] = "command:diff" 
    
    with open(bindings_file, "w", encoding="utf-8") as f:
        json.dump(bindings, f, indent=4)