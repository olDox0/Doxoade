# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_utils/intelligence_utils.py
"""
Support_Utils para Intelligence (PASC 1.2 / MPoT 17).
Foco: Extração de Metadados de Documentação e Análise de Fluxo de IO.
"""
import os
import ast
import re
import sys
import json
from typing import List, Dict, Any
from html.parser import HTMLParser

# Padrões de IO para busca via AST
IO_KEYWORDS = {
    'open', 'read', 'write', 'load', 'dump', 'print', 'input', 'get', 'post','request'
}
IO_MODULES = {
    'os', 'sys', 'pathlib', 'shutil', 'subprocess', 'socket', 'requests', 'json', 'toml'
}

def compact_python_imports(code: str) -> str:
    """
    Concatena declarações consecutivas de 'import' com a mesma indentação em uma linha única.
    Exemplo:
        import os
        import sys
        import re
        --> import os, sys, re

    Também agrupa 'from X import A' e 'from X import B' consecutivos do mesmo módulo:
        from typing import List
        from typing import Dict
        --> from typing import List, Dict
    """
    lines = code.splitlines()
    if not lines:
        return code

    new_lines = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ── 1. AGRUPAMENTO DE 'import mod1', 'import mod2' ─────────────
        if (stripped.startswith("import ") and 
            not stripped.startswith("import (") and 
            "#" not in line and 
            ";" not in line):
            
            indent = line[:len(line) - len(stripped)]
            collected_imports = [stripped[len("import "):].strip()]

            j = i + 1
            while j < n:
                next_line = lines[j]
                next_stripped = next_line.strip()
                next_indent = next_line[:len(next_line) - len(next_stripped)]

                if (next_indent == indent and
                    next_stripped.startswith("import ") and
                    not next_stripped.startswith("import (") and
                    "#" not in next_line and
                    ";" not in next_line):
                    
                    collected_imports.append(next_stripped[len("import "):].strip())
                    j += 1
                else:
                    break

            if len(collected_imports) > 1:
                joined_items = ", ".join(collected_imports)
                new_lines.append(f"{indent}import {joined_items}")
                i = j
                continue

        # ── 2. AGRUPAMENTO DE 'from X import A', 'from X import B' ─────
        elif (stripped.startswith("from ") and 
              " import " in stripped and 
              not stripped.endswith("(") and 
              "#" not in line and 
              ";" not in line):
            
            indent = line[:len(line) - len(stripped)]
            match = re.match(r"^from\s+([\w\.]+)\s+import\s+(.+)$", stripped)
            if match:
                mod_name = match.group(1)
                first_items = match.group(2).strip()
                collected_from_items = [first_items]

                j = i + 1
                while j < n:
                    next_line = lines[j]
                    next_stripped = next_line.strip()
                    next_indent = next_line[:len(next_line) - len(next_stripped)]

                    if (next_indent == indent and
                        next_stripped.startswith(f"from {mod_name} import ") and
                        not next_stripped.endswith("(") and
                        "#" not in next_line and
                        ";" not in next_line):
                        
                        next_match = re.match(rf"^from\s+{re.escape(mod_name)}\s+import\s+(.+)$", next_stripped)
                        if next_match:
                            collected_from_items.append(next_match.group(1).strip())
                            j += 1
                            continue
                    break

                if len(collected_from_items) > 1:
                    joined_from = ", ".join(collected_from_items)
                    new_lines.append(f"{indent}from {mod_name} import {joined_from}")
                    i = j
                    continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines)
    
