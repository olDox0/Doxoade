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
    Usa convenções de nome e análise semântica (comentários) para ligar os pontos.
    """
    def __init__(self, root_path):
        self.root = Path(root_path)
        self.map = {
            'covered': {},   # {source_file: [test_files]}
            'orphans': [],   # [source_files_without_tests]
            'loose_tests': [] # [tests_without_target]
        }

    def scan(self):
        """Constrói a matriz de testes."""
        # 1. Lista todos os arquivos .py (Source vs Tests)
        all_py = list(self.root.rglob("*.py"))
        
        sources = []
        tests = []
        
        # Heurística simples de separação
        for p in all_py:
            if "venv" in p.parts or ".git" in p.parts: continue
            
            # Se começa com test_ ou termina com _test.py, ou está na pasta tests/
            if p.name.startswith("test_") or p.name.endswith("_test.py") or "tests" in p.parts:
                tests.append(p)
            else:
                sources.append(p)

        # 2. Indexação de Testes (Metadata)
        test_metadata = {}
        for t in tests:
            targets = self._find_targets_in_test(t)
            test_metadata[t] = targets

        # 3. Cruzamento (Matching)
        for s in sources:
            rel_s = s.relative_to(self.root)
            self.map['covered'][str(rel_s)] = []
            
            found = False
            
            # Estratégia A: Naming Convention (test_nome.py -> nome.py)
            expected_test_name = f"test_{s.name}"
            
            # Estratégia B: Metadata (Comentários no teste)
            
            for t in tests:
                # Match por nome
                if t.name == expected_test_name:
                    self.map['covered'][str(rel_s)].append(str(t.relative_to(self.root)))
                    found = True
                    continue
                
                # Match por anotação
                t_targets = test_metadata.get(t, [])
                if s.name in t_targets or str(rel_s) in t_targets:
                    self.map['covered'][str(rel_s)].append(str(t.relative_to(self.root)))
                    found = True

            if not found:
                self.map['orphans'].append(str(rel_s))

        return self.map

    def _find_targets_in_test(self, test_path):
        """Lê o arquivo de teste procurando dicas de qual arquivo ele testa."""
        targets = []
        try:
            with open(test_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Procura: # TEST-TARGET: arquivo.py
            import re
            matches = re.findall(r'#\s*TEST-TARGET:\s*(.+)', content)
            for m in matches:
                targets.append(m.strip())
                
            # Procura imports: from doxoade.commands import check
            # (Isso é mais complexo, deixaremos para a V2 do mapper)
                
        except Exception: pass
        return targets

    def generate_skeleton(self, source_path):
        """Gera um conteúdo de teste básico para um arquivo órfão."""
        try:
            with open(self.root / source_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
            
            module_name = str(source_path).replace(os.sep, '.').replace('.py', '')
            
            lines = [
                f"# Teste gerado automaticamente pelo Doxoade para {source_path}",
                "import pytest",
                f"from {module_name} import *",
                "",
            ]
            
            for func in funcs:
                lines.append(f"def test_{func}_exists():")
                lines.append(f"    # TODO: Implementar teste para {func}")
                lines.append(f"    assert callable({func})")
                lines.append("")
                
            return "\n".join(lines)
        except:
            return "# Falha ao gerar esqueleto."

@click.command('test-map')
@click.option('--generate', '-g', is_flag=True, help="Gera arquivos de teste para os órfãos.")
@click.pass_context
def test_map(ctx, generate):
    """Mapeia a cobertura de testes e gera esqueletos faltantes."""
    with ExecutionLogger('test-map', '.', ctx.params) as logger:
        mapper = TestMapper('.')
        matrix = mapper.scan()
        
        click.echo(Fore.CYAN + "--- Matriz de Testes ---")
        
        # Cobertos
        for src, tests in matrix['covered'].items():
            if tests:
                click.echo(f"{Fore.GREEN}✔ {src}")
                for t in tests:
                    click.echo(f"  └── {t}")
        
        # Órfãos
        if matrix['orphans']:
            click.echo(Fore.YELLOW + f"\n--- Arquivos sem Teste ({len(matrix['orphans'])}) ---")
            for src in matrix['orphans']:
                click.echo(f"{Fore.RED}✘ {src}")
                
                if generate:
                    test_name = f"tests/test_{os.path.basename(src)}"
                    if not os.path.exists("tests"): os.makedirs("tests")
                    
                    if not os.path.exists(test_name):
                        content = mapper.generate_skeleton(src)
                        with open(test_name, 'w', encoding='utf-8') as f:
                            f.write(content)
                        click.echo(Fore.GREEN + f"   > Gerado: {test_name}")
                        logger.add_finding("INFO", f"Teste gerado para {src}")

        # Estatísticas
        coverage = len(matrix['covered']) - len(matrix['orphans'])
        total = len(matrix['covered']) # chaves do dict covered incluem todos os sources
        # Correção lógica: 'covered' tem todos.
        real_covered = len([k for k,v in matrix['covered'].items() if v])
        
        click.echo(Fore.CYAN + "\nResumo:")
        click.echo(f"Fontes: {len(matrix['covered'])}")
        click.echo(f"Cobertos: {real_covered}")
        click.echo(f"Órfãos: {len(matrix['orphans'])}")