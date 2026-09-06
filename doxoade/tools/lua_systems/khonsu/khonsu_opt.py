# doxoade/tools/lua_systems/khonsu/khonsu_opt.py
# -*- coding: utf-8 -*-
"""
🌙 KHONSU OPT ENGINE — Otimizador Léxico, Minificador e Compilador AOT de Bytecode (V2.2 POSIX).
Com Self-Validation Gate e Gravação Binária Atômica ('wb') imune a erros de escape do Windows.
"""
from __future__ import annotations
import os
import re
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        GREEN = YELLOW = RED = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = RESET_ALL = ""

class KhonsuOptimizer:
    """🌙 Motor de Otimização e Compilação de Código Lua com Auto-Validação."""
    _LUA_LITERALS_PATTERN = re.compile(
        r"--\[(=*)\[.*?\]\1\]|"  
        r"--[^\r\n]*|"           
        r"\[(=*)\[.*?\]\2\]|"    
        r'"(?:\\.|[^"\\])*"|'   
        r"'(?:\\.|[^'\\])*'",    
        re.DOTALL
    )

    @classmethod
    def minify_lua_source(cls, source: str) -> str:
        """[PLANO B] Minificação léxica segura preservando strings literais."""
        def _replacer(match: re.Match) -> str:
            token = match.group(0)
            if token.startswith("--"):
                return " "
            return token
        stripped = cls._LUA_LITERALS_PATTERN.sub(_replacer, source)
        cleaned_lines = [l.strip() for l in stripped.splitlines() if l.strip()]
        return "\n".join(cleaned_lines)

    @classmethod
    def compile_to_bytecode(cls, lua_source: str) -> Tuple[bool, Union[bytes, str], Dict[str, Any]]:
        """
        [PLANO A] Compila para Bytecode Nativo Lua 5.4 gravado diretamente em modo binário ('wb').
        Executa Self-Validation Gate antes de retornar com caminhos POSIX.
        """
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
        runtime_info = LiteXLEngine.lua_runtime_info()
        if not runtime_info:
            lua_path_str = LiteXLEngine.ensure_lua_runtime()
            if lua_path_str:
                runtime_info = (Path(lua_path_str), "Lua 5.4")
            else:
                return False, "Runtime Lua não disponível para compilação AOT", {}

        lua_exe, _ = runtime_info

        with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False, encoding="utf-8") as src_tmp:
            src_tmp.write(lua_source)
            src_tmp_path = Path(src_tmp.name)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".luac", delete=False) as out_tmp:
            out_bin_path = Path(out_tmp.name)

        posix_src = src_tmp_path.as_posix()
        posix_out = out_bin_path.as_posix()

        compiler_lua_script = f"""
local f_in = io.open("{posix_src}", "r")
if not f_in then os.exit(1) end
local content = f_in:read("*a")
f_in:close()
local chunk, err = load(content, "=(khonsu_aot)")
if not chunk then
  io.stderr:write("COMPILATION_ERROR: " .. tostring(err))
  os.exit(2)
end
local bytecode = string.dump(chunk, true)
local f_out = io.open("{posix_out}", "wb")
if not f_out then os.exit(3) end
f_out:write(bytecode)
f_out:flush()
f_out:close()
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False, encoding="utf-8") as script_tmp:
            script_tmp.write(compiler_lua_script)
            script_tmp_path = Path(script_tmp.name)

        try:
            proc = subprocess.run(
                [str(lua_exe), str(script_tmp_path)],
                capture_output=True,
                timeout=10,
                text=True
            )
            if proc.returncode == 0 and out_bin_path.exists() and out_bin_path.stat().st_size > 0:
                bytecode = out_bin_path.read_bytes()
                verify_proc = subprocess.run(
                    [str(lua_exe), "-e", f'local f, err = loadfile("{posix_out}"); if not f then io.stderr:write(tostring(err)); os.exit(1) end'],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                if verify_proc.returncode != 0:
                    err_laudo = verify_proc.stderr.strip()
                    return False, f"Bytecode falhou no Self-Validation Gate: {err_laudo}", {}

                orig_len = len(lua_source.encode("utf-8"))
                opt_len = len(bytecode)
                ratio = round((1.0 - (opt_len / max(1, orig_len))) * 100, 1)
                metrics = {
                    "mode": "AOT_BYTECODE_STRIPPED",
                    "original_bytes": orig_len,
                    "optimized_bytes": opt_len,
                    "compression_ratio_pct": ratio,
                    "is_binary": True,
                    "validation": "PASS_SELF_GATE"
                }
                return True, bytecode, metrics
            else:
                err_msg = proc.stderr.strip()
                return False, f"Falha na compilação AOT: {err_msg}", {}
        except Exception as e:
            return False, f"Exceção durante compilação: {e}", {}
        finally:
            if src_tmp_path.exists(): src_tmp_path.unlink()
            if script_tmp_path.exists(): script_tmp_path.unlink()
            if out_bin_path.exists(): out_bin_path.unlink()

    @classmethod
    def optimize(cls, lua_source: str, force_text: bool = False) -> Tuple[Union[bytes, str], Dict[str, Any]]:
        """Pipeline de Otimização Transparente com Fallback Automático."""
        orig_bytes = len(lua_source.encode("utf-8"))
        if not force_text:
            ok, bytecode, metrics = cls.compile_to_bytecode(lua_source)
            if ok and isinstance(bytecode, bytes):
                return bytecode, metrics
            else:
                print(f"  {Fore.YELLOW}⚠ [KHONSU GATE] Bytecode recusado: {bytecode}. Acionando Plano B (Minificação).{Fore.RESET}")
        try:
            minified_text = cls.minify_lua_source(lua_source)
            opt_bytes = len(minified_text.encode("utf-8"))
            ratio = round((1.0 - (opt_bytes / max(1, orig_bytes))) * 100, 1)
            return minified_text, {
                "mode": "MINIFIED_TEXT",
                "original_bytes": orig_bytes,
                "optimized_bytes": opt_bytes,
                "compression_ratio_pct": ratio,
                "is_binary": False,
                "validation": "PASS_MINIFIED"
            }
        except Exception:
            return lua_source, {
                "mode": "SAFE_PASS_THROUGH",
                "original_bytes": orig_bytes,
                "optimized_bytes": orig_bytes,
                "compression_ratio_pct": 0.0,
                "is_binary": False,
                "validation": "SAFE_FALLBACK"
            }
