# doxoade/commands/maestro.py
import click
import subprocess
import os
import re
import shlex # <--- Segurança
from colorama import Fore, Style

class MaestroInterpreter:
    def __init__(self):
        self.variables = {}
        self.lines = []
        self.ip = 0 
        self.loop_stack = []

    def _resolve_vars(self, text):
        for key, val in self.variables.items():
            text = text.replace(f"{{{key}}}", str(val))
        return text

    def execute_file(self, filepath):
        if not os.path.exists(filepath):
            click.echo(Fore.RED + f"[MAESTRO] Arquivo não encontrado: {filepath}")
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            self.lines = [l.strip() for l in f.readlines()]
        
        self.ip = 0
        self.run()

    def run(self):
        while self.ip < len(self.lines):
            line = self.lines[self.ip]
            self.ip += 1 
            
            if not line or line.startswith('#'): continue

            if line.startswith('PRINT '):
                msg = self._resolve_vars(line[6:].strip().strip('"'))
                click.echo(Fore.MAGENTA + f"[MAESTRO] {msg}")
            elif line.startswith('PRINT-RED '):
                msg = self._resolve_vars(line[10:].strip().strip('"'))
                click.echo(Fore.RED + Style.BRIGHT + f"[MAESTRO] {msg}")
            elif line.startswith('PRINT-GREEN '):
                msg = self._resolve_vars(line[12:].strip().strip('"'))
                click.echo(Fore.GREEN + Style.BRIGHT + f"[MAESTRO] {msg}")
            elif line.startswith('PRINT-YELLOW '):
                msg = self._resolve_vars(line[13:].strip().strip('"'))
                click.echo(Fore.YELLOW + Style.BRIGHT + f"[MAESTRO] {msg}")
            elif line.startswith('SET '):
                parts = line[4:].split('=')
                var = parts[0].strip()
                val = self._resolve_vars(parts[1].strip()).strip('"')
                if val.isdigit(): val = int(val)
                self.variables[var] = val
            elif line.startswith('INC '):
                var = line[4:].strip()
                if var in self.variables and isinstance(self.variables[var], int):
                    self.variables[var] += 1
            elif line.startswith('READ_LINES '):
                parts = line[11:].split('->')
                fname = self._resolve_vars(parts[0].strip())
                var = parts[1].strip()
                if os.path.exists(fname):
                    with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                        self.variables[var] = [l.strip() for l in f.readlines()]
                else:
                    self.variables[var] = []

            # --- CORREÇÃO DE SEGURANÇA BATCH ---
            elif line.startswith('BATCH '):
                # BATCH é intencionalmente um shell command, mas vamos tentar usar shlex se possível
                # ou manter shell=True mas com aviso (Bandit vai reclamar, mas é 'by design')
                parts = line[6:].split('->')
                cmd_str = parts[0].strip()
                target_var = parts[1].strip() if len(parts) > 1 else None
                
                cmd_str = self._resolve_vars(cmd_str)
                click.echo(Fore.BLUE + f"   > [SHELL] {cmd_str}")
                
                try:
                    # Para comandos complexos de SO (pipe, redirect), shell=True é necessário.
                    # Vamos marcar como # nosec para o Bandit ignorar, pois é feature.
                    result = subprocess.run(
                        cmd_str, 
                        shell=True,  # nosec
                        capture_output=True, text=True, encoding='utf-8', errors='replace'
                    )
                    output = result.stdout + result.stderr
                    
                    if not target_var: print(output, end='')
                    else: self.variables[target_var] = output.strip()
                except Exception as e:
                    click.echo(Fore.RED + f"[MAESTRO BATCH ERROR] {e}")

            # --- CORREÇÃO DE SEGURANÇA RUN (Doxoade) ---
            elif line.startswith('RUN '):
                parts = line[4:].split('->')
                cmd_str = parts[0].strip()
                target_var = parts[1].strip() if len(parts) > 1 else None
                
                cmd_str = self._resolve_vars(cmd_str)
                click.echo(Fore.CYAN + f"   > Executando: {cmd_str}")
                
                try:
                    # AQUI MUDAMOS: shlex.split + shell=False
                    args = shlex.split(cmd_str)
                    result = subprocess.run(
                        args, 
                        capture_output=True, text=True, encoding='utf-8', errors='replace',
                        shell=False
                    )
                    output = result.stdout + result.stderr
                    
                    if not target_var or result.returncode != 0:
                         click.echo(output)

                    if target_var:
                        self.variables[target_var] = output.strip()
                except Exception as e:
                    click.echo(Fore.RED + f"[MAESTRO ERROR] Falha ao executar '{cmd_str}': {e}")

            elif line.startswith('FIND '):
                parts = line[5:].split('->')
                left = parts[0].strip()
                target_var = parts[1].strip() if len(parts) > 1 else None
                import glob
                path = "."
                pattern = left
                if " IN " in left:
                    pattern, path = left.split(" IN ")
                    pattern = pattern.strip().strip('"')
                    path = path.strip().strip('"')
                else: pattern = pattern.strip().strip('"')
                path = self._resolve_vars(path)
                pattern = self._resolve_vars(pattern)
                full_pattern = os.path.join(path, pattern)
                files = glob.glob(full_pattern, recursive=True)
                result_str = "\n".join(files)
                if target_var: self.variables[target_var] = result_str
                click.echo(Fore.CYAN + f"   > Encontrados {len(files)} arquivos.")

            elif line.startswith('GREP '):
                parts = line[5:].split('->')
                left = parts[0].strip()
                target_var = parts[1].strip() if len(parts) > 1 else None
                if " IN " not in left: continue
                term, source_var = left.split(" IN ")
                term = self._resolve_vars(term.strip().strip('"'))
                source_var = source_var.strip()
                content = self.variables.get(source_var, "")
                if isinstance(content, list): content = "\n".join(content)
                found_lines = [l for l in content.splitlines() if term in l]
                if target_var: self.variables[target_var] = "\n".join(found_lines)
                click.echo(Fore.CYAN + f"   > Grep encontrou {len(found_lines)} ocorrências.")

            elif line.startswith("FIND_LINE_NUMBER"):
                try:
                    parts = line.split(" ")
                    search_term = self._resolve_vars(parts[1].strip('"\''))
                    target_file = self._resolve_vars(parts[3].strip('"\''))
                    dest_var = parts[5]
                    found_line = "-1"
                    if os.path.exists(target_file):
                        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                            for idx, file_line in enumerate(f):
                                if search_term in file_line:
                                    found_line = str(idx)
                                    break
                    self.variables[dest_var] = found_line
                except Exception: pass

            elif line.startswith("DELETE_BLOCK_TREE"):
                try:
                    parts = line.split(" ")
                    start_idx = int(self._resolve_vars(parts[2]))
                    target_file = self._resolve_vars(parts[4].strip('"\''))
                    if start_idx != -1 and os.path.exists(target_file):
                        with open(target_file, 'r') as f: lines = f.readlines()
                        if start_idx < len(lines):
                            base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
                            new_lines = lines[:start_idx]
                            i = start_idx + 1
                            while i < len(lines):
                                if not lines[i].strip(): 
                                    i += 1; continue
                                if len(lines[i]) - len(lines[i].lstrip()) > base_indent: 
                                    i += 1
                                else: break
                            new_lines.extend(lines[i:])
                            with open(target_file, 'w') as f: f.writelines(new_lines)
                            click.echo(Fore.GREEN + f"   > [MAESTRO FAST] Bloco removido.")
                except Exception: pass

            elif line.startswith('IF '):
                line_resolved = self._resolve_vars(line)
                match = re.match(r'IF\s+(\w+)\s+(==|!=|CONTAINS)\s+"(.*)"', line_resolved)
                condition = False
                if match:
                    var_name, op, val_str = match.groups()
                    var_val = str(self.variables.get(var_name, ""))
                    if op == '==': condition = (var_val == val_str)
                    elif op == '!=': condition = (var_val != val_str)
                    elif op == 'CONTAINS': condition = (val_str in var_val)
                if not condition: self._skip_block()
            
            elif line == 'ELSE': self._skip_block()
            
            elif line.startswith('FOR '):
                parts = line[4:].split(' IN ')
                iter_var = parts[0].strip()
                list_name = parts[1].strip()
                source_list = self.variables.get(list_name, [])
                if isinstance(source_list, str): source_list = source_list.splitlines()
                if not source_list:
                    self._skip_block()
                else:
                    self.loop_stack.append({'type': 'FOR', 'start_ip': self.ip, 'var': iter_var, 'items': source_list, 'idx': 0})
                    self.variables[iter_var] = source_list[0]

            elif line == 'END':
                if self.loop_stack:
                    loop = self.loop_stack[-1]
                    if loop['type'] == 'FOR':
                        loop['idx'] += 1
                        if loop['idx'] < len(loop['items']):
                            self.variables[loop['var']] = loop['items'][loop['idx']]
                            self.ip = loop['start_ip']
                        else: self.loop_stack.pop()
            
            elif line == 'BREAK':
                if self.loop_stack:
                    self.loop_stack.pop()
                    self._skip_block(break_loop=True)

    def _skip_block(self, break_loop=False):
        nesting = 1
        while self.ip < len(self.lines):
            line = self.lines[self.ip]
            self.ip += 1
            if line.startswith('IF ') or line.startswith('FOR ') or line.startswith('WHILE '): nesting += 1
            elif line == 'END':
                nesting -= 1
                if nesting == 0: return
            elif line == 'ELSE' and nesting == 1 and not break_loop: return

