# doxoade/tools/analysis.py
import ast
import hashlib
import re
import json

def _get_file_hash(file_path):
    """Calcula o hash SHA256 do conteúdo de um arquivo."""
    h = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except IOError:
        return None

def _get_code_snippet(file_path, line_number, context_lines=2):
    if not line_number or not isinstance(line_number, int) or line_number <= 0: return None
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        snippet = {i + 1: lines[i].rstrip('\n') for i in range(start, end)}
        return snippet
    except (IOError, IndexError): return None

def _get_code_snippet_from_string(content, line_number, context_lines=2):
    if not line_number or not isinstance(line_number, int) or line_number <= 0: return None
    try:
        lines = content.splitlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        return {i + 1: lines[i] for i in range(start, end)}
    except IndexError: return None

def _extract_function_parameters(func_node):
    params = []
    for arg in func_node.args.args:
        param_type = ast.unparse(arg.annotation) if arg.annotation else "não anotado"
        params.append({'name': arg.arg, 'type': param_type})
    return params

def _find_returns_and_risks_in_function(func_node):
    returns = []
    risks = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value:
            return_type = "literal" if isinstance(node.value, ast.Constant) else "variável" if isinstance(node.value, ast.Name) else "expressão"
            returns.append({'lineno': node.lineno, 'type': return_type})
        elif isinstance(node, ast.Subscript):
            risks.append({
                'lineno': node.lineno,
                'message': "Acesso a dicionário/lista sem tratamento.",
                'details': f"Acesso direto a '{ast.unparse(node)}' pode causar 'KeyError' ou 'IndexError'."
            })
    return returns, risks

def _get_complexity_rank(complexity):
    if complexity > 20: return "Altissima"
    if complexity > 15: return "Alta"
    if complexity > 10: return "Média"
    if complexity > 5: return "Baixa"
    return "Baixissima"

def _analyze_function_flow(tree, content):
    dossiers = []
    try:
        from radon.visitors import ComplexityVisitor
        complexity_map = {f.name: f.complexity for f in ComplexityVisitor.from_code(content).functions}
    except ImportError:
        complexity_map = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            complexity = complexity_map.get(node.name, 0)
            params = _extract_function_parameters(node)
            returns, risks = _find_returns_and_risks_in_function(node)
            dossiers.append({
                'name': node.name,
                'lineno': node.lineno,
                'params': params,
                'returns': returns,
                'risks': risks,
                'complexity': complexity,
                'complexity_rank': _get_complexity_rank(complexity)
            })
    return dossiers

def analyze_file_structure(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if not content.strip():
                return {'functions': []}
            tree = ast.parse(content, filename=file_path)
    except (SyntaxError, IOError) as e:
        return {'error': f"Falha ao ler ou analisar o arquivo: {e}"}

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append({
                'name': node.name,
                'lineno': node.lineno,
                'args': len(node.args.args)
            })
    return {'functions': functions}

def _mine_traceback(stderr_output):
    """Analisa um traceback bruto."""
    if not stderr_output: return None
    file_blocks = list(re.finditer(r'File "(.+?)", line (\d+), in (.+?)\n\s*(.+?)\n', stderr_output))
    error_match = re.search(r'\n(\w+Error|Exception): (.+)', stderr_output)
    
    if not error_match:
        error_match = re.search(r'\n(\w+): (.+)', stderr_output)

    if not error_match: return None

    error_type = error_match.group(1)
    message = error_match.group(2)
    
    if file_blocks:
        last_block = file_blocks[-1]
        code_line = last_block.group(4).strip()
        return {
            'file': last_block.group(1),
            'line': int(last_block.group(2)),
            'context': last_block.group(3),
            'code': code_line,
            'error_type': error_type,
            'message': message
        }
    else:
        return {
            'file': 'Desconhecido',
            'line': 0,
            'context': 'Runtime',
            'code': 'N/A',
            'error_type': error_type,
            'message': message
        }

def _analyze_runtime_error(error_data):
    if not error_data: return None
    etype = error_data['error_type']
    msg = error_data['message']
    
    suggestion = None
    if etype == 'ModuleNotFoundError':
        module = msg.replace("No module named ", "").strip("'")
        suggestion = f"Falta instalar ou importar: '{module}'.\n      Tente: pip install {module} ou verifique o import."
    elif etype == 'ZeroDivisionError':
        suggestion = "Divisão por zero detectada. Adicione uma verificação 'if divisor != 0:'."
    elif etype == 'IndexError':
        suggestion = "Tentativa de acessar um índice que não existe na lista. Verifique o tamanho (len)."
    elif etype == 'KeyError':
        suggestion = f"A chave {msg} não existe no dicionário. Use .get({msg})."
    elif etype == 'TypeError' and "NoneType" in msg:
        suggestion = "Uma variável é 'None' onde não deveria. Verifique retornos de função."
    elif etype == 'IndentationError':
        suggestion = "Erro de indentação. Mistura de tabs e espaços ou alinhamento incorreto."
    elif etype == 'SyntaxError':
        suggestion = "Erro de sintaxe. Verifique parênteses não fechados ou dois pontos ':'."

    return suggestion
    
def _sanitize_json_output(json_data, project_path):
    raw_json_string = json.dumps(json_data)
    path_to_replace = project_path.replace('\\', '\\\\')
    sanitized_string = raw_json_string.replace(path_to_replace, "<PROJECT_PATH>")
    return json.loads(sanitized_string)

def _get_all_findings(results_report):
    """Extrai uma lista plana de todos os findings de um relatório de 'check'."""
    all_findings = []
    if not results_report or 'file_reports' not in results_report:
        return []
    for file_path, report in results_report['file_reports'].items():
        for finding in report.get('static_analysis', {}).get('findings', []):
            finding['path_for_diff'] = file_path 
            all_findings.append(finding)
    return all_findings
