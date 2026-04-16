# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/refactor_systems/refactor_engine.py
import os
import ast
import re
import shutil
import click
from pathlib import Path

from .refactor_verify         import verify_and_fix
from .refactor_utils          import iter_python_files, read_text_safe 
from doxoade.tools.filesystem import _find_project_root

class FunctionMover(ast.NodeTransformer):

    def __init__(self, func_name):
        self.func_name = func_name
        self.found = False

    def visit_FunctionDef(self, node):
        if node.name == self.func_name:
            self.found = True
            return None
        return node

class ImportCorrector(ast.NodeTransformer):
    """Corrige imports após movimentação de funções ou renomeação de arquivos."""

    def __init__(self, func_name, old_mod, new_mod):
        self.func_name = func_name
        self.old_mod = old_mod
        self.new_mod = new_mod
        self.changed = False

    def visit_ImportFrom(self, node):
        if node.module == self.old_mod:
            for alias in node.names:
                if alias.name == self.func_name:
                    if len(node.names) == 1:
                        node.module = self.new_mod
                    else:
                        node.module = self.new_mod
                    self.changed = True
        return node

class ImportUnfolder(ast.NodeTransformer):
    """Garante imports absolutos e desdobra a Facade shared_tools."""

    def __init__(self, facade_map):
        self.facade_map = facade_map
        self.changed = False

    def visit_Import(self, node):
        """Trata 'import tools.x' -> 'import doxoade.tools.x'"""
        for alias in node.names:
            if alias.name.startswith('tools.'):
                alias.name = 'doxoade.' + alias.name
                self.changed = True
        return node

    def visit_ImportFrom(self, node):
        """Trata 'from tools.x' e desdobra 'from doxoade.shared_tools'."""
        if not node.module:
            return node
        if node.module.startswith('tools.') or node.module == 'tools':
            node.module = 'doxoade.' + node.module
            self.changed = True
        is_facade = node.module == 'doxoade.shared_tools' or node.module == 'shared_tools' or node.module.endswith('.shared_tools')
        if is_facade:
            new_nodes = []
            for alias in node.names:
                real_module = self.facade_map.get(alias.name)
                if real_module:
                    new_nodes.append(ast.ImportFrom(module=real_module, names=[ast.alias(name=alias.name, asname=alias.asname)], level=0))
                    self.changed = True
                else:
                    new_nodes.append(node)
            return new_nodes
        return node

class AbsoluteImportFixer(ast.NodeTransformer):
    """
    Transformador AST agressivo que:
    1. Troca 'from tools...' por 'from doxoade.tools...'
    2. Troca 'import commands...' por 'import doxoade.commands...'
    3. Resolve 'shared_tools' para 'doxoade.shared_tools'
    """
    INTERNAL_ROOTS = {'tools', 'commands', 'diagnostic', 'shared_tools', 'database', 'tools_v2', 'dnm'}

    def __init__(self):
        self.changed = False

    def _fix_name(self, name):
        if not name:
            return name
        parts = name.split('.')
        if parts[0] in self.INTERNAL_ROOTS:
            self.changed = True
            return f'doxoade.{name}'
        return name

    def visit_Import(self, node):
        for alias in node.names:
            new_name = self._fix_name(alias.name)
            if new_name != alias.name:
                alias.name = new_name
        return node

    def visit_ImportFrom(self, node):
        if not node.module:
            return node
        new_module = self._fix_name(node.module)
        if new_module != node.module:
            node.module = new_module
            self.changed = True
            node.level = 0
        return node