TEMPLATES = {
    "ci-padrao": """
# Pipeline de Integração Contínua Local
PRINT "--- CI START ---"
RUN doxoade check . --no-cache -> REPORT
IF REPORT CONTAINS "problema crítico"
    PRINT "FALHA: O código não está seguro."
    RUN doxoade check . --fix
ELSE
    PRINT "SUCESSO: Código aprovado."
    RUN doxoade health
END
PRINT "--- CI END ---"
""",
    "deploy-seguro": """
# Pipeline de Deploy com Verificação de Segurança
PRINT "Verificando segurança..."
RUN doxoade check . --no-cache -> CHECK
IF CHECK CONTAINS "SECURITY"
    PRINT "ABORTAR: Falhas de segurança detectadas (Hunter Probe)."
ELSE
    PRINT "Segurança OK. Preparando release..."
END
"""
}

@click.command('maestro')
@click.argument('workflow_file', required=False, type=click.Path())
@click.option('--list', 'show_list', is_flag=True, help="Lista templates de workflow disponíveis.")
@click.option('--use', 'template_name', help="Cria um arquivo .dox a partir de um template.")
def maestro(workflow_file, show_list, template_name):
    """
    Executa ou gerencia pipelines de automação (.dox).
    """
    if show_list:
        click.echo(Fore.CYAN + "--- Templates Maestro Disponíveis ---")
        for name in TEMPLATES:
            click.echo(f" - {name}")
        return

    if template_name:
        content = TEMPLATES.get(template_name)
        if not content:
            click.echo(Fore.RED + f"Template '{template_name}' não encontrado.")
            return
        
        filename = f"{template_name}.dox"
        if os.path.exists(filename):
             click.echo(Fore.YELLOW + f"Arquivo '{filename}' já existe.")
             return
             
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content.strip())
        click.echo(Fore.GREEN + f"Workflow criado: {filename}")
        click.echo("Execute com: doxoade maestro " + filename)
        return

    if not workflow_file:
        click.echo(Fore.RED + "Erro: Forneça um arquivo .dox ou use --list/--use.")
        return

    click.echo(Fore.BLUE + Style.BRIGHT + f"--- DOXOADE MAESTRO: {workflow_file} ---")
    interpreter = MaestroInterpreter()
    interpreter.execute_file(workflow_file)