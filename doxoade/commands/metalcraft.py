# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/metalcraft.py
import click
import os
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

@click.group('metal') # 'metal' é mais curto e forte
def metal_group():
    """⚒️  Nexus Metalcraft: Fundição Industrial de Binários C."""
    pass

@metal_group.command('build')
@click.option('--force', '-f', is_flag=True, help="Ignora o cache e reforja tudo.")
@click.pass_context
def metal_build(ctx, force):
    """Transforma fontes C em binários Gold Standard."""
    from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
    
    with ExecutionLogger('metal_build', '.', ctx.params):
        engine = NexusMetalEngine(os.getcwd())
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [HEFESTO FORGE] ---{Style.RESET_ALL}")
        success = engine.build()
        
        if success:
            click.secho("✔ Metalurgia concluída.", fg="green")

@metal_group.command('run')
@click.argument('target', required=False)
@click.pass_context
def metal_run(ctx, target):
    """Compila (se necessário) e executa o binário."""
    # 1. Garante que o sistema está atualizado
    # O invoke garante que o ExecutionLogger e o SSA sejam rodados
    ctx.invoke(metal_build)
    
    # 2. Se o build anterior falhou, o clique vai parar aqui.
    # Caso contrário, pegamos o motor e rodamos o binário.
    from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
    engine = NexusMetalEngine(os.getcwd())
    
    # Espaço visual para o output do programa
    click.echo("")
    engine.run_binary(target_name=target)

@metal_group.command('init')
@click.argument('name', required=False)
def metal_init(name):
    """Cria um projeto C 'vacinado' com Sotéria e configurado."""
    project_name = name or os.path.basename(os.getcwd())
    click.echo(f"⚒️  Iniciando Projeto Metalcraft: {project_name}")
    
    # 1. Cria Estrutura Industrial
    dirs = ['src', 'include', 'bin', 'lib', '.doxoade/metalcraft/obj']
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        
    # 2. Cria o metalcraft.toml (O Contrato)
    toml_content = f"""# Nexus Metalcraft Configuration
[project]
name = "{project_name}"
version = "1.0.0"
type = "executable"

[compiler]
engine = "gcc"
std = "c11"
opt = "O2"
shield = true         # Ativa Sotéria (Resgate Nativo)
incremental = true    # Recompila apenas mudanças

[paths]
sources = ["src/*.c"]
headers = ["include/"]
output  = "bin/"
"""
    with open("metalcraft.toml", "w") as f: f.write(toml_content)
    
    # 3. Cria um main.c de exemplo "Vacinável"
    main_c = """#include <stdio.h>

// Macros Sotéria (O Scribe cuidará disso no build)
int main(int argc, char** argv) {
    printf("Olá, Nexus! Sistema operacional e protegido.\\n");
    return 0;
}
"""
    with open("src/main.c", "w") as f: f.write(main_c)
    click.secho("✅ Fundição pronta! Tente: doxoade metal build", fg="green")
    click.secho("✅ Estrutura de metalurgia pronta.", fg="green")

@metal_group.command('build')
@click.option('--release', is_flag=True, help="Build de alta performance.")
@click.option('--soteria/--no-soteria', default=True, help="Ativa/Desativa o escudo de resgate.")
@click.option('--force', '-f', is_flag=True, help="Força a re-compilação.") # <--- ADICIONE ESTA LINHA
@click.pass_context # <--- ADICIONE ISSO PARA PODER ACESSAR O CONTEXTO
def metal_build(ctx, release, soteria, force): # <--- ADICIONE O 'force' AQUI
    """Forja os fontes em binários executáveis."""
    # O ExecutionLogger precisa dos params (ctx.params)
    with ExecutionLogger('metal_build', os.getcwd(), ctx.params) as logger:
        from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
        
        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔨 Iniciando Forja...{Style.RESET_ALL}")
        engine = NexusMetalEngine(os.getcwd())
        
        # Passamos o force para o motor
        success = engine.build(release=release, use_soteria=soteria, force=force)
        
        if success:
            click.secho("\n✔ Binário fundido com sucesso!", fg="green", bold=True)
        else:
            click.secho("\n✘ Falha na fundição. Chame o Lazarus para necropsia.", fg="red", bold=True)