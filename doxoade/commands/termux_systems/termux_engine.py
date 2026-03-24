# -*- coding: utf-8 -*-
# doxoade/commands/termux_systems/termux_engine.py
"""
Motor de Configuração do Termux.
Arquétipo: Dionísio.
"""
from .termux_io import print_step, print_success, print_warning, print_error
from .termux_tools import setup_extra_keys, setup_micro_settings, setup_micro_bindings

def run_termux_config():
    """Orquestra a configuração do ambiente Termux e do Micro."""
    print_step("Iniciando configuração do Termux...")
    
    try:
        print_step("1 & 2. Configurando propriedades do Termux e Extra-Keys (Shift, Ctrl, etc)...")
        setup_extra_keys()
        
        print_step("Configurando o Micro (Editor padrão do Doxoade no mobile)...")
        print_step("  -> Habilitando número de linhas e réguas de indentação...")
        setup_micro_settings()
        
        print_step("  -> Configurando atalhos de transição (Premier/Pot), Identação, Undo/Redo e Diff...")
        setup_micro_bindings()
        
        print_success("\nConfiguração concluída com sucesso!")
        print_warning("DICA: Reinicie o Termux (feche e abra o app novamente) para aplicar completamente o novo teclado (extra-keys).")
        
    except Exception as e:
        print_error(f"Falha ao configurar Termux: {e}")