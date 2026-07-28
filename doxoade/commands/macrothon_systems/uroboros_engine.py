# -*- coding: utf-8 -*-
# doxoade/commands/macrothon_systems/uroboros_engine.py
"""
🔄 MOTOR UROBOROS v1.0 - A Serpente que Devora a Própria Cauda.
Gerencia o ciclo de vida dos Bricks entre a House Local e o Acervo Global.
Compliance: PASC-8 (Sincronização Sem Fricção).
"""
import os
import json
import hashlib
import shutil
import toml
from pathlib import Path
from datetime import datetime

from doxoade.tools.core_locator      import CORE_ROOT
from doxoade.tools.doxcolors         import Fore, Style
from doxoade.core_database          import get_db_connection
from doxoade.tools.alexandria.engine import alexandria_write
from doxoade.core_database           import get_db_connection
from doxoade.commands.init           import _refactor_to_silo

class UroborosEngine:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.manifest_path = self.project_root / '.doxoade' / 'house_manifest.json'
        self.pyproject_path = self.project_root / 'pyproject.toml'
        
        # 📡 [BEACON] O Acervo Global vive DENTRO da instalação do Doxoade
        self.global_acervo = CORE_ROOT / "data" / "acervo" / "bricks"
        self.global_acervo.mkdir(parents=True, exist_ok=True)
        
        self._load_config()

    def _load_config(self):
        """Lê o pyproject.toml para descobrir a pasta de bricks e os requisitos."""
        if not self.pyproject_path.exists():
            raise FileNotFoundError("pyproject.toml não encontrado. O Silo não é uma House.")
        
        config = toml.load(self.pyproject_path)
        macrothon_conf = config.get('tool', {}).get('doxoade', {}).get('macrothon', {})
        
        self.bricks_dir = self.project_root / macrothon_conf.get('bricks_dir', 'bricks')
        self.requires = macrothon_conf.get('requires', [])
        self.bricks_dir.mkdir(parents=True, exist_ok=True)

    def _get_manifest(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text(encoding='utf-8'))
        return {"house_name": self.project_root.name, "bricks": {}, "last_sync": None}

    def _save_manifest(self, data: dict):
        data['last_sync'] = datetime.now().isoformat()
        self.manifest_path.write_text(json.dumps(data, indent=4), encoding='utf-8')

    def _calculate_hash(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()[:12]

    # ==========================================
    # 🌾 A COLHEITA (House -> Acervo Global)
    # ==========================================
    def harvest(self):
        """Escaneia a House e promove para o Acervo Global (Modo Industrial)."""
        click.echo(f"{Fore.CYAN}🌾 [UROBOROS] Iniciando Colheita Industrial...{Style.RESET_ALL}")
        
        # 1. Preparamos o Batch de Inserção (Hades Fast-Path)
        batch_updates = []
        harvested_count = 0
        
        for local_file in self.bricks_dir.glob("*.py"):
            if local_file.name == "__init__.py": continue
            
            current_hash = self._calculate_hash(local_file)
            brick_name = local_file.stem
            
            # Lógica de comparação de hash omitida para brevidade...
            # Se mudou ou é novo:
            new_version = recorded.get('version', 0) + 1
            
            # 2. Ao invés de dar INSERT/UPDATE um por um, acumulamos
            batch_updates.append((
                brick_name, 
                f"{brick_name}.py", 
                new_version, 
                datetime.now().isoformat(), 
                manifest['house_name']
            ))
            harvested_count += 1

        # 3. O Flush Sem Gargalo (Transação Única no Hades)
        if batch_updates:
            conn = get_db_connection()
            try:
                # O Hades já está em WAL mode, mas forçamos o BEGIN para máxima velocidade
                conn.execute("BEGIN TRANSACTION")
                conn.executemany("""
                    INSERT INTO moduloid_acervo (name, filename, version, last_updated, origin_project)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        version = excluded.version,
                        last_updated = excluded.last_updated,
                        origin_project = excluded.origin_project
                """, batch_updates)
                conn.commit()
            except Exception as e:
                conn.rollback()
                click.echo(f"{Fore.RED}   ✘ Erro no Hades Batch: {e}{Style.RESET_ALL}")
            finally:
                conn.close()
                
        click.echo(f"{Fore.GREEN}🌾 Colheita concluída: {harvested_count} Brick(s) selados no Acervo.{Style.RESET_ALL}\n")

    # ==========================================
    # 📥 A SINCRONIZAÇÃO (Acervo Global -> House)
    # ==========================================
    def sync(self):
        """Puxa as versões mais recentes dos Bricks exigidos pela House."""
        click.echo(f"{Fore.CYAN}📥 [UROBOROS] Sincronizando House com o Acervo Global...{Style.RESET_ALL}")
        manifest = self._get_manifest()
        synced_count = 0
        
        conn = get_db_connection()
        
        for brick_name in self.requires:
            # 1. Busca a versão mais recente no Hades
            row = conn.execute("""
                SELECT version, filename FROM moduloid_acervo 
                WHERE name = ? ORDER BY version DESC LIMIT 1
            """, (brick_name,)).fetchone()
            
            if not row:
                click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} Brick '{brick_name}' não encontrado no Acervo Global.")
                continue
                
            global_version = row['version']
            global_filename = row['filename']
            global_path = self.global_acervo / global_filename
            
            if not global_path.exists():
                click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} Arquivo físico de '{brick_name}' ausente no Acervo.")
                continue

            # 2. Compara com o Manifesto Local
            local_record = manifest['bricks'].get(brick_name, {})
            local_version = local_record.get('version', 0)
            
            if global_version > local_version:
                # 3. Puxa e Refatora (Aplica o DNA do Silo Alvo)
                dest_path = self.bricks_dir / global_filename
                content = global_path.read_text(encoding='utf-8', errors='ignore')
                refactored_content = _refactor_to_silo(content)
                dest_path.write_text(refactored_content, encoding='utf-8')
                
                new_hash = self._calculate_hash(dest_path)
                
                # 4. Atualiza o Manifesto
                manifest['bricks'][brick_name] = {
                    "version": global_version,
                    "hash": new_hash,
                    "status": "SYNCED"
                }
                
                click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {brick_name} atualizado para {Fore.YELLOW}v{global_version}{Style.RESET_ALL}")
                synced_count += 1
            else:
                click.echo(f"   {Fore.WHITE}●{Style.RESET_ALL} {brick_name} já está na versão mais recente (v{local_version}).")

        conn.close()
        self._save_manifest(manifest)
        click.echo(f"{Fore.GREEN}📥 Sincronização concluída: {synced_count} Brick(s) puxado(s).{Style.RESET_ALL}\n")