def inline_single_statement_blocks(code: str) -> str:
    """
    Concatena blocos de instrução única diretamente após ':' na mesma linha.
    Exemplo:
        if not path.exists():
            return None
        --> if not path.exists(): return None
    """
    lines = code.splitlines()
    if len(lines) < 2:
        return code

    def get_indent(line: str) -> int:
        return len(line) - len(line.lstrip())

    def has_balanced_delimiters(line: str) -> bool:
        parens = line.count('(') - line.count(')')
        brackets = line.count('[') - line.count(']')
        braces = line.count('{') - line.count('}')
        single_quotes = line.count("'") % 2
        double_quotes = line.count('"') % 2
        return parens == 0 and brackets == 0 and braces == 0 and single_quotes == 0 and double_quotes == 0

    BLOCK_KEYWORDS = (
        'if ', 'elif ', 'else:', 'while ', 'for ', 'with ',
        'try:', 'except', 'finally:', 'def ', 'class '
    )

    COMPOUND_START = (
        'if ', 'elif ', 'else:', 'while ', 'for ', 'with ',
        'try:', 'except', 'finally:', 'def ', 'class ', '@'
    )

    new_lines = []
    i = 0
    n = len(lines)

    while i < n:
        curr = lines[i]
        stripped_curr = curr.strip()

        # Checa se a linha atual termina com ':' e é um cabeçalho de bloco válido
        is_block_header = (
            stripped_curr.endswith(':') and
            any(stripped_curr.startswith(kw) for kw in BLOCK_KEYWORDS) and
            '#' not in curr  # Evita que comentários engulam a instrução inlined
        )

        if is_block_header and i + 1 < n:
            # Localiza a próxima linha com conteúdo
            next_idx = i + 1
            while next_idx < n and not lines[next_idx].strip():
                next_idx += 1

            if next_idx < n:
                nxt = lines[next_idx]
                stripped_nxt = nxt.strip()
                indent_curr = get_indent(curr)
                indent_nxt = get_indent(nxt)

                # O corpo deve estar indentado em relação ao cabeçalho
                if indent_nxt > indent_curr:
                    # O corpo deve ser uma instrução simples (não outro bloco)
                    is_simple_stmt = (
                        not stripped_nxt.endswith(':') and
                        not any(stripped_nxt.startswith(kw) for kw in COMPOUND_START) and
                        has_balanced_delimiters(stripped_nxt)
                    )

                    if is_simple_stmt:
                        # Checa se após esta linha o bloco desindenta (garante que é corpo ÚNICO)
                        after_idx = next_idx + 1
                        while after_idx < n and not lines[after_idx].strip():
                            after_idx += 1

                        is_single_body = (
                            after_idx >= n or
                            get_indent(lines[after_idx]) <= indent_curr
                        )

                        if is_single_body:
                            # ⚡ Concatena na mesma linha após o ':'
                            inlined = f"{curr} {stripped_nxt}"
                            new_lines.append(inlined)
                            i = next_idx + 1
                            continue

        new_lines.append(curr)
        i += 1

    return '\n'.join(new_lines)

def strip_py_docstrings(text: str) -> str:
    """
    Remove cirurgicamente docstrings de módulos, classes e funções.
    Dupla camada: AST estrutural + Regex de segurança para blocos triplos.
    """
    if not text:
        return text

    # ── CAMADA 1: Remoção Estrutural via AST (preserva indentação e injeta pass se necessário)
    try:
        tree = ast.parse(text)
        lines = text.splitlines()
        spans_to_remove = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                if not node.body:
                    continue
                first = node.body[0]
                if isinstance(first, ast.Expr):
                    val = getattr(first, 'value', None)
                    is_str = False
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        is_str = True
                    elif isinstance(val, ast.Str):
                        is_str = True

                    if is_str:
                        start = getattr(first, 'lineno', None)
                        end = getattr(first, 'end_lineno', start)
                        if start is not None and end is not None:
                            needs_pass = len(node.body) == 1 and not isinstance(node, ast.Module)
                            indent = lines[start - 1][:len(lines[start - 1]) - len(lines[start - 1].lstrip())]
                            spans_to_remove.append((start - 1, end, needs_pass, indent))

        if spans_to_remove:
            spans_to_remove.sort(key=lambda x: x[0], reverse=True)
            for start, end, needs_pass, indent in spans_to_remove:
                if needs_pass:
                    lines[start:end] = [f"{indent}pass"]
                else:
                    del lines[start:end]
            text = '\n'.join(lines)
    except Exception:
        pass  # Se o código estiver truncado, a Camada 2 resolve

    # ── CAMADA 2: Varredura Regex de Segurança (Garante que nenhuma aspa tripla escape)
    # Remove qualquer bloco """...""" ou '''...''' isolado
    pattern = r'(?m)^[ \t]*([ruRU]?("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'))[ \t]*\n?'
    text = re.sub(pattern, '', text)

    return text


