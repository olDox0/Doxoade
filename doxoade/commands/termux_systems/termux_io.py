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

def print_tutorial():
    """Exibe o tutorial de uso dos editores no Termux."""
    click.secho("\n=== TUTORIAL DE PRODUTIVIDADE MOBILE (TERMUX) ===", fg="cyan", bold=True)
    
    click.secho("\n[ 1. MICRO (Editor Oficial Padrão do Doxoade) ]", fg="green", bold=True)
    click.echo("O Micro foi configurado com o conceito de 'Premier' (Tela Principal) e 'Pot' (Bandeja).")
    click.secho("  • Divisão de Tela e Foco:", fg="yellow")
    click.echo("    - Alt + S      : Divide a tela na horizontal (cria a bandeja/Pot).")
    click.echo("    - Alt + V      : Divide a tela na vertical.")
    click.echo("    - Ctrl + W     : Pula o cursor entre as telas divididas (Premier <-> Pot).")
    click.echo("    - Alt + W      : (Alternativa caso o Android bloqueie o Ctrl+W) Pula o cursor.")
    
    click.secho("  • Edição de Código:", fg="yellow")
    click.echo("    - Tab          : Indenta uma ou múltiplas linhas selecionadas.")
    click.echo("    - Shift + Tab  : Remove a indentação (Outdent).")
    click.echo("    - Ctrl + Z     : Desfazer (Undo).")
    click.echo("    - Ctrl + Y     : Refazer (Redo).")
    click.echo("    - Alt + D      : Invoca comando de Diff / Comandos do Micro.")
    
    click.secho("  • Ações Básicas:", fg="yellow")
    click.echo("    - Ctrl + S     : Salvar arquivo.")
    click.echo("    - Ctrl + Q     : Sair.")
    click.echo("    - Ctrl + E     : Abrir linha de comando interna do Micro (ex: 'set ruler true').")

    click.secho("\n[ 2. NANO (Editor Clássico/Alternativo) ]", fg="green", bold=True)
    click.echo("O Nano é minimalista. Não suporta nativamente a divisão de tela (Premier/Pot) como o Micro.")
    click.secho("  • Atalhos Essenciais:", fg="yellow")
    click.echo("    - Ctrl + O     : Salvar arquivo (pressione Enter para confirmar o nome).")
    click.echo("    - Ctrl + X     : Sair do editor.")
    click.echo("    - Ctrl + W     : Buscar texto (Pesquisar).")
    click.echo("    - Alt + U      : Desfazer (Undo).")
    click.echo("    - Alt + E      : Refazer (Redo).")
    click.echo("    - Alt + A      : Iniciar seleção de texto (Marcar).")
    click.echo("    - Alt + 6      : Copiar o texto selecionado.")
    click.echo("    - Ctrl + U     : Colar o texto copiado / Cortar a linha inteira.")

    click.secho("\nDICA:", fg="cyan", bold=True)
    click.echo("Para programar com o Doxoade, recomendamos fortemente o uso do ")
    click.secho("Micro", fg="green", bold=True, nl=False)
    click.echo(" devido ao suporte de abas e atalhos customizados. Inicie com:")
    click.secho("  $ micro <nome_do_arquivo>\n", fg="white", bold=True)