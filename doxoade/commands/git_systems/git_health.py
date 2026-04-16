# doxoade/doxoade/commands/git_systems/git_health.py
import subprocess
import sys
import click
from doxoade.tools.doxcolors import Fore, Style

class DependencyGuard:

    def __init__(self, root):
        self.root = root

    def check_health(self, auto_fix=False):
        print(f'{Fore.CYAN}🛡  [DEPENDABOT-LOCAL] Analisando suprimentos...{Style.RESET_ALL}')
        python_exe = sys.executable
        try:
            print('   > Verificando vulnerabilidades (Safety Audit)...')
            res = subprocess.run([python_exe, '-m', 'safety', 'check', '-r', 'requirements.txt'], capture_output=True, text=True)
            if res.returncode != 0:
                print(Fore.RED + '   ✘ Vulnerabilidades encontradas!')
                print(Style.DIM + res.stdout)
            else:
                print(Fore.GREEN + '   ✔ Nenhuma vulnerabilidade conhecida detectada.')
            print('\n   > Verificando versões obsoletas...')
            res_out = subprocess.run([python_exe, '-m', 'pip', 'list', '--outdated'], capture_output=True, text=True)
            if res_out.stdout:
                print(Fore.YELLOW + '   ⚠ Dependências desatualizadas:')
                print(Style.DIM + res_out.stdout)
                if auto_fix:
                    self._perform_rebuild_protocol()
            else:
                print(Fore.GREEN + '   ✔ Todas as dependências estão no Estado de Ouro.')
        except Exception as e:
            print(Fore.RED + f'   ✘ Falha no diagnóstico de dependências: {e}')

    def _perform_rebuild_protocol(self):
        """Aciona o Protocolo Fênix para cura total."""
        if click.confirm(f"\n{Fore.CYAN}Deseja rodar o 'doxoade rebuild' para curar o ambiente?"):
            subprocess.run(['doxoade', 'rebuild'])