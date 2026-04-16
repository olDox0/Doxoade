# doxoade/doxoade/commands/mk_systems/mk_engine.py
import os
import shutil
from doxoade.tools.doxcolors import Fore, Style
from .mk_utils import get_indent_level, is_directory, clean_path_and_content, expand_braces, TREE_BRANCH, TREE_LAST, TREE_INDENT, get_tree_icon
from doxoade.tools.filesystem import is_ignored

class MkEngine:
    """Motor de Construção de Topologia (Nexus Edition)."""
    MOVE_BLACKLIST = ['__init__.py', '.gitignore', 'pyproject.toml', 'README.md', 'LICENSE']

    def __init__(self, base_path='.'):
        self.base_path = os.path.abspath(base_path)
        self.stack = [(-1, self.base_path)]
        self.consumed_sources = set()

    def _process_single_item(self, indent, raw_name):
        """Gerencia a pilha de diretórios com proteção de escopo (OSL-1)."""
        while len(self.stack) > 1 and self.stack[-1][0] >= indent:
            self.stack.pop()
        name, content = clean_path_and_content(raw_name)
        parent_path = self.stack[-1][1]
        if os.path.isfile(parent_path):
            self.stack.pop()
            parent_path = self.stack[-1][1]
        full_path = os.path.normpath(os.path.join(parent_path, name))
        if is_directory(name):
            if os.path.exists(full_path) and (not os.path.isdir(full_path)):
                os.remove(full_path)
            os.makedirs(full_path, exist_ok=True)
            self.stack.append((indent, full_path))
            return (full_path, 'Diretório')
        else:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                return (full_path, 'Mantido')
            if not content:
                filename = os.path.basename(full_path)
                if filename not in self.MOVE_BLACKLIST:
                    existing = self._find_existing_file(filename)
                    if existing and existing != full_path and (existing not in self.consumed_sources):
                        if os.path.isdir(full_path):
                            shutil.rmtree(full_path)
                        try:
                            shutil.move(existing, full_path)
                            self.consumed_sources.add(existing)
                            return (full_path, 'Movido')
                        except Exception:
                            pass
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return (full_path, 'Arquivo')

    def parse_architecture_file(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip() or line.strip().startswith('#'):
                    continue
                indent = get_indent_level(line)
                for expanded in expand_braces(line.strip()):
                    yield self._process_single_item(indent, expanded)

    def _expand_and_create(self, indent, item):
        """[FIX] Método solicitado pela mk_commands para expansão de chaves."""
        for expanded in expand_braces(item):
            path, kind = self._process_single_item(indent, expanded)
            yield f'{kind:<10}: {path}'

    def render_tree(self, path: str, project_root: str, prefix: str=''):
        """Visualização recursiva blindada pelo DNM e TOML."""
        from doxoade.dnm import DNM
        if not os.path.exists(path):
            return
        dnm = DNM(project_root)
        try:
            raw_items = os.listdir(path)
            items = []
            for i in sorted(raw_items):
                full_item_path = os.path.join(path, i)
                if not dnm.is_ignored(full_item_path):
                    items.append(i)
        except PermissionError:
            return
        count = len(items)
        for i, item in enumerate(items):
            is_last = i == count - 1
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            connector = TREE_LAST if is_last else TREE_BRANCH
            icon = get_tree_icon(is_dir)
            color = Fore.CYAN if is_dir else Fore.WHITE
            yield f'{prefix}{connector}{icon}{color}{item}{Style.RESET_ALL}'
            if is_dir:
                new_prefix = prefix + ('    ' if is_last else TREE_INDENT)
                yield from self.render_tree(full_path, project_root, new_prefix)

    def _find_existing_file(self, filename: str) -> str | None:
        """Busca por arquivo. Retorna o caminho apenas se houver EXATAMENTE UMA ocorrência no projeto."""
        candidates = []
        for dirpath, _, filenames in os.walk(self.base_path):
            if filename in filenames:
                full_p = os.path.normpath(os.path.join(dirpath, filename))
                if full_p not in self.consumed_sources:
                    candidates.append(full_p)
        if len(candidates) == 1:
            return candidates[0]
        return None
