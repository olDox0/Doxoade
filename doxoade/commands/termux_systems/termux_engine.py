# -*- coding: utf-8 -*-
# doxoade/commands/termux_systems/termux_engine.py
"""
Motor de Configuração do Termux.
Arquétipo: Dionísio.
"""
from .termux_io import print_step, print_success, print_warning, print_error

# Importa as extra-keys do termux_tools
from .termux_tools import setup_extra_keys

# Importa as novas funções refatoradas do termux_config
from .termux_config import apply_micro_settings, apply_micro_bindings

def run_termux_config():
    """Orquestra a configuração do ambiente Termux e do Micro."""
    print_step("Iniciando configuração do Termux...")
    
    try:
        print_step("1 & 2. Configurando propriedades do Termux e Extra-Keys (Shift, Ctrl, etc)...")
        setup_extra_keys()
        
        print_step("Configurando o Micro (Editor padrão do Doxoade no mobile)...")
        print_step("  -> Habilitando número de linhas e réguas de indentação...")
        apply_micro_settings()  # <-- Função atualizada
        
        print_step("  -> Configurando atalhos de transição (Premier/Pot), Identação, Undo/Redo e Diff...")
        apply_micro_bindings()  # <-- Função atualizada
        
        print_success("\nConfiguração concluída com sucesso!")
        print_warning("DICA: Reinicie o Termux (feche e abra o app novamente) para aplicar completamente o novo teclado (extra-keys).")
        
    except Exception as e:
        print_error(f"Falha ao configurar Termux: {e}")