def minify_code(code: str, filename: str, no_comments: bool, no_spaces: bool, no_docstrings: bool = False, compact_blocks: bool = False, compact_imports: bool = False) -> str:
    """
    Pipeline de Minificação PASC-11 (Token Saver).
    Suporta Python, C/C++, JS/TS, HTML, CSS e Assembly (.s).
    """
    import re

    # 0. CAMADA DE REMOÇÃO DE DOCSTRINGS (-nd)
    if no_docstrings:
        if filename.endswith('.py'):
            code = strip_py_docstrings(code)
        elif filename.endswith(('.c', '.cpp', '.h', '.hpp')):
            code = re.sub(r'/\*\*[\s\S]*?\*/', '', code)
        elif filename.endswith('.lua'):
            code = re.sub(r'--\[\[[\s\S]*?\]\]', '', code)

    # 0.4. CAMADA DE CONCATENAÇÃO DE IMPORTS (-ci)
    if compact_imports and filename.endswith('.py'):
        code = compact_python_imports(code)

    # 0.5. CAMADA DE CONCATENAÇÃO DE BLOCOS ÚNICOS APÓS ':' (-cb)
    if compact_blocks and filename.endswith('.py'):
        code = inline_single_statement_blocks(code)

    lines = code.splitlines()
    if not lines: 
        return code

    # Preserva Shebang ou encoding da primeira linha se existir
    if lines and lines[0].startswith(("#!", "# -*-")):
        header = [lines[0]]
        body = lines[1:]
    else:
        header = []
        body = lines

    # 1. CAMADA DE REMOÇÃO DE COMENTÁRIOS (-nc)
    if no_comments:
        if filename.endswith('.py'):
            body = [re.sub(r'#.*$', '', line) for line in body]
        elif filename.endswith('.lua'):
            temp_body = '\n'.join(body)
            temp_body = re.sub(r'--\[\[.*?\]\]', '', temp_body, flags=re.DOTALL)
            temp_body = re.sub(r'--.*$', '', temp_body, flags=re.MULTILINE)
            body = temp_body.splitlines()
        elif filename.endswith(('.c', '.cpp', '.h', '.hpp', '.js', '.ts', '.jsx', '.tsx')):
            body = [re.sub(r'//.*$', '', line) for line in body]
            temp_body = '\n'.join(body)
            temp_body = re.sub(r'/\*.*?\*/', '', temp_body, flags=re.DOTALL)
            body = temp_body.splitlines()
        elif filename.endswith(('.html', '.css')):
            temp_body = '\n'.join(body)
            temp_body = re.sub(r'<!--.*?-->', '', temp_body, flags=re.DOTALL)
            temp_body = re.sub(r'/\*.*?\*/', '', temp_body, flags=re.DOTALL)
            body = temp_body.splitlines()
        elif filename.endswith('.s'):
            body = [re.sub(r';.*$', '', line) for line in body]

    # 2. CAMADA DE REMOÇÃO DE ESPAÇOS (-ns)
    if no_spaces:
        body = [l for l in body if l.strip()]
    else:
        body = [l.rstrip() for l in body]

    return '\n'.join(header + body)

