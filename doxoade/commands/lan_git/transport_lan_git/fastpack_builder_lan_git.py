# doxoade\commands\lan_git\transport_lan_git\fastpack_builder_lan_git.py
""" Módulo Construtor de FastPack Soberano via Zipapp Nativo (.pyz).
Gera um executável Python autocontido, comprimido e 100% offline. """

import os
import sys
import io
import time
import shutil
import hashlib
import zipfile
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Dict, List

from doxoade.commands.lan_git.web_lan_git.sanitizer_stream_lan_git import ProjectSanitizer


# Código que será injetado como __main__.py dentro do Zipapp
ZIPAPP_MAIN_SCRIPT = '''# -*- coding: utf-8 -*-
"""
================================================================================
⚡ DOXOADE SOVEREIGN FASTPACK - EXECUTOR NATIVO ZIPAPP
================================================================================
"""

import os
import sys
import io
import time
import shutil
import zipfile
import subprocess
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
if os.name == 'nt':
    os.system('')

class UI:
    CYAN    = '\\033[1;36m'
    GREEN   = '\\033[1;32m'
    YELLOW  = '\\033[1;33m'
    RED     = '\\033[1;31m'
    MAGENTA = '\\033[1;35m'
    BOLD    = '\\033[1m'
    DIM     = '\\033[2m'
    RESET   = '\\033[0m'

def main():
    print(f"\\n{UI.CYAN}{UI.BOLD}{'='*68}")
    print(f" ⚡ INSTALADOR FASTPACK OFFLINE - DOXOADE")
    print(f"{'='*68}{UI.RESET}")
    
    target_dir = Path.cwd()
    app_archive = sys.argv[0]

    # 1. Extração do conteúdo do Zipapp para o diretório atual
    print(f"\\n{UI.MAGENTA}[1/4]{{UI.RESET}} {{UI.BOLD}}Extraindo Árvore de Projeto e Wheels Locais...{{UI.RESET}}")
    try:
        with zipfile.ZipFile(app_archive, 'r') as zf:
            for member in zf.infolist():
                if member.filename not in ("__main__.py", "__main__.pyc"):
                    zf.extract(member, target_dir)
        print(f"  {UI.GREEN}✔{{UI.RESET}} Código-fonte e dependências extraídos com sucesso.")
    except Exception as e:
        print(f"  {UI.RED}✘ Falha na extração do pacote: {e}{{UI.RESET}}")
        sys.exit(1)

    # 2. Criação do Ambiente Virtual Isolado
    print(f"\\n{UI.MAGENTA}[2/4]{{UI.RESET}} {{UI.BOLD}}Configurando Ambiente Virtual (venv)...{{UI.RESET}}")
    venv_dir = target_dir / "venv"
    if not venv_dir.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print(f"  {UI.GREEN}✔{{UI.RESET}} Ambiente virtual criado.")
    else:
        print(f"  {UI.GREEN}✔{{UI.RESET}} Ambiente virtual existente reaproveitado.")

    # 3. Resolução dos Executáveis
    if os.name == "nt":
        py_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
        activate_cmd = "call venv\\\\Scripts\\\\activate.bat"
    else:
        py_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
        activate_cmd = "source venv/bin/activate"

    # 4. Instalação Offline via Wheelhouse Local
    print(f"\\n{UI.MAGENTA}[3/4]{{UI.RESET}} {{UI.BOLD}}Instalando Pacotes Locais (Zero Internet)...{{UI.RESET}}")
    wheelhouse_dir = target_dir / "_fastpack_whl"
    
    t0 = time.time()
    try:
        cmd = [
            str(py_exe), "-m", "pip", "install",
            "--no-index",
            "--no-build-isolation",
            f"--find-links={str(wheelhouse_dir)}",
            "-e", str(target_dir)
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        dur = time.time() - t0
        print(f"  {UI.GREEN}✔{{UI.RESET}} Dependências instaladas em {{UI.BOLD}}{{dur:.2f}}s{{UI.RESET}}!")
    except subprocess.CalledProcessError as e:
        print(f"  {UI.YELLOW}⚠ Instalação básica concluída (Requer setup_install para dependências extras).{{UI.RESET}}")

    # 5. Limpeza
    print(f"\\n{UI.MAGENTA}[4/4]{{UI.RESET}} {{UI.BOLD}}Finalizando e Limpando Caches Temporários...{{UI.RESET}}")
    if wheelhouse_dir.exists():
        try:
            shutil.rmtree(wheelhouse_dir)
        except Exception:
            pass
    print(f"  {{UI.GREEN}}✔{{UI.RESET}} Ambiente higienizado e pronto.")

    # Conclusão
    print(f"\\n{{UI.CYAN}}{{UI.BOLD}}{{'='*68}}")
    print(f" 🚀 INSTALAÇÃO OFFLINE CONCLUÍDA COM SUCESSO!")
    print(f"{'='*68}{UI.RESET}")
    print(f"\\n{{UI.GREEN}}{{UI.BOLD}}Para ativar o ambiente e usar o Doxoade:{{UI.RESET}}")
    print(f"  {{UI.CYAN}}{{UI.BOLD}}{{activate_cmd}}{{UI.RESET}}\\n")

if __name__ == '__main__':
    main()
'''


