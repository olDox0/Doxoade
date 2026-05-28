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
@click.option('--release', is_flag=True)
@click.option('--soteria/--no-soteria', default=True)
@click.option('--force', '-f', is_flag=True)
@click.pass_context
def metal_build(ctx, release, soteria, force):
    """Forja os fontes em binários executáveis."""
    # O status deve ser capturado fora do 'with' para ser retornado
    success = False
    with ExecutionLogger('metal_build', os.getcwd(), ctx.params) as logger:
        from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
        engine = NexusMetalEngine(os.getcwd())
        success = engine.build(release=release, use_soteria=soteria, force=force)
    
    return success # <--- [VITAL] O segredo da continuidade está aqui!

@metal_group.command('run', context_settings=dict(ignore_unknown_options=True))
@click.argument('target', required=False)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def metal_run(ctx, target, args):
    """Compila e executa o binário."""
    # 1. Invoca o build e recebe o veredito
    build_ok = ctx.invoke(metal_build)
    
    if build_ok:
        from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
        engine = NexusMetalEngine(os.getcwd())
        # 2. Só agora Hefesto abre os portões!
        engine.run_binary(target_name=target, extra_args=list(args))
    else:
        click.secho("\n[!] Execução cancelada: O build falhou.", fg="yellow")

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
    success = False
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
    return success

@metal_group.command('embedded')
@click.argument('target_path', type=click.Path(exists=True, file_okay=False))
@click.option('--soteria/--no-soteria', default=True, help="Embarca o escudo nativo.")
def metal_embedded(target_path, soteria):
    """🚢 Transplanta o DNA do Doxoade para um projeto externo (Modo Silo)."""
    from doxoade.tools.metalcraft.metal_engine import NexusMetalEngine
    
    # [VITAL] Passamos o diretório atual do sistema (o alvo)
    engine = NexusMetalEngine(target_path) 
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}🚢 [EMBARQUE] Iniciando transplante...{Style.RESET_ALL}")
    
    if engine.deploy_embedded(target_path, use_soteria=soteria):
        click.echo(f"\n   {Fore.GREEN}✔ DNA Nexus embarcado em: {target_path}{Style.RESET_ALL}")
    else:
        click.echo(f"\n   {Fore.RED}❌ Falha no transplante logístico.{Style.RESET_ALL}")
        
@metal_group.command('audit-bin')
@click.argument('target_exe', required=False)
def metal_audit_bin(target_exe):
    """🔬 Necropsia de Binário: Valida o DNA Sotéria e Assembly."""
    import shutil
    import subprocess
    
    exe_name = target_exe or "gordian_test.exe"
    # Procura nos locais prováveis de build
    candidates = [
        os.path.join("bin", exe_name),
        os.path.join(".doxoade", "metalcraft", "bin", exe_name)
    ]
    
    exe_path = next((c for c in candidates if os.path.exists(c)), None)

    if not exe_path:
        click.secho(f"   [!] Erro: Binário '{exe_name}' não localizado.", fg="red")
        return

    click.echo(f"{Fore.CYAN}🔬 [NECROPSIA] Analisando DNA de: {exe_name}{Style.RESET_ALL}")
    
    nm = shutil.which("nm") or shutil.which("nm.exe")
    if not nm:
        click.secho("   [!] Erro: nm.exe não encontrado no PATH.", fg="red")
        return

    try:
        res = subprocess.run([nm, exe_path], capture_output=True, text=True)
        symbols = res.stdout
        # Lista de Símbolos Críticos que provam a metalurgia correta
        dna = {
            "CORE": "soteria_init", 
            "VACCINE": "soteria_mark_var", 
            "ASM_ENGINE": "soteria_dump_hardware_state"
        }
        
        for label, sym in dna.items():
            status = f"{Fore.GREEN}✅" if sym in symbols else f"{Fore.RED}❌"
            click.echo(f"   • {label:<12}: {status} {sym}{Style.RESET_ALL}")
    except Exception as e:
        click.echo(f"   [!] Falha na necropsia: {e}")

@metal_group.command('setup-tools')
@click.pass_context
def metal_setup_tools(ctx):
    """🛠️  Provisionamento Automático: Baixa e instala o GCC/Toolchain."""
    from doxoade.tools.metalcraft.provisioner import download_w64devkit
    from pathlib import Path
    
    core_root = Path(__file__).resolve().parents[2]
    target_dir = core_root / "thirdparty" / "w64devkit"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"{Fore.CYAN}⚒️  Doxoade Metalcraft: Iniciando Configuração de Toolchain{Style.RESET_ALL}")
    
    if (target_dir / "bin" / "gcc.exe").exists():
        if not click.confirm(f"   {Fore.YELLOW}Compilador já detectado. Deseja reinstalar?{Style.RESET_ALL}"):
            return

    if download_w64devkit(target_dir):
        click.secho("\n✅ Toolchain pronto! GCC, Make e BusyBox instalados.", fg="green", bold=True)
        click.echo(f"   Local: {target_dir}")
    else:
        click.secho("\n❌ Erro ao configurar ambiente.", fg="red", bold=True)