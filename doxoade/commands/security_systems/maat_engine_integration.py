# doxoade/doxoade/commands/security_systems/maat_engine_integration.py
import ast
import os

def run_internal_security_audit(root, files):
    findings = []
    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines() # Para checar comentários por linha
                tree = ast.parse(content)
                
            for node in ast.walk(tree):
                # 1. Detecção de eval/exec (Padrão Aegis)
                if isinstance(node, ast.Call):
                    func_id = ""
                    if isinstance(node.func, ast.Name):
                        func_id = node.func.id
                    
                    if func_id in ['eval', 'exec']:
                        # Verifica se a linha contém autorização explícita
                        line_content = lines[node.lineno - 1]
                        if "# noqa" in line_content:
                            continue # Autorizado pela engenharia
                            
                        findings.append({
                            'tool': 'NEXUS-INTERNAL',
                            'severity': 'CRITICAL',
                            'message': f"Uso perigoso de {func_id} detectado. Use aegis_core.nexus_{func_id}() ou # noqa.",
                            'file': os.path.relpath(fpath, root),
                            'line': node.lineno
                        })
                
                # 2. Detecção de sqlite3 direto (Violação de Arquitetura)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == 'sqlite3':
                            line_content = lines[node.lineno - 1]
                            if "# noqa" in line_content:
                                continue # Import autorizado (wrapper ou emergência)
                            
                            findings.append({
                                'tool': 'NEXUS-ARCH',
                                'severity': 'HIGH',
                                'message': "Import direto de sqlite3 proibido. Use nexus_db ou # noqa.",
                                'file': os.path.relpath(fpath, root),
                                'line': node.lineno
                            })
                            
                # 3. Detecção de From sqlite3
                if isinstance(node, ast.ImportFrom) and node.module == 'sqlite3':
                    line_content = lines[node.lineno - 1]
                    if "# noqa" not in line_content:
                        findings.append({
                            'tool': 'NEXUS-ARCH',
                            'severity': 'HIGH',
                            'message': "Import from sqlite3 proibido. Use nexus_db.",
                            'file': os.path.relpath(fpath, root),
                            'line': node.lineno
                        })
                        
        except: continue
    return findings