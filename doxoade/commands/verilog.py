# doxoade/commands/verilog.py
import click
import os
import subprocess
import re
from colorama import Fore
from ..shared_tools import ExecutionLogger, _get_project_config, _get_code_snippet

def check_iverilog_installed():
    """Verifica se o Icarus Verilog está no PATH."""
    try:
        subprocess.run(['iverilog', '-V'], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def find_verilog_library_dirs(root_path, ignore_dirs):
    """Encontra diretórios que contêm arquivos Verilog."""
    lib_dirs = set()
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        if any(f.endswith(('.v', '.sv')) for f in files):
            lib_dirs.add(root)
    return list(lib_dirs)

def parse_iverilog_output(output):
    """Minera o output do iverilog."""
    findings = []
    pattern = re.compile(r'^(?P<file>.+?):(?P<line>\d+):\s*(?P<msg>.+)$')
    
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            msg = match.group('msg').strip()
            severity = 'ERROR'
            category = 'COMPILER'
            
            msg_lower = msg.lower()
            if 'syntax error' in msg_lower:
                category = 'SYNTAX'
                severity = 'CRITICAL'
            elif 'unknown module' in msg_lower or 'implicit' in msg_lower:
                category = 'LINKING'
            elif 'include file' in msg_lower and 'not found' in msg_lower:
                category = 'INCLUDE'
                severity = 'CRITICAL'
            elif 'warning' in msg_lower:
                category = 'WARNING'
                severity = 'WARNING'
            elif 'already declared' in msg_lower:
                category = 'DUPLICATE'
                severity = 'CRITICAL'

            findings.append({
                'file': match.group('file'),
                'line': int(match.group('line')),
                'message': msg,
                'severity': severity,
                'category': category
            })
    return findings

def scan_verilog_files(path, ignore_set):
    """Coleta arquivos alvo."""
    verilog_files = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ignore_set and not d.startswith('.')]
        for file in files:
            if file.endswith(('.v', '.sv')):
                verilog_files.append(os.path.join(root, file))
    return verilog_files

@click.command('verilog')
@click.pass_context
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--entrypoint', '-e', help="Arquivo principal para verificação de linkagem.")
@click.option('--no-libs', is_flag=True, help="Desativa busca automática de bibliotecas (-y). Use se seu código usa 'include'.")
def verilog(ctx, path, entrypoint, no_libs):
    """
    Diagnóstico de Hardware.
    """
    with ExecutionLogger('verilog', path, ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [VERILOG] Diagnóstico de Hardware em '{path}' ---")
        
        if not check_iverilog_installed():
            click.echo(Fore.RED + "[ERRO] 'iverilog' não encontrado no PATH."); return

        config = _get_project_config(logger, start_path=path)
        ignore_list = set(config.get('ignore', [])) | {'venv', '.git', 'build', 'sim', 'Vers', 'bkp', 'tmp', '__pycache__'}
        
        lib_dirs = find_verilog_library_dirs(path, ignore_list)
        
        target_files = []
        if entrypoint:
            if os.path.exists(entrypoint):
                target_files = [entrypoint]
                click.echo(Fore.YELLOW + f"   > Modo Entrypoint: '{entrypoint}'")
            else:
                click.echo(Fore.RED + f"[ERRO] Arquivo '{entrypoint}' não encontrado."); return
        else:
            target_files = scan_verilog_files(path, ignore_list)
            click.echo(f"   > Verificando {len(target_files)} arquivos...")

        if not target_files:
            click.echo(Fore.YELLOW + "Nenhum arquivo Verilog encontrado."); return

        files_with_errors = 0
        
        # Define a lista de execução
        # Se entrypoint, roda só ele. Se não, roda todos.
        run_list = [entrypoint] if entrypoint else target_files

        for v_file in run_list:
            if not v_file: continue # Segurança

            cmd = ['iverilog', '-t', 'null', '-g2012', '-Wall']
            
            for d in lib_dirs:
                # -I (Include Path): SEMPRE necessário para achar arquivos em `include "file.v"`
                cmd.extend(['-I', d])
                
                # -y (Library Path): Só adiciona se o usuário NÃO desativou (padrão é ativar)
                if not no_libs:
                    cmd.extend(['-y', d])
            
            cmd.append(v_file)

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
                output = result.stderr + result.stdout
                
                if result.returncode != 0 or "error" in output.lower() or "warning" in output.lower():
                    findings = parse_iverilog_output(output)
                    
                    if findings:
                        has_printed_header = False
                        
                        for f in findings:
                            # Ignora avisos de linkagem se não estamos no modo entrypoint e nem no modo libs
                            if not entrypoint and f['category'] == 'LINKING': pass

                            if not has_printed_header:
                                files_with_errors += 1
                                has_printed_header = True

                            severity_color = Fore.RED if f['severity'] in ['CRITICAL', 'ERROR'] else Fore.YELLOW
                            click.echo(severity_color + f"[{f['severity']}][{f['category']}] {f['message']}")
                            click.echo(Fore.WHITE + f"   > Em '{f['file']}:{f['line']}'")
                            
                            snippet = _get_code_snippet(f['file'], f['line'])
                            if snippet:
                                for lnum, text in snippet.items():
                                    prefix = "      > " if lnum == f['line'] else "        "
                                    l_color = Fore.CYAN if lnum == f['line'] else Fore.WHITE
                                    click.echo(l_color + f"{prefix}{lnum:4}: {text}")
                            
                            logger.add_finding(**f)

            except Exception as e:
                click.echo(Fore.RED + f"[CRASH] Falha ao analisar {v_file}: {e}")

        if files_with_errors == 0:
            click.echo(Fore.GREEN + "\n[OK] Hardware validado com sucesso.")
        else:
            click.echo(Fore.YELLOW + f"\n[FIM] {files_with_errors} arquivos apresentam problemas.")