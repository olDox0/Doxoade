# -*- coding: utf-8 -*-
# doxoade/commands/refactor_systems/refactor_cache.py
from __future__ import annotations
import ast
import json
import os
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, Set, List, Tuple
from .refactor_utils import iter_python_files, read_text_safe

def compute_canonical_hash(text: str) -> str:
    """Hash SHA-256 normalizado para ignorar ruído de CRLF/LF e trailing whitespaces."""
    lines = [l.rstrip() for l in text.replace('\r\n', '\n').split('\n')]
    while lines and lines[-1] == '':
        lines.pop()
    return hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest()

def _resolve_import_from(base_module: str, node: ast.ImportFrom) -> str:
    """Resolve imports relativos para o nome canônico absoluto."""
    level = node.level or 0
    if level == 0:
        return node.module or ""
    parts = base_module.split('.')[:-1]
    up = level - 1
    if up > len(parts):
        return node.module or ""
    base_parts = parts if up == 0 else parts[:-up]
    return '.'.join(base_parts + ([node.module] if node.module else []))

def extract_imported_modules(tree: ast.AST, current_module: str) -> Set[str]:
    """Extrai todos os módulos e submódulos importados pelo arquivo."""
    modules: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import_from(current_module, node)
            if resolved:
                modules.add(resolved)
                for alias in node.names:
                    # Inclui também o símbolo importado (ex: modulo.funcao)
                    modules.add(f"{resolved}.{alias.name}")
    return modules

class RefactorDependencyCache:
    """Cache persistente e incremental do Grafo Invertido de Dependências."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.cache_dir = self.root / ".doxoade" / "cache"
        self.cache_file = self.cache_dir / "refactor_graph.json"
        
        # Estrutura em memória
        # { file_rel_path: {"mtime_ns": int, "size": int, "hash": str, "imports": [str]} }
        self.file_records: Dict[str, dict] = {}
        # { imported_module: [file_rel_path, ...] }
        self.inverted_index: Dict[str, Set[str]] = {}
        
        self.load()

    def load(self) -> None:
        """Carrega o cache do disco se existir."""
        if not self.cache_file.exists():
            return
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.file_records = data.get("files", {})
                raw_index = data.get("inverted_index", {})
                self.inverted_index = {k: set(v) for k, v in raw_index.items()}
        except Exception:
            # Em caso de corrupção, descarta e reconstroi limpo
            self.file_records = {}
            self.inverted_index = {}

    def save(self) -> None:
        """Gravação atômica do cache no disco."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        serializable_index = {k: list(v) for k, v in self.inverted_index.items()}
        payload = {
            "version": 1,
            "files": self.file_records,
            "inverted_index": serializable_index
        }
        
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=str(self.cache_dir), delete=False, encoding='utf-8') as f:
                json.dump(payload, f, indent=1)
                tmp_file = Path(f.name)
            os.replace(tmp_file, self.cache_file)
        except Exception:
            if tmp_file and tmp_file.exists():
                tmp_file.unlink()

    def sync(self) -> Tuple[int, int]:
        """
        Sincronização incremental em ~10ms.
        Verifica os.stat() de todos os arquivos. Parseia AST somente se o hash mudar.
        """
        current_disk_files: Set[str] = set()
        updated_count = 0
        removed_count = 0

        for py_path in iter_python_files(self.root):
            try:
                rel_path = py_path.resolve().relative_to(self.root).as_posix()
                current_disk_files.add(rel_path)
                st = py_path.stat()
                mtime_ns = st.st_mtime_ns
                size = st.st_size

                # 1. Checagem rápida de stat (microsegundos)
                rec = self.file_records.get(rel_path)
                if rec and rec.get("mtime_ns") == mtime_ns and rec.get("size") == size:
                    continue  # Nada mudou, mantém registro

                # 2. Checagem canônica de conteúdo
                content = read_text_safe(py_path)
                content_hash = compute_canonical_hash(content)

                if rec and rec.get("hash") == content_hash:
                    # Conteúdo semântico é igual (apenas touch/timestamp)
                    rec["mtime_ns"] = mtime_ns
                    rec["size"] = size
                    continue

                # 3. Mudança real detectada: extrai imports via AST
                module_name = '.'.join(Path(rel_path).with_suffix('').parts)
                try:
                    tree = ast.parse(content, filename=str(py_path))
                    imports = extract_imported_modules(tree, module_name)
                except Exception:
                    imports = set()

                # Remove dependências antigas do índice invertido
                if rec:
                    for old_imp in rec.get("imports", []):
                        if old_imp in self.inverted_index:
                            self.inverted_index[old_imp].discard(rel_path)

                # Insere novas dependências
                for imp in imports:
                    self.inverted_index.setdefault(imp, set()).add(rel_path)

                self.file_records[rel_path] = {
                    "mtime_ns": mtime_ns,
                    "size": size,
                    "hash": content_hash,
                    "imports": list(imports)
                }
                updated_count += 1

            except Exception:
                continue

        # 4. Remove arquivos deletados do disco
        deleted = set(self.file_records.keys()) - current_disk_files
        for del_path in deleted:
            rec = self.file_records.pop(del_path, None)
            if rec:
                for old_imp in rec.get("imports", []):
                    if old_imp in self.inverted_index:
                        self.inverted_index[old_imp].discard(del_path)
            removed_count += 1

        if updated_count > 0 or removed_count > 0:
            self.save()

        return updated_count, removed_count

    def find_affected_files(self, old_modules: Set[str]) -> Set[Path]:
        """
        Consulta em O(1) no índice invertido:
        Retorna EXATAMENTE os arquivos que importam algum dos módulos em questão.
        """
        affected_rel_paths: Set[str] = set()

        for old_mod in old_modules:
            # Caso 1: Match exato do módulo
            if old_mod in self.inverted_index:
                affected_rel_paths.update(self.inverted_index[old_mod])

            # Caso 2: Match de prefixo ou submódulos
            for indexed_mod, files in self.inverted_index.items():
                if indexed_mod.startswith(old_mod + ".") or indexed_mod == old_mod:
                    affected_rel_paths.update(files)

        return {self.root / Path(p) for p in affected_rel_paths}
