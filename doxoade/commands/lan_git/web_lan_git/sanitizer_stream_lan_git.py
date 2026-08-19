# doxoade/commands/lan_git/web_lan_git/sanitizer_stream_lan_git.py
# Streaming de ZIP seguro com exclusão forçada de .env, chaves e venv
""" Módulo Sanitizador de Exportação e Compactação Segura.
Compacta o projeto em memória descartando ativamente segredos, credenciais e lixo binário.

Compactar o repositório em formato `.zip` sem passar segredos para o disco ou alocar a RAM inteira.
    Blacklist Estrita de Arquivos:  Filtra automaticamente `.env`, `.env.*`, `*.pem`, `*.key`, `*.pfx`, `*.pub`, `venv/`, `.venv/`, `__pycache__/`, `.git/credentials`, `.dox_marker`.
    Semáforo de Concorrência:  Limita a 2 downloads simultâneos para não sufocar CPU/RAM do Host. """
    
import os
import io
import zipfile
import fnmatch
import threading
from typing import Set, Tuple, Optional


class ProjectSanitizer:
    """Gera pacotes ZIP sanitizados com controle de concorrência."""

    # Diretórios estritamente proibidos de entrar no ZIP
    FORBIDDEN_DIRS: Set[str] = {
        ".git", ".venv", "venv", "env", "__pycache__",
        ".pytest_cache", ".mypy_cache", ".vscode", ".idea",
        "build", "dist", ".eggs"
    }

    # Padrões de arquivos confidenciais proibidos
    FORBIDDEN_PATTERNS: Tuple[str, ...] = (
        "*.pem", "*.key", "*.pfx", "*.pub", "*.cert", "*.crt",
        ".env", ".env.*", "*.pyc", "*.pyo", "*.pyd",
        ".dox_marker", "id_rsa*", "id_ed25519*", "*.log",
        "*.db", "*.sqlite", "*.sqlite3"
    )

    _download_semaphore = threading.Semaphore(2)  # Máximo de 2 compressões simultâneas

    @classmethod
    def is_safe_path(cls, root_dir: str, current_dir: str, file_name: str) -> bool:
        """Avalia se um arquivo é seguro para exportação pública."""
        rel_dir = os.path.relpath(current_dir, root_dir)
        dir_parts = set(rel_dir.replace("\\", "/").split("/"))

        # 1. Verifica se está dentro de uma pasta proibida
        if any(f_dir in dir_parts for f_dir in cls.FORBIDDEN_DIRS):
            return False

        # 2. Verifica se o nome do arquivo bate com padrão de segredo
        for pattern in cls.FORBIDDEN_PATTERNS:
            if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
                return False

        return True

    @classmethod
    def build_sanitized_zip_buffer(cls, project_root: str) -> Tuple[bool, Optional[io.BytesIO], Optional[str]]:
        """
        Gera um arquivo ZIP em memória sanitizado.
        Usa semáforo para evitar exaustão de CPU/RAM no Host.
        """
        if not cls._download_semaphore.acquire(blocking=False):
            return False, None, "Servidor ocupado com outras transferências. Tente em instantes."

        try:
            project_root = os.path.abspath(project_root)
            buffer = io.BytesIO()

            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(project_root):
                    # Modifica dirs in-place para não descer em pastas proibidas
                    dirs[:] = [d for d in dirs if d not in cls.FORBIDDEN_DIRS]

                    for file in files:
                        if cls.is_safe_path(project_root, root, file):
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, project_root)
                            zf.write(full_path, arcname=rel_path)

            buffer.seek(0)
            return True, buffer, None
        except Exception as e:
            return False, None, f"Erro ao gerar pacote ZIP: {e}"
        finally:
            cls._download_semaphore.release()