# -*- coding: utf-8 -*-
# doxoade/commands/termux_systems/termux_io.py
"""
I/O do comando termux-config.
Arquétipo: Apolo (Comunicação limpa e colorida com o desenvolvedor).
"""
import click

def print_step(message: str):
    """Exibe um passo em progresso."""
    click.secho(f"[*] {message}", fg="cyan")

def print_success(message: str):
    """Exibe sucesso na operação."""
    click.secho(f"[+] {message}", fg="green", bold=True)

def print_warning(message: str):
    """Exibe um aviso útil ao usuário."""
    click.secho(f"[!] {message}", fg="yellow")

def print_error(message: str):
    """Exibe um erro que interrompeu a configuração."""
    click.secho(f"[-] {message}", fg="red", bold=True)