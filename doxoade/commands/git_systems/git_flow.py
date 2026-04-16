# doxoade/doxoade/commands/git_systems/git_flow.py
import subprocess
from doxoade.tools.doxcolors import Fore, Style

class GitFlowManager:

    def __init__(self, root):
        self.root = root

    def create_branch(self, name):
        prefix = 'feature/' if not '/' in name else ''
        full_name = f'{prefix}{name}'
        print(f'{Fore.CYAN}🚀 Criando nova frente de trabalho: {full_name}{Style.RESET_ALL}')
        subprocess.run(['git', 'checkout', '-b', full_name])

    def list_branches(self):
        print(f'\n{Fore.WHITE}{Style.BRIGHT}🌿 Ramos da Árvore de Código:{Style.RESET_ALL}')
        subprocess.run(['git', 'branch', '-vv'])