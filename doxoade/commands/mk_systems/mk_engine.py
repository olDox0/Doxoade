# doxoade/doxoade/commands/mk_systems/mk_engine.py
import os
import shutil
from doxoade.tools.doxcolors import Fore, Style
from .mk_utils import (
    get_indent_level, is_directory, clean_path_and_content, 
    expand_braces, TREE_BRANCH, TREE_LAST, TREE_INDENT, get_tree_icon
)
from doxoade.tools.filesystem import is_ignored

class MkEngine:
    """Motor de Construção de Topologia (Nexus Edition)."""
    MOVE_BLACKLIST = ['__init__.py', '.gitignore', 'pyproject.toml', 'README.md', 'LICENSE']

    def __init__(self, base_path='.'):
        self.base_path = os.path.abspath(base_path)
        self.stack = [(-1, self.base_path)]
        self.consumed_sources = set()
        self.affected_files = []

    def _create_init_py(self, directory_path):
        """Cria um __init__.py vazio se não existir, subindo até a base."""
        # Não cria se estiver fora do base_path (segurança)
        if not directory_path.startswith(self.base_path):
            return

        current = directory_path
        # Sobe criando __init__.py até chegar na base do projeto
        while current and current != self.base_path and len(current) > len(self.base_path):
            init_file = os.path.join(current, '__init__.py')
            if not os.path.exists(init_file):
                # Se for um projeto C (como o seu), talvez não queira __init__.py
                # Mas como você solicitou a automação:
                with open(init_file, 'w', encoding='utf-8') as f:
                    f.write('')
            current = os.path.dirname(current)

    def _process_single_item(self, indent, raw_name):
        while len(self.stack) > 1 and self.stack[-1][0] >= indent:
            self.stack.pop()
        
        name, content = clean_path_and_content(raw_name)
        parent_path = self.stack[-1][1]
        if os.path.isfile(parent_path):
            self.stack.pop()
            parent_path = self.stack[-1][1]
        
        full_path = os.path.normpath(os.path.join(parent_path, name))

        if is_directory(name):
            os.makedirs(full_path, exist_ok=True)
            self._create_init_py(full_path) # Agora garante na pasta e acima
            self.stack.append((indent, full_path))
            return (full_path, 'Diretório')
        else:
            # Para arquivos:
            parent_dir = os.path.dirname(full_path)
            os.makedirs(parent_dir, exist_ok=True)
            self._create_init_py(parent_dir) # Garante __init__.py na pasta do arquivo
            
            # Caso o destino seja uma pasta onde deveria ser arquivo
            if os.path.exists(full_path) and os.path.isdir(full_path):
                return (full_path, 'ERRO: Pasta existe')

            # Se arquivo já existe, mantemos e adicionamos ao --up
            if os.path.exists(full_path) and os.path.isfile(full_path):
                if full_path not in self.affected_files:
                    self.affected_files.append(full_path)
                return (full_path, 'Mantido')

            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Lógica de Movimentação (apenas se não tiver conteúdo explícito)
            if not content:
                filename = os.path.basename(full_path)
                if filename not in self.MOVE_BLACKLIST:
                    existing = self._find_existing_file(filename)
                    if existing and existing != full_path and (existing not in self.consumed_sources):
                        try:
                            shutil.move(existing, full_path)
                            self.consumed_sources.add(existing)
                            self.affected_files.append(full_path)
                            return (full_path, 'Movido')
                        except: pass

            # Criação de novo arquivo
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if full_path not in self.affected_files:
                self.affected_files.append(full_path)
            return (full_path, 'Arquivo')

    def parse_architecture_file(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip() or line.strip().startswith('#'): continue
                indent = get_indent_level(line)
                for expanded in expand_braces(line.strip()):
                    yield self._process_single_item(indent, expanded)

    def _expand_and_create(self, indent, item):
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
