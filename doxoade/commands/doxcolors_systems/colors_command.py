# -*- coding: utf-8 -*-
import click
import os
import re
import shutil
import time

from datetime import datetime
from pathlib import Path

import doxoade.tools as dox_tools

# Localização do motor no Doxoade
DOXCOLORS_SOURCE_PATH = Path(dox_tools.__file__).parent / 'doxcolors.py'

# Template de configuração
COLORS_CONF_TEMPLATE = """
# Padrão Nexus de Identidade Visual
[PRIMARY]   = #006CFF
[SUCCESS]   = #26bc5f
[ERROR]     = #FF6700
[WARNING]   = #E8AA00
[STABLE]    = #B0B0B0
[VOLATILE]  = #FF00FF
[DEBUG]     = 1;30
""".strip()

class ColorMigrator:
    def __init__(self, target_path, apply=False, module_prefix='utils'):
        self.target_path = Path(target_path).resolve()
        self.apply = apply
        self.modifications = 0
        self.module_prefix = module_prefix
        self.target_module = f"{module_prefix}.doxcolors"

    def run(self):
        label = "AUDITORIA (DRY-RUN)" if not self.apply else "MIGRAÇÃO REAL"
        click.secho(f"🎨 Doxcolors Embedded Migration: {label}", fg="cyan", bold=True)
        
        dest_dir = self._find_best_dest()
        
        if self.apply:
            self._inject_file(dest_dir)
        else:
            click.echo(f"📍 Destino planejado: {dest_dir.relative_to(self.target_path)}/doxcolors.py")

        self._scan_and_refactor()
        
        click.echo('\n' + '─' * 60)
        status = "seriam alterados" if not self.apply else "foram modificados"
        click.secho(f"✔ Resumo: {self.modifications} arquivo(s) {status}.", fg="green", bold=True)

    def _find_best_dest(self) -> Path:
        for name in [self.module_prefix, 'utils', 'tools']:
            candidate = self.target_path / name
            if candidate.exists() and candidate.is_dir():
                return candidate
        return self.target_path

    def _inject_file(self, dest_dir: Path):
        """Injeta o motor doxcolors.py com Header de Identidade Nexus."""
        target_file = dest_dir / 'doxcolors.py'
        
        if not DOXCOLORS_SOURCE_PATH.exists():
            click.secho(f"   [FALHA] Fonte não encontrada em {DOXCOLORS_SOURCE_PATH}", fg="red")
            return

        # 1. Lê o conteúdo original do motor
        source_content = DOXCOLORS_SOURCE_PATH.read_text(encoding='utf-8')

        # 2. Gera o Header dinâmico
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = (
            f"# -*- coding: utf-8 -*-\n"
            f"# {'─' * 60}\n"
            f"# NEXUS UI ENGINE (Embedded Version)\n"
            f"# Sincronizado por: Doxoade Control\n"
            f"# Data: {timestamp}\n"
            f"# Projeto Alvo: {self.target_path.name}\n"
            f"# Compliance: MPoT-1, PASC-6.4 (High-Performance UI)\n"
            f"# {'─' * 60}\n\n"
        )

        # 3. Limpeza: Remove headers de desenvolvimento originais se existirem
        # Evita duplicar a linha de coding: utf-8
        clean_content = re.sub(r'^# -\*- coding: utf-8 -\*-\n', '', source_content)
        
        # 4. Combina e salva
        final_code = header + clean_content
        
        try:
            target_file.write_text(final_code, encoding='utf-8')
            click.secho(f"   [OK] Motor Nexus injetado e atualizado em: {target_file.name}", fg="green")
        except Exception as e:
            click.secho(f"   [ERRO] Falha na escrita do motor: {e}", fg="red")

    def _scan_and_refactor(self):
        ignore_dirs = {'.git', 'venv', '__pycache__', 'build', 'dist', 'sysutils.egg-info'}
        for root, dirs, files in os.walk(self.target_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file.endswith('.py') and file != 'doxcolors.py':
                    self._refactor_file(Path(root) / file)

    def _refactor_file(self, file_path: Path):
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if "colorama" not in content: return

            lines = content.splitlines(keepends=True)
            new_lines, made_change, diff_log = [], False, []

            for i, line in enumerate(lines):
                new_line = line
                # Caso A: from colorama import Fore, Style, init
                if "from colorama import" in line:
                    # Remove o 'init' da lista de nomes e limpa vírgulas extras
                    clean_names = line.replace("from colorama import", "").strip()
                    names = [n.strip() for n in clean_names.split(",") if n.strip() != "init"]
                    new_line = f"from {self.target_module} import {', '.join(names)}\n"
                
                # Caso B: import colorama
                elif "import colorama" in line:
                    new_line = f"import {self.target_module} as colorama\n"
                
                # Caso C: chamada de função init() isolada
                elif "init(" in line and "colorama" in line:
                    new_line = "" # Remove a linha completamente

                if new_line != line:
                    made_change = True
                    diff_log.append((i + 1, line.strip(), new_line.strip()))
                    if new_line == "": continue
                new_lines.append(new_line)

            if made_change:
                self.modifications += 1
                click.secho(f"\n📝 {file_path.relative_to(self.target_path)}", fg="white", bold=True)
                for ln, old, new in diff_log:
                    click.echo(f"   L{ln}: ", nl=False)
                    click.secho(f"- {old}", fg="red", nl=False)
                    if new:
                        click.echo("  ->  ", nl=False)
                        click.secho(new, fg="green")
                    else:
                        click.secho(" (REMOVIDO)", fg="yellow")

                if self.apply:
                    shutil.copy2(file_path, file_path.with_suffix('.py.bak'))
                    file_path.write_text("".join(new_lines), encoding='utf-8')
                    click.secho("   [SALVO]", fg="green")
        except Exception as e:
            click.echo(f"   [ERRO] {file_path.name}: {e}")

# --- GRUPO CLI ---

@click.group('doxcolors', invoke_without_command=True)
@click.option('--path', '-p', default='.', type=click.Path(exists=True))
@click.option('--apply', is_flag=True, help='Aplica as mudanças.')
@click.option('--prefix', default='utils', help='Pasta/Módulo onde o motor será injetado.')
@click.pass_context
def doxcolors_cmd(ctx, path, apply, prefix):
    """Refatoração Colorama -> Doxcolors Embedded."""
    if ctx.invoked_subcommand is None:
        migrator = ColorMigrator(target_path=path, apply=apply, module_prefix=prefix)
        migrator.run()

@doxcolors_cmd.command('config')
def config():
    """Cria arquivo colors.conf."""
    config_file = Path('colors.conf')
    if config_file.exists() and not click.confirm("Sobrescrever colors.conf?"): return
    config_file.write_text(COLORS_CONF_TEMPLATE, encoding='utf-8')
    click.secho("[OK] colors.conf criado.", fg="green")
    
@doxcolors_cmd.command('play')
@click.argument('file', type=click.Path(exists=True))
@click.option('--interval', '-i', default=0.1, help="Velocidade da animação.")
@click.option('--loops', '-l', default=1, help="Quantidade de repetições.")
def play_animation_command(file, interval, loops):
    """Reproduz um arquivo de animação Nexus (.nxa ou .txt)."""
    from doxoade.tools.doxcolors import colors
    
    frames = colors.UI.load_animation(file)
    if not frames:
        click.secho("[ERRO] Nenhum frame encontrado no arquivo.", fg="red")
        return
        
    click.secho(f"[*] Reproduzindo: {file}", fg="cyan")
    colors.UI.play_animation(frames, interval=interval, loops=loops)
    
@doxcolors_cmd.command('new-anim')
@click.argument('name')
def create_anim_template(name):
    """Cria um template de animação para o usuário editar."""
    filename = f"{name}.nxa"
    template = "Frame 1\n===FRAME===\nFrame 2\n===FRAME===\nFrame 3"
    Path(filename).write_text(template, encoding='utf-8')
    click.secho(f"[OK] Template criado: {filename}", fg="green")
    
@doxcolors_cmd.command('load')
@click.argument('file', type=click.Path(exists=True))
@click.option('--seconds', '-s', default=3)
@click.option('--interval', '-i', default=0.1)
@click.option('--debug', '-d', is_flag=True, help="Habilita moldura de debug.")
def load_test_command(file, seconds, interval, debug):
    """Testa uma animação assíncrona com proteção contra ghosting."""
    from doxoade.tools.doxcolors import colors
    
    click.secho(f"[*] Testando: {os.path.basename(file)}", fg="cyan")
    
    # CORREÇÃO: Usar o loader da UI que agora suporta debug
    try:
        with colors.UI.loader(file, interval=interval, debug=debug) as anim:
            time.sleep(seconds)
    except KeyboardInterrupt:
        pass
        
    click.secho("\n[OK] Teste finalizado.", fg="green")
    
@doxcolors_cmd.command('play')
@click.argument('file', type=click.Path(exists=True))
@click.option('--interval', '-i', default=0.1)
@click.option('--loops', '-l', default=1)
@click.option('--ping-pong', '-pp', is_flag=True, help="Efeito ida e volta.")
def play_animation_command(file, interval, loops, ping_pong):
    from doxoade.tools.doxcolors import colors
    frames = colors.UI.load_animation(file)
    # Usamos a classe diretamente para suportar loops no play estático
    # (Ou podemos usar o loader se preferir assíncrono)
    colors.UI.play_animation(frames, interval=interval, loops=loops)

@doxcolors_cmd.command('load')
@click.argument('file', type=click.Path(exists=True))
@click.option('--seconds', '-s', default=3)
@click.option('--interval', '-i', default=0.1)
@click.option('--debug', '-d', is_flag=True)
@click.option('--ping-pong', '-pp', is_flag=True, help="Efeito ida e volta.")
def load_test_command(file, seconds, interval, debug, ping_pong):
    from doxoade.tools.doxcolors import colors
    click.secho(f"[*] Modo {'Ping-Pong' if ping_pong else 'Linear'}: {os.path.basename(file)}", fg="cyan")
    
    with colors.UI.loader(file, interval=interval, debug=debug, ping_pong=ping_pong) as anim:
        time.sleep(seconds)
    
    click.secho("\n[OK] Teste finalizado.", fg="green")
    
@doxcolors_cmd.command('probe')
def probe_colors():
    """Testa e exibe a capacidade cromática do terminal atual."""
    support = DoxColors.detect_support()
    level_map = {0: "Nenhum", 4: "ANSI 16", 8: "ANSI 256", 24: "TrueColor (24-bit)"}
    
    click.echo(f"🔍 [PROBE] Nível de Suporte: {Fore.PRIMARY}{level_map.get(support)}{Style.RESET_ALL}")
    
    # Teste de Gradiente
    test_text = "NEXUS PERFORMANCE UI"
    if support == 24:
        click.echo("🎨 Teste TrueColor: " + NexusUI.gradient_text(test_text))
    else:
        click.echo("🎨 Teste Fallback: " + Fore.PRIMARY + test_text + Style.RESET_ALL)

    # Exibe a paleta atual do colors.conf
    click.echo("\n📋 Paleta Ativa (colors.conf):")
    for color_name in ['PRIMARY', 'SUCCESS', 'ERROR', 'WARNING', 'STABLE', 'EMERALD', 'ORANGE']:
        if hasattr(Fore, color_name):
            c = getattr(Fore, color_name)
            click.echo(f"  • {color_name:<10}: {c}██████{Style.RESET_ALL} (Code: {c.replace(chr(27),'ESC')})")