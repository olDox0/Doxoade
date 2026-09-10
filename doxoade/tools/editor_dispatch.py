# -*- coding: utf-8 -*-
# doxoade/tools/editor_dispatch.py
"""
🧭 Despachante Universal de Editores do Doxoade (Sovereign Editor Gateway).
Centraliza o roteamento de abertura de arquivos e salto de coordenadas forenses.
Prioridade:
  1. Doxly / Lite XL (Instância viva via IPC ou lançamento novo com foco).
  2. Notepad++ (Fallback secundário com -n<linha>).
  3. Editor padrão do Sistema Operacional.
Compliance: ProDeNov 1.2.1 (Planos A, B e C), PASC-8.13.
"""
from __future__ import annotations
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import List, Union, Optional, Tuple

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        CYAN = GREEN = YELLOW = RED = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = RESET_ALL = ""

try:
    from doxoade.commands.lite_xl_systems.lite_xl_process import LiteXLProcess
    from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
    LITEXL_AVAILABLE = True
except ImportError:
    LITEXL_AVAILABLE = False


class EditorDispatcher:
    """Roteador industrial e fail-safe de editores para o Doxoade."""

    NPP_CANDIDATES = [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
        "notepad++.exe",
        "notepad++",
    ]

    # =========================================================================
    # 🔍 DETECTORES DE BINÁRIOS
    # =========================================================================
    @classmethod
    def find_notepadpp(cls) -> Optional[str]:
        """Localiza o binário do Notepad++ no PATH ou diretórios conhecidos."""
        for candidate in cls.NPP_CANDIDATES:
            if shutil.which(candidate) or (os.name == "nt" and os.path.exists(candidate)):
                return candidate
        return None

    @classmethod
    def find_doxly(cls) -> Optional[Path]:
        """Localiza o executável do Doxly / Lite XL."""
        if not LITEXL_AVAILABLE:
            return None
        return LiteXLProcess.find_executable()

    # =========================================================================
    # 🚀 PLANO A: DOXLY / LITE XL (IPC & COORDENADAS)
    # =========================================================================
    @classmethod
    def _open_doxly_at_line(cls, file_path: Path, line: int = 1, col: int = 1) -> bool:
        """Abre arquivo no Doxly posicionando na linha informada."""
        if not LITEXL_AVAILABLE:
            return False

        resolved = str(file_path.resolve())
        target_payload = f"{resolved}:{line}:{col}" if col > 1 else f"{resolved}:{line}"

        # Se o Lite XL já estiver rodando, envia via IPC e foca a janela
        if LiteXLProcess.is_process_alive():
            ok, _ = LiteXLProcess.send_to_running_instance(target_payload)
            if ok:
                return True

        # Se não estiver rodando, lança o executável e enfileira o salto no IPC
        exe = cls.find_doxly()
        if not exe:
            return False

        try:
            CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
            # Lança apontando para o arquivo
            subprocess.Popen(
                [str(exe), resolved],
                creationflags=CREATE_NEW_CONSOLE,
                close_fds=(sys.platform != "win32")
            )
            # Enfileira a coordenada no IPC para posicionar assim que o boot terminar
            if line > 1:
                time.sleep(0.4)
                ipc_queue = LiteXLPaths.get_ipc_queue_path()
                ipc_queue.parent.mkdir(parents=True, exist_ok=True)
                with open(ipc_queue, "a", encoding="utf-8") as f:
                    f.write(f"{resolved}:{line}\n")

            return True
        except Exception:
            return False

    @classmethod
    def _open_doxly_batch(cls, files: List[Path]) -> bool:
        """Abre múltiplos arquivos no Doxly em abas."""
        if not LITEXL_AVAILABLE:
            return False

        # Se o processo estiver vivo, envia todos via IPC
        if LiteXLProcess.is_process_alive():
            ipc_queue = LiteXLPaths.get_ipc_queue_path()
            ipc_queue.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(ipc_queue, "a", encoding="utf-8") as f:
                    for f_path in files:
                        resolved = str(f_path.resolve())
                        f.write(f"{resolved}\n")
                LiteXLProcess.focus_running_window()
                return True
            except Exception:
                pass

        # Se não estiver vivo, lança o processo abrindo todos os arquivos como argumentos
        exe = cls.find_doxly()
        if not exe:
            return False

        try:
            CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
            args = [str(exe)] + [str(f.resolve()) for f in files]
            subprocess.Popen(
                args,
                creationflags=CREATE_NEW_CONSOLE,
                close_fds=(sys.platform != "win32")
            )
            return True
        except Exception:
            return False

    # =========================================================================
    # 🛡️ PLANO B: NOTEPAD++ (FALLBACK COM -n<linha>)
    # =========================================================================
    @classmethod
    def _open_npp_at_line(cls, file_path: Path, line: int = 1) -> bool:
        npp = cls.find_notepadpp()
        if not npp:
            return False
        try:
            subprocess.Popen(
                [npp, f"-n{line}", "-nosession", str(file_path.resolve())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    @classmethod
    def _open_npp_batch(cls, files: List[Path]) -> bool:
        npp = cls.find_notepadpp()
        if not npp:
            return False
        try:
            args = [npp, "-nosession"] + [str(f.resolve()) for f in files]
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    # =========================================================================
    # 📦 PLANO C: FALLBACK DO SISTEMA OPERACIONAL
    # =========================================================================
    @classmethod
    def _open_os_fallback(cls, target: Union[Path, List[Path]]) -> bool:
        targets = [target] if isinstance(target, Path) else target
        try:
            for t in targets:
                if sys.platform == "win32":
                    os.startfile(str(t.resolve()))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(t.resolve())])
                else:
                    subprocess.Popen(["xdg-open", str(t.resolve())])
            return True
        except Exception:
            return False

    # =========================================================================
    # 🌐 MÉTODOS PÚBLICOS DE ALTO NÍVEL
    # =========================================================================
    @classmethod
    def open_at_line(
        cls,
        file_path: Union[str, Path],
        line: int = 1,
        col: int = 1,
        prefer_npp: bool = False
    ) -> bool:
        """
        Abre o arquivo na coordenada exata (linha/coluna).
        Utilizado principalmente pelo motor de resgate Sotéria.
        """
        p = Path(file_path).resolve()
        if not p.exists():
            return False

        # 1. Notepad++ se explicitamente solicitado
        if prefer_npp:
            if cls._open_npp_at_line(p, line):
                return True

        # 2. Plano A: Doxly / Lite XL com salto de linha
        if cls._open_doxly_at_line(p, line, col):
            return True

        # 3. Plano B: Notepad++ como fallback automático
        if cls._open_npp_at_line(p, line):
            return True

        # 4. Plano C: Editor do SO
        return cls._open_os_fallback(p)

    @classmethod
    def open_files(
        cls,
        files: List[Union[str, Path]],
        prefer_npp: bool = False
    ) -> Tuple[bool, str]:
        """
        Abre lote de arquivos em abas.
        Utilizado pelos comandos `mk --up` e `init --up`.
        Retorna (sucesso, nome_do_editor_utilizado).
        """
        valid_files = [Path(f).resolve() for f in files if Path(f).is_file()]
        if not valid_files:
            return False, "nenhum arquivo válido"

        # 1. Notepad++ se explicitamente solicitado
        if prefer_npp:
            if cls._open_npp_batch(valid_files):
                return True, "Notepad++"

        # 2. Plano A: Doxly / Lite XL (Abas via IPC ou Processo Novo)
        if cls._open_doxly_batch(valid_files):
            return True, "Doxly (Lite XL)"

        # 3. Plano B: Notepad++ como fallback
        if cls._open_npp_batch(valid_files):
            return True, "Notepad++"

        # 4. Plano C: Sistema Operacional
        if cls._open_os_fallback(valid_files):
            return True, "Editor do Sistema"

        return False, "falha ao disparar editores"
