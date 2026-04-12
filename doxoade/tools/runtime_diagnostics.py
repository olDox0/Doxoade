# doxoade/tools/runtime_diagnostics.py
from __future__ import annotations

import os
import ctypes
from contextlib import contextmanager
from pathlib import Path

class DxoadeNativeLoadError(RuntimeError):
    pass

@contextmanager
def hook_ctypes_cdll(script_path: str):
    real_cdll = ctypes.CDLL
    seen_paths: list[str] = []

    def wrapped_cdll(name, *args, **kwargs):
        path = os.fspath(name) if isinstance(name, (str, os.PathLike)) else str(name)
        seen_paths.append(path)

        if isinstance(path, str) and path.lower().endswith((".dll", ".so", ".dylib")):
            if os.path.isabs(path) and not os.path.exists(path):
                raise DxoadeNativeLoadError(
                    f"DLL não encontrada: {path}\n"
                    f"Script: {script_path}\n"
                    f"Verifique se o caminho foi montado corretamente."
                )

        try:
            return real_cdll(name, *args, **kwargs)
        except FileNotFoundError as e:
            raise DxoadeNativeLoadError(
                f"Falha ao carregar DLL: {path}\n"
                f"Possível causa: caminho errado ou dependência ausente.\n"
                f"Erro original: {e}"
            ) from e
        except OSError as e:
            raise DxoadeNativeLoadError(
                f"DLL encontrada, mas não carregou: {path}\n"
                f"Possível causa: dependência nativa ausente (runtime C/C++).\n"
                f"Erro original: {e}"
            ) from e

    ctypes.CDLL = wrapped_cdll
    try:
        yield
    finally:
        ctypes.CDLL = real_cdll

    unique = list(dict.fromkeys(seen_paths))
    if len(unique) > 1:
        print("[Doxoade] Aviso: múltiplos carregamentos de DLL detectados:")
        for p in unique:
            print("  -", p)