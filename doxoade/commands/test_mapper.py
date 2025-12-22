# doxoade/commands/test_mapper.py
import os
import ast
import click
import json
from pathlib import Path
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _get_project_config

class TestMapper:
    """
    Motor de correlação entre Código Fonte e Testes.
    Agora com análise de qualidade/status do teste.
    """
    def __init__(self, root_path):
        self.root = Path(root_path).resolve()
        self.map = {
            'covered': {},   # {source_file: [test_files]}
            'orphans': [],   # [source_files_without_tests]
            'loose_tests': [] 
        }
        self.config = _get_project_config(None, start_path=str(self.root))
        self.ignore_patterns = self._load_ignore_patterns()

    def _load_ignore_patterns(self):
        toml_ignores = {p.strip('/\\') for p in self.config.get('ignore', [])}
        system_ignores = {'venv', '.git', '__pycache__', 'site-packages', 'build', 'dist', '.doxoade_cache', 'htmlcov', '.pytest_cache'}
        return toml_ignores.union(system_ignores)

    def _is_ignored_source(self, path):
        try:
            rel_path = path.relative_to(self.root)
        except ValueError:
            return True
        
        parts = rel_path.parts
        for part in parts:
            if part in self.ignore_patterns:
                return True
                
        # Relativo composto
        rel_str = str(rel_path).replace('\\', '/')
        for pattern in self.ignore_patterns:
            pattern_clean = pattern.replace('\\', '/')
            if rel_str.startswith(pattern_clean):
                return True
        
        if len(parts) == 1 and parts[0] in ['setup.py', 'install.py', 'run_doxoade.py', 'conftest.py']:
            return True
        if path.name == "__init__.py":
            return True
        return False

    def assess_test_status(self, test_path):
        """Analisa se o teste é um esqueleto, WIP ou real."""
        try:
            with open(test_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 1. Detecta Esqueleto Puro (Marcadores do Gerador)
            if "# Teste gerado automaticamente pelo Doxoade" in content:
                # Se ainda tem a marca mas o usuário já implementou algo, pode ser WIP
                # Mas geralmente é esqueleto
                return "SKELETON", Fore.MAGENTA + "💀"
            
            # 2. Detecta TODOs (WIP)
            if "TODO:" in content or "# [TODO]" in content:
                return "WIP", Fore.YELLOW + "🚧"
                
            # 3. Análise AST simples para ver se tem asserts reais
            # (Opcional para futuro, por enquanto baseamos em marcadores)
            
            return "REAL", Fore.CYAN + "✅"
            
        except Exception:
            return "UNKNOWN", Fore.WHITE + "?"

    def scan(self):
        # ... (Lógica de scan idêntica à anterior, mantendo a robustez) ...
        # Copiando a lógica robusta que fizemos no passo anterior:
        
        full_ignore_list = self.ignore_patterns.copy()
        full_ignore_list.discard('tests')
        full_ignore_list.discard('tests/')
        full_ignore_list.discard('commands_test')

        all_py = list(self.root.rglob("*.py"))
        sources = []
        tests = []
        
        for p in all_py:
            if self._is_ignored_source(p) and "tests" not in p.parts: # Simplificação
                continue
                
            # Filtro robusto para não pegar lixo dentro de tests/
            is_valid_test = True
            for part in p.relative_to(self.root).parts:
                if part in self.ignore_patterns and part != 'tests':
                    is_valid_test = False
                    break
            if not is_valid_test: continue

            is_test_file = p.name.startswith("test_") or p.name.endswith("_test.py") or "tests" in p.parts
            
            if is_test_file:
                tests.append(p)
            else:
                sources.append(p)

        test_metadata = {}
        for t in tests:
            targets = self._find_targets_in_test(t)
            test_metadata[t] = targets

        for s in sources:
            try: rel_s = s.relative_to(self.root)
            except ValueError: continue
            rel_s_str = str(rel_s).replace('\\', '/')
            self.map['covered'][rel_s_str] = []
            found = False
            
            expected_test_prefix = f"test_{s.stem}"
            expected_test_suffix = f"{s.stem}_test.py"
            
            for t in tests:
                t_rel = str(t.relative_to(self.root)).replace('\\', '/')
                if t.name == f"{expected_test_prefix}.py" or t.name == expected_test_suffix:
                    self.map['covered'][rel_s_str].append(t_rel)
                    found = True
                    continue
                t_targets = test_metadata.get(t, [])
                if s.name in t_targets or rel_s_str in t_targets:
                    self.map['covered'][rel_s_str].append(t_rel)
                    found = True

            if not found:
                self.map['orphans'].append(rel_s_str)

        return self.map

    def _find_targets_in_test(self, test_path):
        targets = []
        try:
            with open(test_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            import re
            matches = re.findall(r'#\s*TEST-TARGET:\s*(.+)', content)
            for m in matches:
                targets.append(m.strip().replace('\\', '/'))
        except Exception: pass
        return targets

    def generate_skeleton(self, source_path):
        # ... (Código de geração mantido igual) ...
        try:
            full_path = self.root / source_path
            with open(full_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            module_import = str(source_path).replace('.py', '').replace(os.sep, '.').replace('/', '.')
            
            lines = [
                f"# TEST-TARGET: {str(source_path).replace(os.sep, '/')}",
                "import pytest",
                f"from {module_import} import *",
                "",
                "# Teste gerado automaticamente pelo Doxoade", # Marcador de Esqueleto
            ]
            
            if not classes and not funcs:
                lines.append("def test_smoke():")
                lines.append("    # Teste de fumaça (importação)")
                lines.append("    assert True")

            for cls in classes:
                lines.append(f"def test_{cls}_initialization():")
                lines.append(f"    # TODO: Instanciar {cls} e verificar estado inicial")
                lines.append("    pass")
                lines.append("")

            for func in funcs:
                lines.append(f"def test_{func}_behavior():")
                lines.append(f"    # TODO: Implementar teste lógico para {func}") 
                lines.append("    pass")
                lines.append("")
                
            return "\n".join(lines)
        except Exception:
            return f"# Falha ao gerar esqueleto para {source_path}."

@click.command('test-map')
@click.option('--generate', '-g', is_flag=True, help="Gera arquivos de teste para os órfãos.")
@click.pass_context
def test_map(ctx, generate):
    """Mapeia a cobertura de testes e classifica o status (Esqueleto/Real)."""
    with ExecutionLogger('test-map', '.', ctx.params) as logger:
        mapper = TestMapper('.')
        matrix = mapper.scan()
        
        click.echo(Fore.CYAN + "--- Matriz de Testes (Arquitetura & Status) ---")
        
        # Estatísticas de Status
        stats = {'SKELETON': 0, 'WIP': 0, 'REAL': 0}

        sorted_covered = sorted(matrix['covered'].items())
        covered_only = [(src, t) for src, t in sorted_covered if t]
        
        for src, tests in covered_only:
            click.echo(f"{Fore.GREEN}✔ {src}")
            for t in tests:
                # Análise de Status
                status, icon = mapper.assess_test_status(t)
                stats[status] = stats.get(status, 0) + 1
                
                click.echo(f"  └── {icon} {t} ({status})")
        
        # Órfãos
        if matrix['orphans']:
            click.echo(Fore.YELLOW + f"\n--- Arquivos Órfãos (Sem Teste: {len(matrix['orphans'])}) ---")
            for src in matrix['orphans'][:20]:
                click.echo(f"{Fore.RED}✘ {src}")
            if len(matrix['orphans']) > 20:
                click.echo(f"{Fore.RED}... e mais {len(matrix['orphans']) - 20}")
                
            if generate:
                click.echo(Fore.WHITE + "\nGerando testes...")
                for src in matrix['orphans']:
                    src_path = Path(src)
                    test_dir = Path("tests") / src_path.parent
                    if not test_dir.exists(): os.makedirs(test_dir)
                    
                    test_filename = f"test_{src_path.name}"
                    test_path = test_dir / test_filename
                    
                    if not test_path.exists():
                        content = mapper.generate_skeleton(src)
                        with open(test_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        click.echo(Fore.GREEN + f"   > [GEN] Gerado: {test_path}")
                        logger.add_finding("INFO", f"Teste gerado para {src}")

        total_src = len(matrix['covered'])
        real_covered = len(covered_only)
        coverage_pct = (real_covered / total_src * 100) if total_src > 0 else 0
        
        click.echo(Fore.CYAN + "\nResumo da Qualidade:")
        click.echo(f"  Arquivos Fonte: {total_src}")
        click.echo(f"  Cobertos:       {real_covered} ({coverage_pct:.1f}%)")
        click.echo(Fore.WHITE + "  Status dos Testes:")
        click.echo(f"    💀 Esqueletos:   {stats['SKELETON']}")
        click.echo(f"    🚧 Em Progresso: {stats['WIP']}")
        click.echo(f"    ✅ Reais:        {stats['REAL']}")