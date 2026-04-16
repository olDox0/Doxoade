# doxoade/doxoade/commands/security_systems/maat_engine_integration.py
import ast
import os

def run_internal_security_audit(root, files):
    findings = []
    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
                
            for node in ast.walk(tree):
                # Detecção de eval/exec (O que o Ma'at viu em check_exame.py)
                if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in ['eval', 'exec']:
                    findings.append({
                        'tool': 'NEXUS-INTERNAL',
                        'severity': 'CRITICAL',
                        'message': f"Uso perigoso de {node.func.id} detectado.",
                        'file': os.path.relpath(fpath, root),
                        'line': node.lineno
                    })
                
                # Detecção de sqlite3 direto (Violação de Arquitetura)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == 'sqlite3':
                            findings.append({
                                'tool': 'NEXUS-ARCH',
                                'severity': 'HIGH',
                                'message': "Import direto de sqlite3 proibido. Use doxoade.database.",
                                'file': os.path.relpath(fpath, root),
                                'line': node.lineno
                            })
        except: continue
    return findings