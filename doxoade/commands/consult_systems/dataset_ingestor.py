# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/dataset_ingestor.py
"""
🔨 HEFESTO + 🌊 POSEIDON + 💀 HADES — Ingestor de Datasets (Local ou Remoto).
- Detecção automática de caminho local vs URL.
- Parse de JSONL em O(1) de RAM (leitura linha a linha).
- Inserção em lote (Batch) no SQLite FTS5 para máxima velocidade.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations
import os
import sys
import json
import sqlite3
import urllib.request
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn

console = Console()

class DatasetIngestor:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=60.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = OFF") # Ultra-fast para bulk insert
        conn.execute("PRAGMA cache_size = -64000")
        return conn

    def _infer_schema(self, data: Dict[str, Any]) -> tuple[str, str]:
        """Mapeia campos comuns de datasets para title/content de forma resiliente."""
        title, content = "Unknown", ""
        
        if "instruction" in data:
            title = data.get("instruction", "Prompt")
            content = data.get("output", data.get("response", data.get("answer", "")))
        elif "question" in data:
            title = data.get("question", "Query")
            content = data.get("answer", data.get("solution", ""))
        elif "code" in data or "content" in data:
            title = data.get("filename", data.get("repo_name", "Snippet"))
            content = data.get("code", data.get("content", ""))
            if "docstring" in data:
                title = f"{title} - {data['docstring'].split(chr(10))[0][:50]}"
        else:
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 50:
                    content = v
                    title = data.get("title", data.get("id", k))
                    break
        return str(title).strip(), str(content).strip()

    def ingest(self, source: str, dataset_name: str, limit: int = 0):
        """Roteador: processa arquivo local ou faz download de URL."""
        path = Path(source)
        
        if path.exists() and path.is_file():
            console.print(f"[cyan]📂 Processando arquivo local:[/cyan] {path}")
            self._process_and_index(path, dataset_name, limit)
        else:
            console.print(f"[cyan]📥 Iniciando download de:[/cyan] {source}")
            req = urllib.request.Request(source, headers={'User-Agent': 'Doxoade-Ingestor/1.0'})
            temp_file = self.db_path.parent / f"temp_{dataset_name}.jsonl"
            
            try:
                with urllib.request.urlopen(req) as response, open(temp_file, 'wb') as out_file:
                    total_size = int(response.headers.get('Content-Length', 0))
                    with Progress(
                        SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
                        BarColumn(), DownloadColumn(), TransferSpeedColumn()
                    ) as progress:
                        task = progress.add_task("Baixando dataset", total=total_size)
                        while True:
                            chunk = response.read(8192)
                            if not chunk: break
                            out_file.write(chunk)
                            progress.update(task, advance=len(chunk))
            except Exception as e:
                console.print(f"[red]❌ Falha no download: {e}[/red]")
                return
            
            self._process_and_index(temp_file, dataset_name, limit)
            if temp_file.exists():
                temp_file.unlink() # Limpeza automática

    def _process_and_index(self, file_path: Path, dataset_name: str, limit: int):
        """Motor de parse em stream e inserção em lote no FTS5."""
        console.print(f"[yellow]⚙️ Processando e indexando {dataset_name}...[/yellow]")
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        insert_stmt = "INSERT INTO docs_fts (path, title, content) VALUES (?, ?, ?)"
        batch = []
        batch_size = 2000
        total_indexed = 0
        skipped = 0

        try:
            conn.execute("BEGIN")
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if limit > 0 and total_indexed >= limit:
                        break
                    try:
                        data = json.loads(line)
                        
                        # 🛡️ BLINDAGEM: Ignora arrays JSON ou primitivos, aceita apenas objetos (dict)
                        if not isinstance(data, dict):
                            skipped += 1
                            continue
                            
                        title, content = self._infer_schema(data)
                        if title and content:
                            path = f"{dataset_name}/entry_{line_num}"
                            batch.append((path, title, content))
                            
                            if len(batch) >= batch_size:
                                cursor.executemany(insert_stmt, batch)
                                conn.commit()
                                batch = []
                                total_indexed += batch_size
                                console.print(f"  ↳ {total_indexed} registros indexados...", style="dim")
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
            
            # Commit final do batch restante
            if batch:
                cursor.executemany(insert_stmt, batch)
                conn.commit()
                total_indexed += len(batch)
                
        except Exception as e:
            conn.execute("ROLLBACK")
            console.print(f"[red]❌ Erro durante a indexação: {e}[/red]")
        finally:
            conn.close()
            
        console.print(f"[green]✔ [HADES] Ingestão concluída! {total_indexed} registros adicionados. ({skipped} linhas inválidas ignoradas).[/green]")
