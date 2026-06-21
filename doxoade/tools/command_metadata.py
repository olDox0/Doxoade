# doxoade/tools/command_metadata.py
from doxoade.tools.doxcolors import Fore, Style

# Mapa de metadados: ajuda, ícone/prefixo
COMMAND_META = {
    'android': ('Gerenciamento de ambientes Android (Termux).', '🤖'),
    'check': ('Auditoria de integridade e linting do código.', '🔍'),
    'db': ('Hades Engine: Diagnóstico e manipulação de dados.', '💾'),
    'debug': ('Autópsia forense e monitoramento de performance.', '🩺'),
    'git': ('Nexus-Git: Gestão profissional de fluxo e segurança.', '🛠'),
    'hack': ('Sistema de defesa e pentest técnico.', '🛡'),
    'init': ('Gênese: Cria um novo silo soberano do projeto.', '🚀'),
    'lab': ('Sandbox de alta segurança e teste.', '🧪'),
    'vulcan': ('Projeto Vulcano: Alta performance nativa (C/Cython).', '🔥'),
}

def format_help(cmd_name: str, desc: str, icon: str = '•') -> str:
    return f"{icon} {Fore.CYAN}{cmd_name:<16}{Style.RESET_ALL} {desc}"