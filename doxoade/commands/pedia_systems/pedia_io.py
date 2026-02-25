# -*- coding: utf-8 -*-
# doxoade/commands/pedia_systems/pedia_io.py
"""
Pedia I/O - v96.3 (Refined Scanner).
Alteração: Filtro estrito de extensões (Ignora .py, binários, etc).
"""
import json
import re
import os
import doxoade
from pathlib import Path
from dataclasses import dataclass
# [DOX-UNUSED] from tools.doxcolors import Fore
@dataclass
class Article:
    key: str
    title: str
    content: str
    source: str
    category: str
    date: str = ""
class KnowledgeBaseIO:
    def __init__(self, project_root: str):
        self.user_root = Path(project_root)
        self.system_docs = Path(doxoade.__file__).parent / 'docs'
        self.user_docs = self._locate_user_docs()
    def _locate_user_docs(self) -> Path:
        candidates = [
            self.user_root / 'docs',
            self.user_root / 'documentation',
            self.user_root / 'src' / 'docs'
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c
        return self.user_root / 'docs'
    def load_all_knowledge(self) -> dict:
        articles = {}
        if self.system_docs.exists():
            articles.update(self._scan_tree(self.system_docs, source="DOXOADE CORE"))
        if self.user_docs.exists():
            articles.update(self._scan_tree(self.user_docs, source="local"))
        return articles
    def _scan_tree(self, root_path: Path, source: str) -> dict:
        loaded = {}
        ignore_dirs = {'.git', '__pycache__', '_build', 'site', 'node_modules', 'venv'}
        
        # EXTENSÕES PERMITIDAS (Whitelist)
        valid_exts = {'.json', '.md', '.txt', '.dox'}
        for current_dir, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                file_path = Path(current_dir) / file
                
                # [FIX] Ignora arquivos que não sejam de documentação
                if file_path.suffix.lower() not in valid_exts:
                    continue
                try:
                    rel_parent = file_path.parent.relative_to(root_path)
                    category = str(rel_parent).replace('\\', '/')
                    if category == '.': category = "Geral"
                except ValueError:
                    category = "Geral"
                
                if file.endswith('.json'):
                    loaded.update(self._parse_json(file_path, source, category))
                elif file.endswith(('.md', '.txt', '.dox')):
                    art = self._parse_markdown(file_path, source, category)
                    if art: loaded[art.key] = art
        return loaded
    def _parse_json(self, path: Path, source: str, category: str) -> dict:
        content = self._read_robust(path)
        batch = {}
        if not content: return batch
        
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                for key, val in data.items():
                    title = key
                    date = ""
                    body = ""
                    if isinstance(val, dict):
                        title = val.get('title', key)
                        date = val.get('date', '')
                        raw_content = val.get('content')
                        if raw_content is None:
                            clean_val = val.copy()
                            clean_val.pop('title', None); clean_val.pop('date', None)
                            target_data = clean_val
                        else:
                            target_data = raw_content
                        if isinstance(target_data, str):
                            body = target_data
                        elif isinstance(target_data, (dict, list)):
                            body = json.dumps(target_data, indent=2, ensure_ascii=False)
                        else:
                            body = str(target_data)
                    else:
                        body = str(val)
                    final_cat = category if category != "Geral" else path.stem.title()
                    clean_key = key.lower().strip()
                    batch[clean_key] = Article(clean_key, title, body, source, final_cat, date)
        except json.JSONDecodeError: pass
        return batch
    def _parse_markdown(self, path: Path, source: str, category: str) -> Article:
        content = self._read_robust(path)
        if not content: return None
        
        lines = content.splitlines()
        title = path.stem.replace('_', ' ').replace('-', ' ').title()
        
        for line in lines[:5]:
            if line.startswith('# '):
                title = line[2:].strip()
                break
        
        date_match = re.search(r'(?:Data|Date|Atualizado):\s*(\d{4}-\d{2}-\d{2})', content)
        date = date_match.group(1) if date_match else ''
        return Article(path.stem.lower(), title, content, source, category, date)
    def _read_robust(self, filepath: Path) -> str:
        for enc in ['utf-8', 'cp1252', 'latin-1']:
            try: return filepath.read_text(encoding=enc)
            except (UnicodeDecodeError, OSError): continue
        return ""