def get_ignore_spec(root: str, extra_patterns: list = None):
    """ Carrega especificações de ignorar do intelligence.toml ou defaults. """
    import toml
    import pathspec
    patterns = [
        '.git/', '__pycache__/', 'venv/', '.venv/',
        '*.pyc', '.vscode/', '.idea/', 'dist/', 'build/',
        '*.bak', 'recovery_zone/', 'chief_dossier.json',
        'node_modules/', 'doxoade.egg-info/'
    ]

    # 1. Carrega intelligence.toml (se existir)
    intel_path = os.path.join(root, "intelligence.toml")
    if os.path.exists(intel_path):
        try:
            config = toml.load(intel_path)
            intel_patterns = config.get("ignore", [])
            if intel_patterns:
                patterns.extend(intel_patterns)
        except Exception as e:
            _print_forensic("load_intelligence_toml", e)

    # 2. Carrega [tool.doxoade].ignore do pyproject.toml
    pyproject_path = os.path.join(root, "pyproject.toml")
    if os.path.exists(pyproject_path):
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
        except ImportError:
            try:
                data = toml.load(pyproject_path)
            except Exception:
                data = {}
        except Exception:
            data = {}
        if data:
            pyproject_patterns = (
                (data.get("tool", {}) or {})
                .get("doxoade", {})
                .get("ignore", [])
            )
            if pyproject_patterns:
                patterns.extend(pyproject_patterns)

    if extra_patterns:
        patterns.extend(extra_patterns)
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)

class ChiefInsightVisitor(ast.NodeVisitor):
    def __init__(self, no_docstrings: bool = False):
        self.no_docstrings = no_docstrings
        self.stats = {
            "classes":      [], "functions": [], 
            "imports":      {"stdlib": [], "external": []},
            "complexities": [], "mpot_4_violations": 0, "docstrings": {}
        }
    def _detect_io_calls(self, node: ast.AST) -> List[str]:
        """Rastreia chamadas de IO dentro da função (PASC 8.2)."""
        io_found = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Detecta chamadas diretas (ex: print())
                if isinstance(child.func, ast.Name) and child.func.id in IO_KEYWORDS:
                    io_found.add(child.func.id)
                # Detecta chamadas de módulo (ex: os.path.join())
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name) and child.func.value.id in IO_MODULES:
                        io_found.add(f"{child.func.value.id}.{child.func.attr}")
        return list(io_found)
    def _analyze_func(self, node):
        line_count = (node.end_lineno - node.lineno) if node.end_lineno else 0
        if line_count > 60: self.stats["mpot_4_violations"] += 1
        
        complexity = 1 + sum(1 for child in ast.walk(node) if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)))
        self.stats["complexities"].append(complexity)
        
        self.stats["functions"].append({
            "name":      node.name, 
            "lines":     line_count, 
            "complexity":complexity, 
            "args":      len(node.args.args),
            "io_flow":   self._detect_io_calls(node) # Novo: Rastreio de Fluxo
        })
    def visit_FunctionDef(self, node):
        if not self.no_docstrings:
            doc = ast.get_docstring(node) or ""
            if doc:
                self.stats["docstrings"][node.name] = doc
        self._analyze_func(node)
        self.generic_visit(node)
        self.generic_visit(node)
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._analyze_func(node)
        self.generic_visit(node)
    # REINTEGRANDO LOGICA RESGATADA DO DOSSIER (22/01)
    def visit_ClassDef(self, node):
        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.stats['classes'].append({'name': node.name, 'methods_count': len(methods)})
        self.generic_visit(node)
    def visit_Import(self, node):
        for alias in node.names:
            self._sort_import(alias.name)
    def visit_ImportFrom(self, node):
        if node.module:
            self._sort_import(node.module)
    def _sort_import(self, name):
        """Separa stdlib de externos (PASC 6.1)."""
        root_mod = name.split('.')[0]
        if root_mod in sys.builtin_module_names or root_mod in ['os', 'sys', 'ast', 'json', 're', 'time']:
            self.stats["imports"]["stdlib"].append(name)
        else:
            self.stats["imports"]["external"].append(name)