class RefactorEngine:
    INTERNAL_ROOTS = {'tools', 'commands', 'diagnostic', 'shared_tools', 'database', 'tools_v2', 'dnm'}

    def __init__(self, base_path="."):
        self.root = Path(_find_project_root(base_path))

    def _fix_import_line(self, line):
        changed = False
        new_line = line
        # Preserva o comentário para não refatorar dentro dele
        parts = line.split('#', 1)
        code = parts[0]
        comment = f"#{parts[1]}" if len(parts) > 1 else ""

        for root in self.INTERNAL_ROOTS:
            # Regex que garante que o root é o início do módulo e não parte de outro nome
            regex_from = rf"(\bfrom\s+)({root}\b)"
            if re.search(regex_from, code):
                code = re.sub(regex_from, r"\1doxoade.\2", code)
                changed = True
            regex_import = rf"(\bimport\s+)({root}\b)"
            if re.search(regex_import, code):
                code = re.sub(regex_import, r"\1doxoade.\2", code)
                changed = True
        
        if changed:
            new_line = code + comment
        return new_line, changed

    def fix_facade_imports(self, target_path):
        """Padroniza imports absolutos do projeto."""
        target = Path(target_path)
        files = [target] if target.is_file() else target.rglob("*.py")
        SKIP = {'venv', 'thirdparty', 'build', 'dist', '__pycache__', '.git', '.doxoade'}
        for fpath in files:
            if any(part in SKIP for part in fpath.parts): continue
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                any_change = False
                new_lines = []
                for line in lines:
                    fixed, was_fixed = self._fix_import_line(line)
                    if was_fixed:
                        any_change, line = True, fixed
                    new_lines.append(line)
                if any_change:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    list(self.ensure_nexus_headers(fpath, force=True))
                    yield str(fpath), "Fixed"
            except: continue

    def _build_facade_map(self):
        if self._facade_cache:
            return self._facade_cache
        facade_path = self.root / 'doxoade' / 'shared_tools.py'
        if not facade_path.exists():
            return {}
        mapping = {}
        try:
            with open(facade_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    mod_path = node.module
                    if mod_path.startswith('.'):
                        clean_mod = mod_path.lstrip('.')
                        mod_path = f'doxoade.{clean_mod}' if 'tools' in clean_mod else f'doxoade.tools.{clean_mod}'
                    elif not mod_path.startswith('doxoade.'):
                        mod_path = f'doxoade.{mod_path}'
                    for alias in node.names:
                        mapping[alias.name] = mod_path
        except:
            return {}
        self._facade_cache = mapping
        return mapping

    def _path_to_module(self, file_path):
        try:
            abs_root = self.root.resolve()
            abs_file = Path(file_path).resolve()
            rel = abs_file.relative_to(abs_root)
            parts = list(rel.with_suffix('').parts)
            if parts and parts[0] == "doxoade":
                return '.'.join(parts)
            return "doxoade." + '.'.join(parts)
        except Exception:
            return Path(file_path).stem

    def repair_references(self, target_file, dry_run=False, verbose=False):
        target_path = Path(target_file).resolve()
        
        # --- FASE 0: PURIFICAÇÃO REVERSA (O PINGO NO I) ---
        if not dry_run:
            click.secho(f"[*] Purificando imports internos de {target_path.name}...", fg="cyan")
            if self._purify_file_internals(target_path):
                click.secho(f"  [OK] Imports convertidos para Absoluto.", fg="green")

        # --- FASE 1: MAPEAMENTOS CLI (Continua igual...) ---
        new_mod = self._path_to_module(target_path)
        
        content = read_text_safe(target_path)
        tree = ast.parse(content)
        definitions = [node.name for node in tree.body 
                       if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
        
        if not definitions: return False, "Nada para reparar."

        all_files = list(iter_python_files(self.root))
        modified_count = 0

        # MUDANÇA: Um único loop para Regex e AST
        with click.progressbar(all_files, label="Reparo em Lote (Nexus Turbo)") as bar:
            for fpath in bar:
                if fpath.resolve() == target_path: continue
                
                content = read_text_safe(fpath)
                if not any(name in content for name in definitions): continue

                changed = False
                # 1. Correção de Strings (CLI) via Regex
                for name in definitions:
                    pattern = rf"(['\"])([\w\.]+):({name})(['\"])"
                    if re.search(pattern, content):
                        content = re.sub(pattern, rf"\1{new_mod}:\3\4", content)
                        changed = True

                # 2. Correção de Imports via AST (Apenas se não for dry-run)
                if not dry_run:
                    # Aqui chamamos o fix_imports uma única vez por arquivo
                    # para todas as definições necessárias
                    from .refactor_verify import fix_imports
                    for name in definitions:
                        # O fix_imports agora é rápido porque o arquivo já está em memória (opcionalmente)
                        # mas aqui vamos apenas garantir que ele rode
                        fix_imports(fpath, name, new_mod)
                
                if changed and not dry_run:
                    fpath.write_text(content, encoding='utf-8')
                    modified_count += 1

        return True, f"Reparo concluído. {modified_count} arquivos sincronizados."

    def move_function(self, src_file, dest_file, targets=None, overwrite=False, dry_run=False, include_strings=False):
        src_path = Path(src_file)
        dest_path = Path(dest_file)
        
        if not src_path.exists():
            return False, f"Arquivo de origem não encontrado: {src_file}"

        old_mod = self._path_to_module(src_file)
        new_mod = self._path_to_module(dest_file)
        
        if dry_run:
            click.secho(f"[DRY] Mover: {src_path} -> {dest_path}", fg="yellow")

        # --- MODO INTEGRAL (Arquivo Inteiro) ---
        if not targets:
            with open(src_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                src_path.unlink()
                
                # PURIFICAÇÃO: Usa o old_mod como referência para converter os '.'
                self._ensure_absolute_imports_in_file(dest_path, old_mod)
            
            # --- O PINGO NO I: REPARO AUTOMÁTICO ---
            click.secho(f"[*] Iniciando Sincronização Global: {old_mod} -> {new_mod}", fg="cyan")
            
            # 1. Propaga a mudança do nome do módulo em todo o projeto
            self.update_project_imports(None, old_mod, new_mod, module_level=True, dry_run=dry_run, include_strings=include_strings)
            
            # 2. Se não for simulação, executa o Repair profundo baseado nas funções do arquivo
            if not dry_run:
                success, _ = self.repair_references(dest_path, verbose=False)
                # Garante Headers Nexus no destino
                list(self.ensure_nexus_headers(dest_path, force=True))
                return True, f"Arquivo {src_path.name} movido e projeto sincronizado."
            
            return True, "Simulação de movimentação e reparo concluída."

        # --- MODO 2: MIGRAÇÃO CIRÚRGICA (Via AST) ---
        with open(src_path, 'r', encoding='utf-8') as f:
            src_tree = ast.parse(f.read())

        nodes_to_move = []
        new_src_body = []
        
        for node in src_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and node.name in targets:
                nodes_to_move.append(node)
            else:
                new_src_body.append(node)

        if not nodes_to_move:
            return False, "Nenhum dos itens especificados foi encontrado."

        if not dry_run:
            # Atualização do Destino (AST)
            if dest_path.exists() and not overwrite:
                with open(dest_path, 'r', encoding='utf-8') as f:
                    dest_tree = ast.parse(f.read())
            else:
                dest_tree = ast.Module(body=[], type_ignores=[])
            
            dest_tree.body.extend(nodes_to_move)

            # Regrava arquivos
            src_path.write_text(ast.unparse(ast.Module(body=new_src_body, type_ignores=[])), encoding='utf-8')
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(ast.unparse(dest_tree), encoding='utf-8')

        # Atualização Global das referências das funções
        for name in targets:
            self.update_project_imports(name, old_mod, new_mod, dry_run=dry_run, include_strings=include_strings)
        
        if not dry_run:
            success, msg = self.repair_references(dest_file)
            return True, f"Movimentação física OK. {msg}"
        
        return True, "Simulação de movimentação cirúrgica concluída."

    def update_project_imports(self, func_name, old_mod, new_mod, module_level=False, dry_run=False, include_strings=False):
        all_files = list(iter_python_files(self.root))
        
        # Mapeamento de variações
        old_parts = old_mod.split('.')
        new_parts = new_mod.split('.')
        mapping = {
            old_mod: new_mod,
            '.'.join(old_parts[1:]): '.'.join(new_parts[max(0, len(new_parts)-(len(old_parts)-1)):]),
        }

        with click.progressbar(all_files, label="Limpando rastros") as bar:
            for fpath in bar:
                content = read_text_safe(fpath)
                if not content: continue
                lines = content.splitlines(keepends=True)
                changed, new_lines, file_diff = False, [], []

                for i, line in enumerate(lines):
                    stripped = line.strip()
                    
                    # NOVO FILTRO: É import ou é uma string de mapeamento CLI?
                    is_import = stripped.startswith(('from ', 'import '))
                    is_cli_map = (':' in stripped and (old_mod in stripped))
                    
                    if not (include_strings or is_import or is_cli_map):
                        new_lines.append(line)
                        continue

                    new_line = line
                    for o_var, n_var in mapping.items():
                        # Se for CLI Map (doxoade.commands.migrate_colors:migrate_colors)
                        if o_var in new_line:
                            new_line = new_line.replace(o_var, n_var)
                            changed = True

                    if new_line != line:
                        file_diff.append((i + 1, line.strip(), new_line.strip()))
                        changed = True
                    new_lines.append(new_line)

                if changed:
                    if dry_run:
                        rel_path = fpath.relative_to(self.root)
                        click.secho(f"\n[CLEANUP] {rel_path}", fg="bright_cyan", bold=True)
                        for ln, old, new in file_diff:
                            click.echo(f"  L{ln}: - {old} -> + {new}")
                    else:
                        with open(fpath, 'w', encoding='utf-8', newline='') as f:
                            f.writelines(new_lines)

    def rename_file(self, old_path, new_path):
        """[PREP] Renomeia arquivo e atualiza todos os imports do projeto."""
        old_p = Path(old_path)
        new_p = Path(new_path)
        old_mod = self._path_to_module(old_path)
        new_mod = self._path_to_module(new_path)
        os.rename(old_p, new_p)
        return True

    def ensure_nexus_headers(self, target_path, force=False):
        """Garante o cabeçalho # doxoade/..."""
        target = Path(target_path)
        files = [target] if target.is_file() else target.rglob("*.py")
        SKIP = {'venv', 'thirdparty', 'build', 'dist', '__pycache__', '.git', '.doxoade'}

        for fpath in files:
            if any(part in SKIP for part in fpath.parts): continue
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                try:
                    rel_path = fpath.absolute().relative_to(self.root.parent).as_posix()
                except: rel_path = fpath.name
                header = f"# {rel_path}\n"
                changed = False
                if not lines:
                    lines, changed = [header], True
                else:
                    idx = 0
                    if lines[0].startswith("#!"): idx = 1
                    if len(lines) > idx and lines[idx].startswith("# ") and "/" in lines[idx]:
                        if force or lines[idx] != header:
                            lines[idx] = header
                            changed = True
                    else:
                        lines.insert(idx, header)
                        changed = True
                if changed:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                    yield str(fpath), "OK"
            except: continue

    def _ensure_absolute_imports_in_file(self, file_path: Path):
        """Força que todos os imports internos do arquivo sejam absolutos."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines = []
            changed = False
            for line in lines:
                fixed, was_fixed = self._fix_import_line(line)
                if was_fixed:
                    new_lines.append(fixed)
                    changed = True
                else:
                    new_lines.append(line)
            
            if changed:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
        except: pass
        
    def _convert_relative_to_absolute(self, line, current_module_path):
        """
        Converte 'from .utils' em 'from doxoade.tools.utils'
        baseado no local original do arquivo (current_module_path).
        """
        # Regex para capturar: from ..sub.modulo import ...
        match = re.search(r'from (\.+)([\w\.]+)', line)
        if not match:
            # Caso especial: from . import xxx
            match = re.search(r'from (\.+)\s+import', line)
            if not match: return line, False
            dots = match.group(1)
            suffix = ""
        else:
            dots = match.group(1)
            suffix = match.group(2)

        level = len(dots) # . = 1, .. = 2
        parts = current_module_path.split('.') # ['doxoade', 'tools', 'logger']
        
        # O ponto '.' refere-se ao pacote atual (remove o nome do arquivo)
        # Se level é 1, removemos 1 parte (logger). Se 2, removemos 2 (logger, tools)
        base_parts = parts[:-level]
        
        if not base_parts:
            return line, False
            
        new_module = '.'.join(base_parts + ([suffix] if suffix else []))
        
        # Reconstrói a linha substituindo o trecho relativo pelo absoluto
        if suffix:
            new_line = line.replace(f"from {dots}{suffix}", f"from {new_module}")
        else:
            new_line = re.sub(rf"from \.{dots}\s+", f"from {new_module} ", line)
            
        return new_line, True
        
    def _ensure_absolute_imports_in_file(self, file_path: Path, source_module_path: str):
        """Purifica o arquivo: transforma relativos em absolutos e fixa roots."""
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines(keepends=True)
            new_lines = []
            changed = False

            for line in lines:
                new_line = line
                
                # 1. Primeiro resolve os pontos (relativos)
                if 'from .' in new_line:
                    fixed_rel, was_rel = self._convert_relative_to_absolute(new_line, source_module_path)
                    if was_rel:
                        new_line = fixed_rel
                        changed = True

                # 2. Depois garante o prefixo doxoade (Nexus Fix)
                fixed_abs, was_abs = self._fix_import_line(new_line)
                if was_abs:
                    new_line = fixed_abs
                    changed = True

                new_lines.append(new_line)

            if changed:
                file_path.write_text("".join(new_lines), encoding='utf-8')
        except Exception as e:
            click.echo(f"  [AVISO] Falha ao purificar {file_path.name}: {e}")
            
    def _module_exists(self, module_name: str) -> bool:
        """Verifica se um nome de módulo existe como arquivo .py no projeto."""
        if not module_name.startswith("doxoade."): return False
        parts = module_name.split('.')
        # Converte doxoade.tools.db_utils -> doxoade/tools/db_utils.py
        path = self.root / Path(*parts[1:]).with_suffix('.py')
        return path.exists()

    def _find_actual_module(self, leaf_name: str) -> str:
        """Busca o nome absoluto de um módulo pelo seu nome curto (ex: db_utils)."""
        for py_file in iter_python_files(self.root):
            if py_file.stem == leaf_name:
                return self._path_to_module(py_file)
        return None

    def _purify_file_internals(self, target_path: Path):
        """
        Analisa o arquivo e corrige imports relativos ou absolutos quebrados.
        """
        try:
            content = target_path.read_text(encoding='utf-8')
            lines = content.splitlines(keepends=True)
            new_lines = []
            changed = False

            for line in lines:
                new_line = line
                
                # 1. CORREÇÃO DE ABSOLUTOS QUEBRADOS (Ex: doxoade.tools.telemetry_tools.db_utils)
                match_abs = re.search(r'from (doxoade\.[\w\.]+)', line)
                if match_abs:
                    full_mod = match_abs.group(1)
                    if not self._module_exists(full_mod):
                        # O import está quebrado. Vamos achar o dono original.
                        leaf = full_mod.split('.')[-1]
                        actual_mod = self._find_actual_module(leaf)
                        if actual_mod:
                            new_line = line.replace(full_mod, actual_mod)
                            changed = True

                # 2. CORREÇÃO DE RELATIVOS (Ex: from .db_utils)
                match_rel = re.search(r'from (\.+)([\w\.]+)', line)
                if match_rel and not changed: # Só tenta se o passo 1 não resolveu
                    dots, suffix = match_rel.group(1), match_rel.group(2)
                    actual_mod = self._find_actual_module(suffix.split('.')[0])
                    if actual_mod:
                        new_line = line.replace(f"from {dots}{suffix}", f"from {actual_mod}")
                        changed = True

                new_lines.append(new_line)

            if changed:
                target_path.write_text("".join(new_lines), encoding='utf-8')
                return True
        except Exception as e:
            click.echo(f"  [ERRO] Falha ao purificar {target_path.name}: {e}")
        return False

    def _resolve_relative_to_absolute(self, target_path: Path, dots: str, suffix: str):
        """
        Tenta localizar fisicamente um módulo referenciado por '.' ou '..'
        e retorna o nome absoluto do módulo Nexus.
        """
        # 1. Determina a pasta de partida baseada nos pontos
        # . = mesma pasta, .. = pasta pai
        level = len(dots)
        base_dir = target_path.parent
        for _ in range(level - 1):
            base_dir = base_dir.parent

        # 2. Tenta achar o arquivo fisicamente (suffix.py ou suffix/__init__.py)
        potential_path = base_dir / (suffix.replace('.', '/') + '.py')
        if not potential_path.exists():
            # Tenta um nível acima (caso o arquivo tenha sido movido para uma subpasta)
            potential_path = base_dir.parent / (suffix.replace('.', '/') + '.py')
            
        if potential_path.exists():
            return self._path_to_module(potential_path)
        
        # 3. Se não achou vizinho, busca no projeto todo (Heurística de emergência)
        for py_file in self.root.rglob(f"{suffix}.py"):
            return self._path_to_module(py_file)
            
        return None