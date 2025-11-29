# doxoade/commands/maestro.py
import click
import subprocess
import os
import re
import shlex
from colorama import Fore, Style

class MaestroInterpreter:
    def __init__(self):
        self.variables = {}
        self.history = []

    def _resolve_vars(self, text):
        """Substitui {VAR} pelo valor da variável."""
        for key, val in self.variables.items():
            text = text.replace(f"{{{key}}}", str(val))
        return text

    def execute_file(self, filepath):
        if not os.path.exists(filepath):
            click.echo(Fore.RED + f"[MAESTRO] Arquivo não encontrado: {filepath}")
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines()]

        self._execute_block(lines)

    def _execute_block(self, lines):
        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1
            
            # Ignora comentários e linhas vazias
            if not line or line.startswith('#'):
                continue

            if line.startswith('PRINT '):
                msg = self._resolve_vars(line[6:].strip().strip('"'))
                click.echo(Fore.MAGENTA + f"[MAESTRO] {msg}") # Padrão
            
            elif line.startswith('PRINT-RED '):
                msg = self._resolve_vars(line[10:].strip().strip('"'))
                click.echo(Fore.RED + Style.BRIGHT + f"[MAESTRO] {msg}")
            
            elif line.startswith('PRINT-GREEN '):
                msg = self._resolve_vars(line[12:].strip().strip('"'))
                click.echo(Fore.GREEN + Style.BRIGHT + f"[MAESTRO] {msg}")
                
            elif line.startswith('PRINT-YELLOW '):
                msg = self._resolve_vars(line[13:].strip().strip('"'))
                click.echo(Fore.YELLOW + Style.BRIGHT + f"[MAESTRO] {msg}")

            # --- COMANDO BATCH (Script Nativo) ---
            # Executa diretamente no shell do sistema (cmd ou bash)
            # Sintaxe: BATCH echo "oi" -> VAR
            elif line.startswith('BATCH '):
                parts = line[6:].split('->')
                cmd_str = parts[0].strip()
                target_var = parts[1].strip() if len(parts) > 1 else None
                
                cmd_str = self._resolve_vars(cmd_str)
                
                click.echo(Fore.BLUE + f"   > [SHELL] {cmd_str}")
                
                try:
                    # shell=True permite pipes e redirecionamentos nativos
                    result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
                    
                    output = result.stdout + result.stderr
                    
                    # Se não capturar, mostra na tela
                    if not target_var:
                        print(output, end='')
                    else:
                        self.variables[target_var] = output.strip()
                        
                except Exception as e:
                    click.echo(Fore.RED + f"[MAESTRO BATCH ERROR] {e}")

            # Comando: RUN
            elif line.startswith('RUN '):
                parts = line[4:].split('->')
                cmd_str = parts[0].strip()
                target_var = parts[1].strip() if len(parts) > 1 else None
                
                cmd_str = self._resolve_vars(cmd_str)
                
                click.echo(Fore.CYAN + f"   > Executando: {cmd_str}")
                
                # Executa (capturando sempre para poder usar em variáveis)
                try:
                    # Usa shell=True para permitir pipes e comandos complexos se necessário
                    # ou shlex para segurança. Vamos de shlex para consistência com o resto.
                    args = shlex.split(cmd_str)
                    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
                    
                    output = result.stdout + result.stderr
                    
                    # Mostra output se não for capturado, ou se tiver erro
                    if not target_var or result.returncode != 0:
                         click.echo(output)

                    if target_var:
                        self.variables[target_var] = output.strip()
                        
                except Exception as e:
                    click.echo(Fore.RED + f"[MAESTRO ERROR] Falha ao executar '{cmd_str}': {e}")

            # Comando: IF
            elif line.startswith('IF '):
                # Sintaxe: IF VAR CONTAINS "TEXTO"
                # Parsing simplificado
                match = re.match(r'IF\s+(\w+)\s+CONTAINS\s+"(.*)"', line)
                if match:
                    var_name, search_text = match.groups()
                    var_value = self.variables.get(var_name, "")
                    condition = search_text in var_value
                else:
                    click.echo(Fore.RED + f"[MAESTRO SINTAXE] IF inválido: {line}")
                    condition = False

                # Encontra o bloco ELSE e END
                block_content = []
                else_content = []
                nesting = 1
                
                # Escaneia para achar o escopo
                has_else = False
                while i < len(lines):
                    inner_line = lines[i]
                    i += 1
                    
                    if inner_line.startswith('IF '):
                        nesting += 1
                    elif inner_line == 'END':
                        nesting -= 1
                        if nesting == 0: break
                    elif inner_line == 'ELSE' and nesting == 1:
                        has_else = True
                        continue # Pula a linha do ELSE e começa a gravar no else_content
                    
                    if has_else:
                        else_content.append(inner_line)
                    else:
                        block_content.append(inner_line)

                # Executa o bloco correto recursivamente
                if condition:
                    self._execute_block(block_content)
                elif else_content:
                    self._execute_block(else_content)

            elif line == 'ELSE' or line == 'END':
                # Se encontramos isso aqui fora do loop do IF, é erro de estrutura ou fim de fluxo
                pass

            # Comando: FIND (Glob)
            # Sintaxe: FIND "*.py" [IN "path"] -> VAR
            elif line.startswith('FIND '):
                # Parse simplificado
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
                else:
                    pattern = pattern.strip().strip('"')

                # Resolve variáveis no path/pattern
                path = self._resolve_vars(path)
                pattern = self._resolve_vars(pattern)

                full_pattern = os.path.join(path, pattern)
                files = glob.glob(full_pattern, recursive=True)
                
                result_str = "\n".join(files)
                if target_var:
                    self.variables[target_var] = result_str
                
                click.echo(Fore.CYAN + f"   > Encontrados {len(files)} arquivos.")

            # Comando: GREP (Busca em texto)
            # Sintaxe: GREP "texto" IN VAR -> VAR_RESULT
            elif line.startswith('GREP '):
                parts = line[5:].split('->')
                left = parts[0].strip()
                target_var = parts[1].strip() if len(parts) > 1 else None
                
                if " IN " not in left:
                    click.echo(Fore.RED + "[MAESTRO] Sintaxe GREP inválida.")
                    continue
                    
                term, source_var = left.split(" IN ")
                term = term.strip().strip('"')
                source_var = source_var.strip()
                
                term = self._resolve_vars(term)
                content = self.variables.get(source_var, "")
                
                # Filtra linhas
                found_lines = [l for l in content.splitlines() if term in l]
                result_str = "\n".join(found_lines)
                
                if target_var:
                    self.variables[target_var] = result_str
                    
                click.echo(Fore.CYAN + f"   > Grep encontrou {len(found_lines)} ocorrências.")



# Templates Embutidos
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
    # Aqui iria o comando de build/release
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
    # Modo Listagem
    if show_list:
        click.echo(Fore.CYAN + "--- Templates Maestro Disponíveis ---")
        for name in TEMPLATES:
            click.echo(f" - {name}")
        return

    # Modo Criação (Use)
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

    # Modo Execução
    if not workflow_file:
        click.echo(Fore.RED + "Erro: Forneça um arquivo .dox ou use --list/--use.")
        return

    click.echo(Fore.BLUE + Style.BRIGHT + f"--- DOXOADE MAESTRO: {workflow_file} ---")
    interpreter = MaestroInterpreter()
    interpreter.execute_file(workflow_file)