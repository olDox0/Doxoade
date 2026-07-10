#!/usr/bin/env python3
# doxoade/tools/hermes_systems/native/build_auto.py
"""
Hermes Native Decoder - Auto-Build System v2.1
Integra com w64devkit (MinGW-w64) via NexusToolchain.
Sem dependência de MSVC.

Correções v2.1:
- Validação de arquivo fonte antes de compilar
- Detecção de arquivos binários corrompidos
- Limpeza automática de .pyd inválidos
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
        self.native_dir = Path(__file__).resolve().parent
#        self.native_dir = self.root / 'doxoade' / 'tools' / 'hermes_systems' / 'native'
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
    
    def _validate_source_file(self) -> bool:
        """Valida se o arquivo fonte é um C válido (não binário corrompido)."""
        if not self.source_file.exists():
            print(f"  ✘ Arquivo fonte não encontrado: {self.source_file}")
            return False
        
        try:
            content = self.source_file.read_text(encoding='utf-8', errors='strict')
            
            # Verifica se contém código C válido
            if '#include' not in content and 'int main' not in content:
                print(f"  ✘ Arquivo fonte não parece ser C válido")
                return False
            
            # Verifica se não contém bytes nulos (corrupção)
            if '\x00' in content:
                print(f"  ✘ Arquivo fonte contém bytes nulos (corrompido)")
                return False
            
            return True
        except UnicodeDecodeError:
            print(f"  ✘ Arquivo fonte não é texto válido (possivelmente binário)")
            return False
        except Exception as e:
            print(f"  ✘ Erro ao validar arquivo fonte: {e}")
            return False
    
    def _cleanup_corrupted_binary(self):
        """Remove binário corrompido se existir."""
        if self.output_file.exists():
            try:
                # Tenta ler como texto para verificar se é válido
                content = self.output_file.read_text(encoding='utf-8', errors='strict')
                # Se conseguir ler como texto, não é um binário válido
                print(f"  ⚠ Binário existente parece corrompido, removendo...")
                self.output_file.unlink()
            except UnicodeDecodeError:
                # Binário válido (não é texto)
                pass
            except Exception:
                # Não consegue ler, pode estar corrompido
                print(f"  ⚠ Não foi possível validar binário, removendo...")
                self.output_file.unlink()
    
    def needs_rebuild(self) -> bool:
        if not self.output_file.exists():
            return True
        
        # Verifica se o binário está corrompido
        self._cleanup_corrupted_binary()
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
        
        # Valida arquivo fonte antes de compilar
        if not self._validate_source_file():
            return False
        
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
            # '-DMS_WIN64',           # REMOVIDO: causa conflito
            f'-I{include_dir}',       # Headers do Python
            str(self.source_file),
            '-o', str(self.output_file),
        ]
        
        # No Windows, NÃO linkar com libpython (símbolos resolvidos em runtime)
        if os.name != 'nt':
            cmd.extend([f'-L{lib_dir}', f'-l{lib_name}'])
        
        print(f"     Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                print(f"  ✘ Erro na compilação:")
                print(result.stderr)
                return False
            
            # Verifica se o arquivo foi gerado
            if not self.output_file.exists():
                print(f"  ✘ Compilação concluída mas arquivo não gerado")
                return False
            
            # Valida o binário gerado
            try:
                size_kb = self.output_file.stat().st_size / 1024
                print(f"  ✔ Decoder C nativo compilado com sucesso!")
                print(f"     Output: {self.output_file.name} ({size_kb:.1f} KB)")
            except Exception as e:
                print(f"  ✘ Erro ao validar binário gerado: {e}")
                return False
            
            # Atualiza cache
            self._save_cache({
                'source_hash': self._get_source_hash(),
                'build_time': datetime.now().isoformat(),
                'gcc': gcc
            })
            
            return True
            
        except Exception as e:
            print(f"  ✘ Erro crítico na compilação: {e}")
            return False


# API Pública
def ensure_decoder_built(project_root: str) -> bool:
    """Garante que o decoder C nativo está compilado e pronto."""
    builder = HermesNativeBuilder(project_root)
    return builder.build()


if __name__ == '__main__':
    # Teste rápido
    import sys
    project_root = Path(__file__).resolve().parents[4]
    success = ensure_decoder_built(str(project_root))
    sys.exit(0 if success else 1)