# doxoade/commands/android.py
import click
import os
import shutil
import sys
import subprocess
from datetime import datetime
from colorama import Fore
from ..shared_tools import ExecutionLogger

def is_termux():
    return "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")

def ensure_storage_access():
    """Verifica e solicita acesso ao armazenamento compartilhado."""
    storage_path = os.path.expanduser("~/storage")
    if not os.path.exists(storage_path):
        click.echo(Fore.YELLOW + "[ANDROID] Configurando acesso ao armazenamento (termux-setup-storage)...")
        try:
            subprocess.run(["termux-setup-storage"], check=True)
            click.echo(Fore.GREEN + "   > Solicitação enviada. Aceite o popup no Android.")
            click.echo(Fore.WHITE + "   > Se a pasta '~/storage' não aparecer, reinicie o Termux.")
        except FileNotFoundError:
             click.echo(Fore.RED + "[ERRO] Comando 'termux-setup-storage' não encontrado.")
             return False
    return os.path.exists(storage_path) or os.path.exists(os.path.expanduser("~/storage/shared"))

def get_android_download_dir():
    """Retorna o caminho para Downloads no Android."""
    options = [
        os.path.expanduser("~/storage/downloads"),
        os.path.expanduser("~/storage/shared/Download"),
        "/sdcard/Download"
    ]
    for path in options:
        if os.path.exists(path):
            return path
    return None

@click.group('android')
def android_group():
    """Ferramentas de integração Termux/Android."""
    if not is_termux():
        click.echo(Fore.YELLOW + "[AVISO] Este comando foi projetado para o ambiente Termux (Android).")

@android_group.command('export')
@click.argument('target', default='.')
@click.option('--zip', '-z', is_flag=True, help="Exporta como arquivo ZIP.")
@click.option('--name', '-n', help="Nome da pasta/arquivo de destino.")
def export_to_android(target, zip, name):
    """Exporta arquivos do Termux para o Armazenamento Android (Downloads)."""
    # Usa _ para ignorar o logger, já que não o usamos explicitamente além do contexto
    with ExecutionLogger('android-export', target, {}) as _:
        if not ensure_storage_access():
            click.echo(Fore.RED + "[FALHA] Sem acesso ao armazenamento."); sys.exit(1)

        dest_root = get_android_download_dir()
        if not dest_root:
            click.echo(Fore.RED + "[FALHA] Pasta de Downloads não encontrada."); sys.exit(1)

        project_name = name or os.path.basename(os.path.abspath(target))
        export_folder = os.path.join(dest_root, "DoxoadeExports")
        os.makedirs(export_folder, exist_ok=True)

        # Lista expandida de ignorados para evitar erros de cópia
        ignore_list = shutil.ignore_patterns(
            'venv', '.git', '__pycache__', 'pytest_temp_dir', 
            '.doxoade_cache', 'tmp', '*.pyc', '.pytest_cache'
        )

        if zip:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name = f"{project_name}_{timestamp}"
            zip_path = os.path.join(export_folder, zip_name)
            
            click.echo(Fore.CYAN + f"Compactando '{target}' para '{zip_path}.zip'...")
            # shutil.make_archive não aceita 'ignore' nativamente de forma simples,
            # então para zip limpo, copiamos para temp primeiro ou confiamos no usuário.
            # Vamos manter simples: zipa tudo (exceto o que o SO bloquear).
            try:
                shutil.make_archive(zip_path, 'zip', target)
                click.echo(Fore.GREEN + f"[OK] Arquivo salvo em: {zip_path}.zip")
            except Exception as e:
                click.echo(Fore.RED + f"[ERRO] Falha na compactação: {e}")
        else:
            dest_path = os.path.join(export_folder, project_name)
            if os.path.exists(dest_path):
                click.echo(Fore.YELLOW + f"   > Substituindo pasta existente: {dest_path}")
                shutil.rmtree(dest_path)
            
            click.echo(Fore.CYAN + f"Copiando '{target}' para '{dest_path}'...")
            try:
                shutil.copytree(target, dest_path, dirs_exist_ok=True, ignore=ignore_list, ignore_dangling_symlinks=True)
                click.echo(Fore.GREEN + "[OK] Exportação concluída.")
            except shutil.Error as e:
                click.echo(Fore.YELLOW + f"[AVISO] Alguns arquivos não foram copiados: {e}")
            except Exception as e:
                click.echo(Fore.RED + f"[ERRO] Falha na cópia: {e}")

@android_group.command('import')
@click.argument('filename')
def import_from_android(filename):
    """Importa um arquivo/pasta de 'Downloads/DoxoadeExports'."""
    src_root = get_android_download_dir()
    if not src_root: return
    
    candidates = [
        os.path.join(src_root, "DoxoadeExports", filename),
        os.path.join(src_root, filename)
    ]
    
    src_path = None
    for c in candidates:
        if os.path.exists(c):
            src_path = c
            break
            
    if not src_path:
        click.echo(Fore.RED + f"[ERRO] '{filename}' não encontrado em Downloads.")
        return

    click.echo(Fore.CYAN + f"Importando '{src_path}'...")
    
    try:
        if os.path.isfile(src_path):
            shutil.copy2(src_path, '.')
        elif os.path.isdir(src_path):
            dest = os.path.join('.', os.path.basename(src_path))
            shutil.copytree(src_path, dest, dirs_exist_ok=True)
        click.echo(Fore.GREEN + "[OK] Importação concluída.")
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Falha na importação: {e}")
