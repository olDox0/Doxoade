#!/usr/bin/env python3
# doxoade/tools/hermes_systems/native/hermes_bridge_builder.py
"""
Hermes v2 Bridge - Auto-Build System (Metalcraft Integrated)
============================================================
Compila o motor nativo do Hermes (Dual-Dictionary + Branchless SSE 4.2).
Integra-se ao NexusToolchain do Metalcraft para detecção de GCC.

Lógica de Build Orientado a Eventos:
  1. Se o binário (.pyd/.so) não existe -> Build.
  2. Se o hash dos fontes (.c) mudou -> Build.
  3. Caso contrário -> Cache Hit (Zero CPU gasto).
"""
import os
import sys
import json
import hashlib
import subprocess
import sysconfig
from pathlib import Path

class HermesBridgeBuilder:
    """Builder automático do Hermes v2 Nativo via Metalcraft."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        #self.native_dir = self.root / 'doxoade' / 'tools' / 'hermes_systems' / 'native'
        self.native_dir = Path(__file__).resolve().parent
        # Fontes do Hermes v2 (Dual-Dictionary Architecture)
        self.source_files = [
            self.native_dir / 'hermes_py_utils.c',      # O Roteador & API (Substitui o py_bridge)
            self.native_dir / 'hermes_cache.c',         # O Motor de Cache L1/L2 (NOVO)
            self.native_dir / 'hermes_hbc5_parser.c',   # O Parser HBC5
            self.native_dir / 'hermes_hbc6_patches.c',  # O Walker DFS HBC6
        ]
        
        self.cache_file = self.native_dir / '.bridge_build_cache.json'
        self.output_ext = '.pyd' if os.name == 'nt' else '.so'
        self.output_file = self.native_dir / f'hermes_bridge{self.output_ext}'
        
    def _get_sources_hash(self) -> str:
        """Gera um hash SHA-256 único para o conjunto de fontes C."""
        hasher = hashlib.sha256()
        for src in self.source_files:
            if src.exists():
                hasher.update(src.read_bytes())
        return hasher.hexdigest()
        
    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text())
            except Exception:
                return {}
        return {}
        
    def _save_cache(self, cache: dict):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(cache, indent=2))
        
    def needs_rebuild(self) -> bool:
        """Verifica se o build é necessário (Evento de Mudança ou Ausência)."""
        if not self.output_file.exists():
            return True
        cache = self._load_cache()
        return self._get_sources_hash() != cache.get('sources_hash', '')

    def build(self) -> bool:
        """Orquestra a compilação usando o Metalcraft."""
        if not self.needs_rebuild():
            print(f"  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).")
            return True
            
        # 1. INTEGRAÇÃO COM METALCRAFT (NexusToolchain)
        try:
            from doxoade.tools.metalcraft.metal_toolchain import NexusToolchain
            tc = NexusToolchain()
            if not tc.detect():
                print(f"  ✘ [HERMES v2] GCC não encontrado (Metalcraft falhou).")
                return False
            gcc = tc.compiler_path
        except ImportError:
            # Fallback de emergência caso o Metalcraft não esteja no path
            import shutil
            gcc = shutil.which('gcc')
            if not gcc:
                print(f"  ✘ [HERMES v2] GCC não encontrado no PATH.")
                return False

        print(f"  🔨 [HERMES v2] Compilando Bridge Nativo (Dual-Dictionary + SSE 4.2)...")
        print(f"     GCC: {gcc}")
        
        include_dir = sysconfig.get_path('include')
        
        # 2. MONTAGEM DO COMANDO (Otimizado para Celeron N2808 / Silvermont)
        cmd = [
            gcc,
            '-O3',                    # Otimização máxima
            '-shared',                # Biblioteca compartilhada (.pyd/.so)
            '-static-libgcc',         # Linka libgcc estaticamente (portabilidade)
            '-fPIC',                  # Position-independent code
            '-msse4.2',               # Habilita SSE 4.2 (STTNI para strings)
            '-mpopcnt',               # Population count (para bitmaps O(1))
            '-funroll-loops',         # Desrola loops para o branchless decoder
            '-march=native',          # Otimiza para a CPU atual
            f'-I{include_dir}',       # Headers da C-API do Python
        ]
        
        # Adiciona os arquivos fonte
        cmd.extend([str(src) for src in self.source_files if src.exists()])
        
        # ═══════════════════════════════════════════════════════════════════
        # LINKAGEM DA C-API (CRÍTICO NO WINDOWS/MINGW)
        # O linker (ld.exe) precisa da import library (python3X.lib) para 
        # resolver os símbolos __imp_Py* que serão carregados da dll hospedeira.
        # ═══════════════════════════════════════════════════════════════════
        if os.name == 'nt':
            # ⚠️ CORREÇÃO: No Windows, o venv não tem a pasta 'libs'.
            # Precisamos pegar da instalação base do Python (sys.base_prefix).
            lib_dir = Path(sys.base_prefix) / 'libs'
            version = f"{sys.version_info.major}{sys.version_info.minor}"
            cmd.extend([f'-L{lib_dir}', f'-lpython{version}'])
        else:
            # Fallback para Linux/macOS
            lib_dir = sysconfig.get_config_var('LIBDIR') or ''
            lib_name = sysconfig.get_config_var('LDLIBRARY') or 'python'
            if lib_name.startswith('lib'): lib_name = lib_name[3:]
            if lib_name.endswith('.so'): lib_name = lib_name[:-3]
            if lib_dir:
                cmd.extend([f'-L{lib_dir}', f'-l{lib_name}'])

        # Output
        cmd.extend(['-o', str(self.output_file)])
        
        # ⚠️ NOTA CRÍTICA (Windows/MinGW): 
        # NÃO linkamos com -lpython3X. Os símbolos da C-API (PyArg_ParseTuple, etc)
        # são resolvidos em runtime pelo python.exe hospedeiro. Linkar causaria erro.
        
        # 3. EXECUÇÃO DA METALURGIA
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace'
            )
            
            if result.returncode != 0:
                print(f"  ✘ [HERMES v2] Erro na Metalurgia:")
                print(result.stderr)
                return False
                
            # 4. SUCESSO: Atualiza o Cache
            self._save_cache({'sources_hash': self._get_sources_hash()})
            
            size_kb = self.output_file.stat().st_size / 1024
            print(f"  ✔ [HERMES v2] Bridge gerado com sucesso: {self.output_file.name} ({size_kb:.1f} KB)")
            return True
            
        except Exception as e:
            print(f"  ✘ [HERMES v2] Falha catastrófica no build: {e}")
            return False

# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA (Para o boot.py ou hermes_init.py)
# ═══════════════════════════════════════════════════════════════════════════════
def ensure_bridge_built(project_root: str) -> bool:
    """
    Garante que o motor nativo do Hermes v2 está compilado e pronto.
    Chamado durante o bootstrap do Doxoade.
    """
    builder = HermesBridgeBuilder(project_root)
    return builder.build()