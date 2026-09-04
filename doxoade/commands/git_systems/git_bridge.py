# doxoade/commands/git_systems/git_bridge.py
"""
GitHub Bridge - Hermes Communication Bridge v1.0.
Integração com GitHub Issues e PRs via API/CLI.
"""
import subprocess
from doxoade.tools.doxcolors import Fore, Style


class GitHubBridge:
    def __init__(self, root: str = '.'):
        self.root = root

    def display_issues(self):
        """Lista issues locais ou via GitHub CLI ('gh') se disponível."""
        print(f"{Fore.CYAN}🪽 [HERMES-BRIDGE] Verificando issues do Olimpo...{Style.RESET_ALL}")
        try:
            res = subprocess.run(['gh', 'issue', 'list'], capture_output=True, text=True, cwd=self.root)
            if res.returncode == 0 and res.stdout.strip():
                print(res.stdout)
            else:
                print(f"{Fore.YELLOW}Nenhuma issue encontrada ou GitHub CLI ('gh') não configurado.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}GitHub CLI não detectado no PATH. ({e}){Style.RESET_ALL}")
