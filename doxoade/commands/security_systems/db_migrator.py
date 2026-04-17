# doxoade/doxoade/commands/security_systems/db_migrator.py
import os
import shutil
import re
from pathlib import Path
import click

class NexusDBMigrator:
    def __init__(self, target_path):
        self.target_path = Path(target_path).resolve()
        # Local de origem do wrapper no Doxoade
        self.source_wrapper = Path(__file__).resolve().parents[2] / 'tools' / 'aegis' / 'nexus_db.py'

    def inject_wrapper(self):
        """Copia o nexus_db.py para o projeto alvo."""
        # Se for o próprio doxoade, ele já está lá. 
        # Se for projeto externo, injeta em tools/
        dest_dir = self.target_path / 'doxoade' / 'tools' / 'aegis'
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / 'nexus_db.py'
        
        if not dest_file.exists():
            shutil.copy2(self.source_wrapper, dest_file)
            click.echo(f"  [+] Wrapper injetado em: {dest_file.name}")

    def refactor_imports(self):
        """Substitui 'import sqlite3' pela versão segura."""
        # Busca em todos os arquivos .py do alvo
        from doxoade.dnm import DNM
        dnm = DNM(str(self.target_path))
        files = dnm.scan(extensions=['py'])
        
        count = 0
        for fpath in files:
            p = Path(fpath)
            # Não refatorar o próprio wrapper
            if p.name == "nexus_db.py": continue
            
            content = p.read_text(encoding='utf-8')
            new_content = content
            
            # Troca Import Direto
            if "import sqlite3" in new_content and "nexus_db" not in new_content:
                new_content = new_content.replace(
                    "import sqlite3", 
                    "import doxoade.tools.aegis.nexus_db as sqlite3  # noqa"
                )
            
            # Troca From/Import
            if "from sqlite3 import" in new_content:
                new_content = re.sub(
                    r"from doxoade.tools.aegis.nexus_db import (.*)",   # noqa
                    r"from doxoade.tools.aegis.nexus_db import \1  # noqa", 
                    new_content
                )

            if new_content != content:
                p.write_text(new_content, encoding='utf-8')
                click.echo(f"  [FIX] {p.name}")
                count += 1
        
        click.echo(f"  [*] {count} arquivos sincronizados.")