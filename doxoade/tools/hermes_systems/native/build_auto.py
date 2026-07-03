#!/usr/bin/env python3
# doxoade/tools/hermes_systems/native/build_auto.py
"""
Hermes Native Decoder - Auto-Build System
Integra com w64devkit (MinGW-w64) via NexusToolchain.
Sem dependência de MSVC.
"""
import os
import sys
import json
import hashlib
import subprocess
import sysconfig
from pathlib import Path
from datetime import datetime


class HermesNativeBuilder:
    """Builder automático do decoder C nativo via w64devkit."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.native_dir = self.root / 'doxoade' / 'tools' / 'hermes_systems' / 'native'
        self.source_file = self.native_dir / 'hermes_decoder.c'
        self.cache_file = self.native_dir / '.build_cache.json'
        self.output_ext = '.pyd' if os.name == 'nt' else '.so'
        self.output_file = self.native_dir / f'hermes_decoder{self.output_ext}'
        
    def _get_source_hash(self) -> str:
        if not self.source_file.exists():
            return ''
        return hashlib.sha256(self.source_file.read_bytes()).hexdigest()
    
    def _load_cache(self) -> dict:
        if not self.cache_file.exists():
            return {}
        try:
            return json.loads(self.cache_file.read_text())
        except Exception:
            return {}
    
    def _save_cache(self, cache: dict):
        self.cache_file.write_text(json.dumps(cache, indent=2))
    
    def needs_rebuild(self) -> bool:
        if not self.output_file.exists():
            return True
        cache = self._load_cache()
        return self._get_source_hash() != cache.get('source_hash', '')
    
    def _detect_gcc(self) -> str:
        """Detecta GCC via NexusToolchain ou fallback."""
        try:
            from doxoade.tools.metalcraft.metal_toolchain import NexusToolchain
            tc = NexusToolchain()
            if tc.detect():
                return tc.compiler_path
        except Exception:
            pass
        
        # Fallback: gcc no PATH
        import shutil
        gcc = shutil.which('gcc')
        if gcc:
            return gcc
        return None
    
    def _get_python_paths(self):
        """Retorna (include_dir, lib_dir, lib_name) para o Python atual."""
        include_dir = sysconfig.get_path('include')
        
        # No Windows, libs ficam em libs/ do prefix
        prefix = sys.prefix
        if os.name == 'nt':
            lib_dir = Path(prefix) / 'libs'
            # python3X.lib (MSVC) ou libpython3X.dll.a (MinGW)
            version = f"{sys.version_info.major}{sys.version_info.minor}"
            
            # Tenta achar lib do MinGW primeiro
            mingw_lib = lib_dir / f'libpython{version}.dll.a'
            if mingw_lib.exists():
                return include_dir, str(lib_dir), f'python{version}'
            
            # Fallback para MSVC .lib (MinGW também consegue linkar)
            msvc_lib = lib_dir / f'python{version}.lib'
            if msvc_lib.exists():
                return include_dir, str(lib_dir), f'python{version}'
            
            return include_dir, str(lib_dir), f'python{version}'
        else:
            ldlib = sysconfig.get_config_var('LDLIBRARY') or ''
            lib_dir = sysconfig.get_config_var('LIBDIR') or ''
            lib_name = sysconfig.get_config_var('LDLIBRARY') or 'python'
            if lib_name.startswith('lib'):
                lib_name = lib_name[3:]
            if lib_name.endswith('.so'):
                lib_name = lib_name[:-3]
            return include_dir, lib_dir, lib_name
    
    def build(self, use_metalcraft: bool = False) -> bool:
        """Build principal via GCC direto (w64devkit)."""
        return self.build_with_gcc()

    def build_with_gcc(self) -> bool:
        """Compila diretamente com GCC do w64devkit."""
        if not self.needs_rebuild():
            print(f"  ✔ Decoder C já compilado (cache hit)")
            return True
        
        gcc = self._detect_gcc()
        if not gcc:
            print(f"  ✘ GCC não encontrado. Instale w64devkit.")
            return False
        
        print(f"  🔨 [Native] Compilando via w64devkit (N2808 baseline)...")
        print(f"     GCC: {gcc}")
        
        include_dir, lib_dir, lib_name = self._get_python_paths()
        
        # ═══════════════════════════════════════════════════════════════════
        # Flags otimizados para Silvermont (N2808)
        # CORREÇÃO CRÍTICA:
        #   1. Removido -DMS_WIN64 (causa conflito com headers MinGW)
        #   2. No Windows, NÃO linkar com libpython (símbolos resolvidos em runtime)
        # ═══════════════════════════════════════════════════════════════════
        cmd = [
            gcc,
            '-O2',                    # Otimização balanceada
            '-shared',                # Biblioteca compartilhada
            '-static-libgcc',         # Linka libgcc estaticamente
            '-fPIC',                  # Position-independent code
            # '-DMS_WIN64',          # ❌ REMOVIDO: causa conflito __gnuc_va_list
            '-march=westmere',        # Baseline Silvermont
            '-msse4.2',               # SSE 4.2 (STTNI para strings)
            f'-I{include_dir}',       # Headers do Python
            str(self.source_file),
            '-o', str(self.output_file),
        ]
        
        # ═══════════════════════════════════════════════════════════════════
        # CORREÇÃO CRÍTICA: Linkagem do Python
        # GCC/MinGW (diferente de MSVC) precisa da import library em tempo
        # de link para gerar os thunks __imp_Py* — sem isso o linker falha
        # com "undefined reference to __imp_PyXxx" mesmo que os símbolos
        # existam em python3XX.dll em runtime. Necessário em TODAS as
        # plataformas quando o compilador é GCC.
        # ═══════════════════════════════════════════════════════════════════
        if lib_dir:
            cmd.append(f'-L{lib_dir}')
            cmd.append(f'-l{lib_name}')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                print(f"  ✘ Falha na compilação:")
                stderr_lines = result.stderr.strip().split('\n')
                for line in stderr_lines[-15:]:
                    print(f"     {line}")
                return False
            
            if not self.output_file.exists():
                print(f"  ✘ Compilação concluída mas arquivo não gerado")
                return False
            
            # Atualiza cache
            cache = {
                'source_hash': self._get_source_hash(),
                'build_time': datetime.now().isoformat(),
                'output_size': self.output_file.stat().st_size,
                'compiler': gcc,
            }
            self._save_cache(cache)
            
            size_kb = self.output_file.stat().st_size / 1024
            print(f"  ✔ Compilação bem-sucedida!")
            print(f"     Output: {self.output_file.name} ({size_kb:.1f} KB)")
            return True
            
        except subprocess.TimeoutExpired:
            print(f"  ✘ Timeout na compilação (>60s)")
            return False
        except Exception as e:
            print(f"  ✘ Erro: {e}")
            return False

def ensure_decoder_built(project_root: str) -> bool:
    """Garante que o decoder C está compilado."""
    builder = HermesNativeBuilder(project_root)
    return builder.build()


if __name__ == '__main__':
    project_root = Path.cwd().resolve()
    print(f"\n🔨 Hermes Native Decoder - Auto-Build\n")
    
    builder = HermesNativeBuilder(str(project_root))
    success = builder.build()
    
    if success:
        print(f"\n✔ Decoder pronto para uso!")
    else:
        print(f"\n✘ Falha na compilação")
        sys.exit(1)