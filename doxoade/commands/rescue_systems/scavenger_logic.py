# -*- coding: utf-8 -*-
# doxoade/commands/rescue_systems/scavenger_logic.py (v2)
"""
Lazarus Scavenger Logic - v1.0.
Mineração de objetos órfãos e reconstrução de material volátil.
"""
import os
import subprocess
import datetime
from colorama import Fore, Style

class Scavenger:
    def __init__(self, root):
        self.root = root

    def find_dangling_blobs(self):
        """Busca conteúdos de arquivos que ficaram órfãos no banco do Git."""
        print(f"{Fore.YELLOW}🔍 Vasculhando o abismo de objetos órfãos (git fsck)...{Style.RESET_ALL}")
        try:
            # Encontra hashes de arquivos que não pertencem a nenhum commit/branch
# [DOX-UNUSED]             cmd = ['git', 'fsck', '--lost-found']
# [DOX-UNUSED]             res = subprocess.run(cmd, capture_output=True, text=True)
            
            # Os objetos encontrados ficam em .git/lost-found/other
            lost_dir = os.path.join(self.root, '.git', 'lost-found', 'other')
            if not os.path.exists(lost_dir):
                return []

            recovered = []
            for blob_hash in os.listdir(lost_dir):
                path = os.path.join(lost_dir, blob_hash)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Filtra apenas o que parece ser código do Doxoade
                    if "doxoade" in content or "import click" in content:
                         recovered.append({
                             'hash': blob_hash,
                             'preview': content[:100].replace('\n', ' '),
                             'full': content,
                             'date': datetime.datetime.fromtimestamp(os.path.getmtime(path))
                         })
            return recovered
        except Exception as e:
            print(f"{Fore.RED}Erro no fsck: {e}{Style.RESET_ALL}")
            return []

    def scan_npp_backups(self):
        """Varre pastas nppBackup em busca de versões recentes antes do reset."""
        found = []
        for root, dirs, files in os.walk(self.root):
            if 'nppBackup' in root:
                for f in files:
                    full_p = os.path.join(root, f)
                    found.append({
                        'name': f,
                        'path': full_p,
                        'date': datetime.datetime.fromtimestamp(os.path.getmtime(full_p))
                    })
        return sorted(found, key=lambda x: x['date'], reverse=True)
        
    def deep_scavenge_reflog(self, keyword):
        """Busca no reflog por hashes de commits que foram 'apagados' mas ainda constam no rastro."""
        print(f"{Fore.YELLOW}🔎 Escaneando Reflog em busca de: {keyword}...{Style.RESET_ALL}")
        try:
            # -g caminha pelo reflog em vez de caminhar pela árvore atual
            cmd = ['git', 'log', '-g', '--pretty=format:%h - %s', '--grep', keyword]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if not res.stdout.strip():
                # Tenta sem o filtro grep para listar tudo o que aconteceu antes da purga
                cmd = ['git', 'reflog', '-n', '50']
                res = subprocess.run(cmd, capture_output=True, text=True)
            
            return res.stdout.strip().splitlines()
        except Exception:
            return []

    def recover_from_npp_session(self):
        """Tenta localizar o arquivo de sessão do Notepad++ que guarda arquivos não salvos."""
        import os
        npp_path = os.path.expandvars(r'%APPDATA%\Notepad++\backup')
        if not os.path.exists(npp_path):
            return []
        
        backups = []
        for f in os.listdir(npp_path):
            full_p = os.path.join(npp_path, f)
            backups.append({
                'name': f,
                'path': full_p,
                'time': datetime.datetime.fromtimestamp(os.path.getmtime(full_p))
            })
        return sorted(backups, key=lambda x: x['time'], reverse=True)