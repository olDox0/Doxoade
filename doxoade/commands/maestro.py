# -*- coding: utf-8 -*-
"""
Doxoade Maestro - v71.1 Gold.
Interpretador de automação (.dox) para pipelines portáveis.
ESTRATÉGIA: Instruction Dispatcher para conformidade MPoT-v71 (Redução de CC: 59 -> 6).
"""

import click
import subprocess
import os
import re
import shlex
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

    # --- DESPACHANTES DE COMANDO (MODULARIZAÇÃO MPoT-17) ---

    def _cmd_print(self, line):
        colors = {
            'PRINT-RED ': (Fore.RED + Style.BRIGHT),
            'PRINT-GREEN ': (Fore.GREEN + Style.BRIGHT),
            'PRINT-YELLOW ': (Fore.YELLOW + Style.BRIGHT),
            'PRINT ': Fore.MAGENTA
        }
        for prefix, color in colors.items():
            if line.startswith(prefix):
                msg = self._resolve_vars(line[len(prefix):].strip().strip('"'))
                click.echo(color + f"[MAESTRO] {msg}")
                return

    def _cmd_vars(self, line):
        if line.startswith('SET '):
            parts = line[4:].split('=')
            var, val = parts[0].strip(), self._resolve_vars(parts[1].strip()).strip('"')
            self.variables[var] = int(val) if val.isdigit() else val
        elif line.startswith('INC '):
            var = line[4:].strip()
            if var in self.variables and isinstance(self.variables[var], int):
                self.variables[var] += 1

    def _cmd_io(self, line):
        if line.startswith('READ_LINES '):
            parts = line[11:].split('->')
            fname, var = self._resolve_vars(parts[0].strip()), parts[1].strip()
            if os.path.exists(fname):
                with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                    self.variables[var] = [l.strip() for l in f.readlines()]
            else: self.variables[var] = []

    def _cmd_execution(self, line):
        if line.startswith('BATCH '):
            parts = line[6:].split('->')
            cmd_str, target_var = parts[0].strip(), (parts[1].strip() if len(parts) > 1 else None)
            cmd_str = self._resolve_vars(cmd_str)
            click.echo(Fore.BLUE + f"   > [SHELL] {cmd_str}")
            try:
                res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, encoding='utf-8') # nosec
                output = res.stdout + res.stderr
                if not target_var: print(output, end='')
                else: self.variables[target_var] = output.strip()
            except Exception as e: click.echo(Fore.RED + f"[MAESTRO BATCH ERROR] {e}")

        elif line.startswith('RUN '):
            parts = line[4:].split('->')
            cmd_str, target_var = self._resolve_vars(parts[0].strip()), (parts[1].strip() if len(parts) > 1 else None)
            click.echo(Fore.CYAN + f"   > Executando: {cmd_str}")
            try:
                args = shlex.split(cmd_str)
                res = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', shell=False)
                output = res.stdout + res.stderr
                if not target_var or res.returncode != 0: click.echo(output)
                if target_var: self.variables[target_var] = output.strip()
            except Exception as e: click.echo(Fore.RED + f"[MAESTRO ERROR] Falha ao executar '{cmd_str}': {e}")

    def _cmd_filesystem(self, line):
        if line.startswith('FIND '):
            parts = line[5:].split('->')
            left, target_var = parts[0].strip(), (parts[1].strip() if len(parts) > 1 else None)
            import glob
            pattern, path = (left.split(" IN ") if " IN " in left else (left, "."))
            full_p = os.path.join(self._resolve_vars(path.strip('" ')), self._resolve_vars(pattern.strip('" ')))
            files = glob.glob(full_p, recursive=True)
            if target_var: self.variables[target_var] = "\n".join(files)
            click.echo(Fore.CYAN + f"   > Encontrados {len(files)} arquivos.")

    def _cmd_fast_utils(self, line):
        if line.startswith("FIND_LINE_NUMBER"):
            parts = line.split(" ")
            term, fpath, dest = self._resolve_vars(parts[1].strip('"\'')), self._resolve_vars(parts[3].strip('"\'')), parts[5]
            found = "-1"
            if os.path.exists(fpath):
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    for idx, l in enumerate(f):
                        if term in l: found = str(idx); break
            self.variables[dest] = found

        elif line.startswith("DELETE_BLOCK_TREE"):
            parts = line.split(" ")
            idx, fpath = int(self._resolve_vars(parts[2])), self._resolve_vars(parts[4].strip('"\''))
            if idx != -1 and os.path.exists(fpath):
                with open(fpath, 'r') as f: lines = f.readlines()
                if idx < len(lines):
                    indent = len(lines[idx]) - len(lines[idx].lstrip())
                    new = lines[:idx]
                    i = idx + 1
                    while i < len(lines):
                        if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= indent: break
                        i += 1
                    new.extend(lines[i:])
                    with open(fpath, 'w') as f: f.writelines(new)
                    click.echo(Fore.GREEN + "   > [MAESTRO FAST] Bloco removido.")

    def _cmd_logic(self, line):
        if line.startswith('IF '):
            res = self._resolve_vars(line)
            m = re.match(r'IF\s+(\w+)\s+(==|!=|CONTAINS)\s+"(.*)"', res)
            if m:
                var, op, val = m.groups()
                cur = str(self.variables.get(var, ""))
                cond = (cur == val) if op == '==' else (cur != val) if op == '!=' else (val in cur)
                if not cond: self._skip_block()
        elif line == 'ELSE': self._skip_block()
        elif line.startswith('FOR '):
            parts = line[4:].split(' IN ')
            var, list_name = parts[0].strip(), parts[1].strip()
            items = self.variables.get(list_name, [])
            if isinstance(items, str): items = items.splitlines()
            if not items: self._skip_block()
            else:
                self.loop_stack.append({'type': 'FOR', 'start_ip': self.ip, 'var': var, 'items': items, 'idx': 0})
                self.variables[var] = items[0]
        elif line == 'END' and self.loop_stack:
            lp = self.loop_stack[-1]
            lp['idx'] += 1
            if lp['idx'] < len(lp['items']):
                self.variables[lp['var']] = lp['items'][lp['idx']]
                self.ip = lp['start_ip']
            else: self.loop_stack.pop()
        elif line == 'BREAK' and self.loop_stack:
            self.loop_stack.pop()
            self._skip_block(break_loop=True)

    def _skip_block(self, break_loop=False):
        nesting = 1
        while self.ip < len(self.lines):
            line = self.lines[self.ip].strip() # FIX: Essencial para detectar 'END' ou 'ELSE'
            self.ip += 1
            if any(line.startswith(k) for k in ['IF ', 'FOR ', 'WHILE ']): nesting += 1
            elif line == 'END':
                nesting -= 1
                if nesting == 0: return
            elif line == 'ELSE' and nesting == 1 and not break_loop: return

    # --- ORQUESTRADOR (COMPLEXIDADE REDUZIDA) ---

    def run(self):
        """Loop de execução principal (Dispatcher)."""
        while self.ip < len(self.lines):
            raw_line = self.lines[self.ip]
            line = raw_line.strip() # FIX: Garante que espaços não quebrem o Dispatcher
            self.ip += 1 
            
            if not line or line.startswith('#'): continue

            # Roteamento de comandos (agora com a linha limpa)
            self._cmd_print(line)
            self._cmd_vars(line)
            self._cmd_io(line)
            self._cmd_execution(line)
            self._cmd_filesystem(line)
            self._cmd_fast_utils(line)
            self._cmd_logic(line)

# (O resto das constantes TEMPLATES e a def maestro permanecem idênticos ao original)
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
    """Executa ou gerencia pipelines de automação (.dox)."""
    if show_list:
        click.echo(Fore.CYAN + "--- Templates Maestro Disponíveis ---")
        for name in TEMPLATES: click.echo(f" - {name}")
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
        with open(filename, 'w', encoding='utf-8') as f: f.write(content.strip())
        click.echo(Fore.GREEN + f"Workflow criado: {filename}")
        return
    if not workflow_file:
        click.echo(Fore.RED + "Erro: Forneça um arquivo .dox ou use --list/--use.")
        return
    click.echo(Fore.BLUE + Style.BRIGHT + f"--- DOXOADE MAESTRO: {workflow_file} ---")
    interpreter = MaestroInterpreter()
    interpreter.execute_file(workflow_file)