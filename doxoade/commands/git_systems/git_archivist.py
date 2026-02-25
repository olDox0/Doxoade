# -*- coding: utf-8 -*-
# doxoade/commands/git_systems/git_archivist.py
"""
Git Archivist - O Livro dos Mortos de Osíris v1.0.
Especialista em manipulação de histórico e remoção de evidências (PASC 2.0).
"""
import subprocess
import sys
import os
from doxoade.tools.doxcolors import Fore, Style
from ...tools.filesystem import _get_venv_python_executable
class GitArchivist:
    def __init__(self, root):
        self.root = root
    def nuclear_purge(self, patterns: list, dry_run: bool = False):
        """Purga profunda via git-filter-repo (Standard Osíris)."""
        # 1. Garante que estamos na raiz
        os.chdir(self.root)
        
        python_exe = _get_venv_python_executable(self.root) or sys.executable
        # 2. Constrói o comando de forma inteligente
        cmd = [python_exe, "-m", "git_filter_repo", "--force"]
        
        if dry_run:
            cmd.append("--analyze")
        for p in patterns:
            p = p.replace('\\', '/')
            # Se o padrão tem wildcard (*), usa path-glob, senão usa path simples
            if '*' in p:
                cmd.extend(['--path-glob', p])
            else:
                cmd.extend(['--path', p])
        
        cmd.append('--invert-paths')
        try:
            # PASC-8.8: Fluxo Explícito
            res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', shell=False)
            
            if res.returncode == 0:
                return True, "O passado foi reescrito. Histórico purificado."
            else:
                return False, res.stderr
        except Exception as e:
            return False, str(e)
    def remove_files_from_commit(self, commit_hash, files: list):
        """Remove arquivos específicos de um commit já realizado (PASC 1.1)."""
        print(f"{Fore.YELLOW}🧪 Iniciando cirurgia no commit {commit_hash}...{Style.RESET_ALL}")
        
        # 1. Validação de estado (OSL 10)
        if self._is_dirty():
            return False, "Working tree está suja. Faça save ou stash antes da cirurgia."
        try:
            # Estratégia: Soft Reset -> Unstage -> Re-commit
            # Se for o último commit (HEAD), é simples. Se for antigo, exige rebase.
            is_head = self._is_head(commit_hash)
            
            if is_head:
                for f in files:
                    subprocess.run(['git', 'reset', 'HEAD^', f], check=True, capture_output=True)
                
                # Refaz o commit mantendo a mensagem original
                subprocess.run(['git', 'commit', '--amend', '--no-edit'], check=True, capture_output=True)
                return True, "Arquivos removidos do commit HEAD."
            else:
                return False, "Modificar commits antigos via CLI exige Rebase Interativo (Feature em Lab)."
        except Exception as e:
            return False, str(e)
    def delete_commit(self, commit_hash):
        """Apaga um commit específico e volta os arquivos para o Stage."""
        if not self._is_head(commit_hash):
            return False, "Por segurança, só é permitido apagar o último commit (HEAD) via CLI."
        
        try:
            # Volta o ponteiro um passo atrás, mantendo as mudanças nos arquivos
            subprocess.run(['git', 'reset', '--soft', 'HEAD^'], check=True)
            return True, "Commit desfeito. As mudanças voltaram para o Stage (Prontas para novo save)."
        except Exception as e:
            return False, str(e)
    def _is_dirty(self):
        res = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        return bool(res.stdout.strip())
    def _is_head(self, commit_hash):
        head_hash = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        return head_hash.startswith(commit_hash) or commit_hash.lower() == "head"
        
# doxoade/commands/git_systems/git_archivist.py
    def list_commit_assets(self, commit_hash, show_all=False):
        """Lista arquivos de um commit respeitando as regras de ignore do Doxoade."""
        target = commit_hash if commit_hash else "HEAD"
        
        try:
            from ...dnm import DNM
            dnm = DNM(self.root)
            
            cmd = ['git', 'ls-tree', '-r', '-l', target]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if res.returncode != 0:
                return False, f"Commit '{target}' não encontrado."
            files_data = []
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5:
                    size_bytes = int(parts[3]) if parts[3].isdigit() else 0
                    path = parts[4]
                    
                    # PASC-8.17: Filtro de Soberania
                    # Se show_all for False, ignora o que o DNM marcar como ignorado
                    if not show_all and dnm.is_ignored(os.path.join(self.root, path)):
                        continue
                        
                    files_data.append({
                        'path': path,
                        'size': size_bytes / 1024,
                        'type': os.path.splitext(path)[1]
                    })
            
            return True, files_data
        except Exception as e:
            return False, str(e)