class FastpackBuilder:
    """Orquestrador de geração e cacheamento de Zipapps Soberanos."""

    @classmethod
    def get_cache_signature(cls, repo_path: str) -> str:
        repo_path = os.path.abspath(repo_path)
        sig_data = []

        try:
            res = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5, check=False
            )
            sig_data.append(res.stdout.strip() if res.returncode == 0 else "no_git")
        except Exception:
            sig_data.append("no_git")

        try:
            res = subprocess.run(
                ["git", "-C", repo_path, "status", "--porcelain"],
                capture_output=True, text=True, timeout=5, check=False
            )
            sig_data.append(res.stdout.strip())
        except Exception:
            pass

        for filename in ("pyproject.toml", "requirements.txt", "setup.py"):
            fpath = os.path.join(repo_path, filename)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "rb") as f:
                        sig_data.append(hashlib.sha256(f.read()).hexdigest())
                except Exception:
                    pass

        return hashlib.sha256("_".join(sig_data).encode("utf-8")).hexdigest()[:16]

    @classmethod
    def get_or_build_fastpack_path(cls, repo_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Retorna o caminho físico do arquivo cached Zipapp (.pyz)."""
        repo_path = os.path.abspath(repo_path)
        cache_dir = os.path.join(repo_path, ".doxoade", "cache", "fastpack")
        os.makedirs(cache_dir, exist_ok=True)

        sig = cls.get_cache_signature(repo_path)
        cached_file = os.path.join(cache_dir, f"doxoade_fastpack_{sig}.pyz")

        if os.path.exists(cached_file) and os.path.getsize(cached_file) > 1024:
            return True, cached_file, None

        ok, err = cls._build_fresh_zipapp(repo_path, cached_file)
        if not ok:
            return False, None, err

        return True, cached_file, None

    @classmethod
    def get_or_build_fastpack(cls, repo_path: str) -> Tuple[bool, Optional[bytes], Optional[str]]:
        ok, path, err = cls.get_or_build_fastpack_path(repo_path)
        if not ok or not path:
            return False, None, err
        try:
            with open(path, "rb") as f:
                return True, f.read(), None
        except Exception as e:
            return False, None, str(e)

    @classmethod
    def _build_fresh_zipapp(cls, repo_path: str, output_pyz_path: str) -> Tuple[bool, Optional[str]]:
        """Forja o arquivo .pyz diretamente em disco."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            wheelhouse_tmp = os.path.join(tmp_dir, "_fastpack_whl")
            os.makedirs(wheelhouse_tmp, exist_ok=True)

            # 1. Coleta os .whl locais
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "wheel", repo_path, "-w", wheelhouse_tmp, "--no-build-isolation"],
                    capture_output=True, timeout=120, check=False
                )
            except Exception:
                pass

            # 2. Constrói o container Zipapp
            try:
                with open(output_pyz_path, "wb") as f_out:
                    # Shebang executável opcional para compatibilidade
                    f_out.write(b"#!/usr/bin/env python3\n")
                    
                    with zipfile.ZipFile(f_out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                        # Injeta o __main__.py do Zipapp
                        zf.writestr("__main__.py", ZIPAPP_MAIN_SCRIPT.encode("utf-8"))

                        # Injeta o código do projeto sanitizado
                        for root, dirs, files in os.walk(repo_path):
                            dirs[:] = [d for d in dirs if d not in ProjectSanitizer.FORBIDDEN_DIRS]
                            for file in files:
                                if ProjectSanitizer.is_safe_path(repo_path, root, file):
                                    full_path = os.path.join(root, file)
                                    rel_path = os.path.relpath(full_path, repo_path)
                                    zf.write(full_path, arcname=rel_path)

                        # Injeta todos os .whl
                        for whl_file in os.listdir(wheelhouse_tmp):
                            if whl_file.endswith(".whl"):
                                full_whl = os.path.join(wheelhouse_tmp, whl_file)
                                zf.write(full_whl, arcname=f"_fastpack_whl/{whl_file}")

                return True, None
            except Exception as e:
                return False, f"Falha ao empacotar Zipapp: {e}"