def analyze_document(file_path: str, ext: str) -> Dict[str, Any]:
    """Extrai dados ricos de documentação (PASC 3.2 / 8.3)."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if ext == '.json':
                data = json.loads(content)
                # Retorna chaves principais para não sobrecarregar se for gigante
                return {"doc_type": "structured_data", "keys": list(data.keys())[:20], "raw": data if len(content) < 5000 else "truncated"}
            elif ext == '.md':
                headers = re.findall(r'^#+\s+(.*)', content, re.MULTILINE)
                return {"doc_type": "markdown", "headers": headers[:10], "brief": content[:500]}
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        return {"error": str(e)}
    return {}
def find_debt_tags(content: str) -> List[Dict[str, Any]]:
    debt = []
    patterns = r'#\s*(TODO|FIXME|BUG|HACK|ADTI)\b[:\s]*(.*)'
    for i, line in enumerate(content.splitlines(), 1):
        m = re.search(patterns, line, re.IGNORECASE)
        if m: debt.append({"line": i, "tag": m.group(1).upper(), "msg": m.group(2).strip()})
    return debt
def _print_forensic(func_name: str, e: Exception):
    import os as _dox_os
    _, _, exc_tb = sys.exc_info()
    f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "unknown"
    line_n = exc_tb.tb_lineno if exc_tb else 0
    print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: {func_name}\033[0m")
    print(f"\033[31m    ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    
def get_god_glossary():
    """Retorna o glossário de arquétipos de engenharia (God Assignment)."""
    return {
        "Zeus": "⚡ Kernel / Orquestrador / Root. Controla permissões e roteamento (CLI, __main__).",
        "Hera": "🦚 Consistência / Contratos / Estado. Mantém a integridade de dados inter-sistemas.",
        "Poseidon": "🌊 Streams / I/O / Caos controlável. Lida com I/O de arquivos e redes.",
        "Hades": "💀 Persistência / Arquivamento. Armazena histórico e logs profundos (banco de dados, cache).",
        "Atena": "🦉 Estratégia / Arquitetura. Define design patterns e lógica de análise profunda.",
        "Ares": "⚔️ Força Bruta / Hack. Ofensiva, scripts rígidos e de execução agressiva (segurança, check).",
        "Apolo": "☀️ Ordem / Código Limpo. Responsável por UI/UX clara no terminal (display, telemetry).",
        "Ártemis": "🏹 Ferramentas Autônomas. Espírito original do Doxoade, independência e precisão.",
        "Hefesto": "🔨 Construção / Engenharia. Build systems, compilação C/Cython (Vulcan).",
        "Hermes": "🪽 Comunicação. APIs, bridges inter-sistemas (integração, middlewares).",
        "Dionísio": "🍷 Caos Criativo. Prototipagem, laboratórios de experimentação, documentação.",
        "Rá": "☀️ Loop Principal. Fonte de energia, clock do sistema.",
        "Osíris": "🌱 Persistência e Renascimento. Snapshots e recovery.",
        "Ísis": "✨ Integração. Magia de juntar partes quebradas (Middlewares).",
        "Hórus": "🦅 Observabilidade. O olho que tudo vê (Telemetria, Chronos).",
        "Ma'at": "⚖️ Ordem e Invariantes. O que nunca pode quebrar (Asserções, auditoria).",
        "Anúbis": "🐺 Validação e Auditoria. O juiz que decide o que passa ou morre (check, security).",
        "Thoth": "📖 Linguagem e Lógica. AST Parsers, Inteligência Simbólica.",
        "Set": "🏜️ Entropia. Falhas esperadas, inputs maliciosos. O sistema maduro espera por Set.",
        "Vulcan": "🔥 Metalurgia Nativa. Compilação C/Cython de alta performance."
    }
    
class SemanticAnalyzer:
    """Extrai a estrutura lógica para tokens de IA (OSL 4 / PASC 8.10)."""
    def __init__(self, code, no_docstrings: bool = False):
        self.code = code
        self.no_docstrings = no_docstrings
        try:
            self.tree = ast.parse(code)
        except Exception:
            self.tree = None
            import sys as _dox_sys, os as _dox_os
            exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: __init__\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            self.tree = None

    def get_map(self):
        if not self.tree: return {"role": "CORRUPT_SOURCE"}
        
        # Identifica o papel do arquivo (God Assignment)
        imports = [n.names[0].name for n in ast.walk(self.tree) if isinstance(n, ast.Import)]
        
        return {
            "role":             self._infer_role(imports),
            "classes":          [n.name for n in ast.walk(self.tree) if isinstance(n, ast.ClassDef)],
            "exported_symbols": [n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) if not n.name.startswith('_')],
            "complexity_index":  len([n for n in ast.walk(self.tree) if isinstance(n, (ast.If, ast.For, ast.While))])
        }

    def _infer_role(self, imports):
        if 'click'   in imports: return "ZEUS_CLI"
        if 'socket'  in imports  or 'requests' in imports: return "POSEIDON_NET"
        if 'sqlite3' in imports: return "HADES_DB"
        return "GENERIC_LOGIC"

    def get_summary(self):
        """Retorna um mapa simplificado da 'alma' do arquivo."""
        if not self.tree: 
            return {"status": "corrupt", "classes": [], "functions": [], "complexity": 0}
        
        funcs = []
        for n in ast.walk(self.tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.no_docstrings:
                    doc_preview = ""
                else:
                    doc = ast.get_docstring(n)
                    doc_preview = doc.split('\n')[0] if doc else ""
                funcs.append({
                    "name": n.name,
                    "docstring": doc_preview
                })
                
        return {
            "status": "stable",
            "classes":    [n.name for n in ast.walk(self.tree) if isinstance(n, ast.ClassDef)],
            "functions":  funcs,
            "complexity":  len([n for n in ast.walk(self.tree) if isinstance(n, (ast.If, ast.For, ast.While))])
        }

    # def get_docstrings(self):
    #     """Mapeia docstrings a símbolos para entendimento contextual."""
    #     docs = {}
    #     if not self.tree or self.no_docstrings: 
    #         return docs
    #     for node in ast.walk(self.tree):
    #         if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
    #             doc = ast.get_docstring(node)
    #             if doc:
    #                 name = getattr(node, 'name', 'module_root')
    #                 docs[name] = {"intent": doc.split('\n')[0], "full_doc": doc}
    #     return docs

    def get_docstrings(self):
        if self.no_docstrings:
            return {}
        docs = {}
        blocks = re.findall(r'/\*\*?(.*?)\*/', self.code, re.DOTALL)
        if blocks:
            docs["c_cpp_comments"] = {"intent": "Extracted block comments", "full_doc": "\n".join(blocks[:3])}
        return docs

class NexusThothMapper:
    """Mapeia a topologia do código para o panteão Doxoade (AI-Ready)."""
    GOD_MAP = {
        "Zeus":    {"keywords":["cli",   "main",        "orchestrator"],"imports":["click", "getopt.h", "argparse.hpp"]},
        "Poseidon":{"keywords":["stream","socket",      "io", "flow"  ],"imports":["asyncio","socket", "sys/socket.h", "curl/curl.h", "arpa/inet.h"]},
        "Hades":   {"keywords":["db",    "storage",     "cache"       ],"imports":["sqlite3","json", "sqlite3.h", "mysql.h", "pqxx"]},
        "Atena":   {"keywords":["logic", "architecture","nexus"       ],"imports": ["abc", "memory", "algorithm", "vector"]},
        "Anúbis":  {"keywords": ["check", "security",    "audit"       ],"imports":["hashlib", "re", "openssl/sha.h", "openssl/md5.h", "regex.h"]}
    }
    
    @classmethod
    def identify(cls, file_path, imports):
        name = file_path.lower()
        for god, criteria in cls.GOD_MAP.items():
            if any(k in name for k in criteria["keywords"]) or \
               any(imp in imports for imp in criteria["imports"]):
                return god
        return "Dionísio"


class CSemanticAnalyzer:
    def __init__(self, code, no_docstrings: bool = False):
        self.code = code
        self.no_docstrings = no_docstrings
        self.classes = []
        self.functions = []
        self.includes = []
        self.complexity = 1
        self._parse()

    def _parse(self):
        # 1. Mapeamento de Includes
        self.includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', self.code)
        
        # 2. Mapeamento de Classes e Structs
        self.classes = re.findall(r'\b(?:class|struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', self.code)
        
        # 3. Mapeamento de Funções (Heurística)
        # Captura: Tipo Retorno + Nome Função + (Args) + {
        func_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_*:&<>\s]+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^;]*\)\s*\{'
        funcs = re.findall(func_pattern, self.code)
        
        # Filtra palavras reservadas capturadas acidentalmente como funções
        reserved = {'if', 'for', 'while', 'switch', 'catch', 'return'}
        self.functions = list(set([f for f in funcs if f not in reserved]))
        
        # 4. Mapeamento de Complexidade (Ramos lógicos)
        logic_branches = re.findall(r'\b(?:if|for|while|catch|case)\b', self.code)
        self.complexity = len(logic_branches) + 1

    def get_summary(self):
        """Retorna um mapa simplificado da 'alma' do arquivo C/C++."""
        return {
            "status": "stable_c_cpp",
            "classes": self.classes,
            "functions": self.functions,
            "complexity": self.complexity
        }

    def get_docstrings(self):
        """Extração simplificada de blocos de comentários."""
        docs = {}
        blocks = re.findall(r'/\*\*?(.*?)\*/', self.code, re.DOTALL)
        if blocks:
            docs["c_cpp_comments"] = {"intent": "Extracted block comments", "full_doc": "\n".join(blocks[:3])}
        return docs
        
class _HTMLStatsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = {}
        self.scripts = 0
        self.styles = 0
        self.complexity = 0
        
    def handle_starttag(self, tag, attrs):
        self.complexity += 1
        self.tags[tag] = self.tags.get(tag, 0) + 1
        if tag == 'script':
            self.scripts += 1
        elif tag == 'style':
            self.styles += 1

class HTMLSemanticAnalyzer:
    """Analisador Semântico para arquivos HTML (PASC Compliance)."""
    def __init__(self, content: str):
        self.content = content
        self.parser = _HTMLStatsParser()
        self.lines_of_code = 0
        self._parse()
        
    def _parse(self):
        try:
            self.lines_of_code = len(self.content.splitlines())
            self.parser.feed(self.content)
        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context="HTMLSemanticAnalyzer._parse", silent=True)
            
    def get_summary(self):
        # Seleciona as 5 tags mais usadas para compor o profile do arquivo
        top_tags = dict(sorted(self.parser.tags.items(), key=lambda item: item[1], reverse=True)[:5])
        
        return {
            "lines": self.lines_of_code,
            "complexity": self.parser.complexity,  # Complexidade baseada em volume de nós/tags
            "html_stats": {
                "unique_tags": len(self.parser.tags),
                "embedded_scripts": self.parser.scripts,
                "embedded_styles": self.parser.styles,
                "top_tags": top_tags
            }
        }

class TOMLSemanticAnalyzer:
    """Extrai a estrutura de arquivos de configuração TOML (PASC 12.1)."""
    def __init__(self, content: str):
        self.content = content
        self.sections = []
        self.keys = []
        self._parse()

    def _parse(self):
        try:
            import toml
            data = toml.loads(self.content)
            for k, v in data.items():
                if isinstance(v, dict): self.sections.append(k)
                else: self.keys.append(k)
        except Exception:
            self.sections = re.findall(r'^\s*\[([^\]]+)\]', self.content, re.MULTILINE)

    def get_summary(self):
        return {
            "status": "stable_toml",
            "classes": self.sections,      
            "functions": self.keys,        
            "complexity": len(self.sections) + len(self.keys)
        }

class MDSemanticAnalyzer:
    """Extrai a estrutura de documentação Markdown (PASC 12.2)."""
    def __init__(self, content: str):
        self.content = content
        self.headers = []
        self.code_blocks = 0
        self._parse()

    def _parse(self):
        self.headers = re.findall(r'^#+\s+(.*)', self.content, re.MULTILINE)
        self.code_blocks = len(re.findall(r'^```', self.content, re.MULTILINE)) // 2

    def get_summary(self):
        return {
            "status": "stable_md",
            "classes": [],
            "functions": self.headers[:20], 
            "complexity": len(self.headers) + self.code_blocks,
            "doc_stats": {
                "total_headers": len(self.headers),
                "embedded_code_blocks": self.code_blocks
            }
        }

class AssemblySemanticAnalyzer:
    """Extrai a estrutura de arquivos Assembly (.s) via Regex (PASC 12.3)."""
    def __init__(self, content: str):
        self.content = content
        self.labels = []     
        self.includes = []   
        self._parse()

    def _parse(self):
        self.labels = len(re.findall(r'^[a-zA-Z_\.]\w*:', clean_content, re.MULTILINE))
        self.sections = len(re.findall(r'^\s*(section|SEGMENT)\b', clean_content, re.MULTILINE | re.IGNORECASE))
        self.globals = len(re.findall(r'^\s*(global|GLOBAL|extern|EXTERN)\b', clean_content, re.MULTILINE | re.IGNORECASE))
        self.includes = re.findall(r'(?:\.include|\.import)\s+["<]([^">]+)[">]', self.content)
        
    def get_summary(self):
        branches = re.findall(r'\b(?:j[a-z]{1,3}|call|loop|jmp)\b', self.content, re.IGNORECASE)
        return {
            "status": "stable_asm",
            "classes": [],
            "functions": self.labels,
            "complexity": len(branches) + 1,
            "asm_stats": {
                "total_labels": len(self.labels),
                "branch_instructions": len(branches)
            }
        }

class JSONSemanticAnalyzer:
    """Extrai a estrutura de arquivos de dados JSON (PASC 12.4)."""
    def __init__(self, content: str):
        self.content = content
        self.keys = []
        self.type = "unknown"
        self._parse()

    def _parse(self):
        try:
            import json
            data = json.loads(self.content)
            if isinstance(data, dict):
                self.type = "object"
                self.keys = list(data.keys())[:30] # Limita para não poluir o dossiê
            elif isinstance(data, list):
                self.type = "array"
                self.keys = [f"item_{i}" for i in range(min(len(data), 5))]
        except Exception:
            self.type = "malformed"

    def get_summary(self):
        return {
            "status": "stable_json",
            "classes": [],
            "functions": self.keys,
            "complexity": len(self.keys),
            "json_stats": {"type": self.type, "top_level_keys": len(self.keys)}
        }

class TXTSemanticAnalyzer:
    """Extrai a estrutura de arquivos de texto puro (PASC 12.5)."""
    def __init__(self, content: str):
        self.content = content
        self.lines = 0
        self.words = 0
        self._parse()

    def _parse(self):
        self.lines = len(self.content.splitlines())
        self.words = len(self.content.split())

    def get_summary(self):
        return {
            "status": "stable_txt",
            "classes": [],
            "functions": [],
            "complexity": 1,
            "txt_stats": {"lines": self.lines, "words": self.words}
        }
