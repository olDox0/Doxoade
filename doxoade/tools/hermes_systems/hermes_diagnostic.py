#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_diagnostic.py
"""
Hermes Diagnostic Module - Sistema de Diagnóstico para Falhas Silenciosas
==========================================================================

Este módulo captura crashes silenciosos (SegFaults, Access Violations) que 
acontecem no Motor C (hermes_bridge.pyd) e faz dump completo do estado do 
sistema antes do processo morrer.

Integração:
- Faulthandler (Python stdlib) para capturar sinais
- Hermes Async Logger para logs não-bloqueantes
- Sotéria para análise forense
- Horus para observabilidade

Uso:
    from doxoade.tools.hermes_systems.hermes_diagnostic import install_diagnostic_hooks
    install_diagnostic_hooks()
"""

import sys
import os
import faulthandler
import traceback
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class HermesDiagnostic:
    """
    Sistema de diagnóstico para capturar falhas silenciosas no Hermes.
    """
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.diagnostic_dir = self.root / '.doxoade' / 'hermes' / 'diagnostics'
        self.diagnostic_dir.mkdir(parents=True, exist_ok=True)
        self._installed = False
        self._logger = None
        
    def _get_logger(self):
        """Lazy load do Hermes Async Logger."""
        if self._logger is None:
            try:
                from doxoade.tools.hermes_systems.hermes_logger import get_logger
                self._logger = get_logger()
            except Exception:
                self._logger = None
        return self._logger
    
    def install(self):
        """
        Instala hooks de diagnóstico para capturar crashes.
        """
        if self._installed:
            return
            
        # 1. Habilita faulthandler para capturar SegFaults
        faulthandler.enable()
        
        # 2. Registra dump file para crashes
        dump_file = self.diagnostic_dir / 'crash_dump.log'
        try:
            faulthandler.dump_traceback_later(
                timeout=30,  # Se travar por 30s, faz dump
                file=open(dump_file, 'w', encoding='utf-8'),
                exit=False
            )
        except Exception as e:
            print(f"[HERMES-DIAG] ⚠ Falha ao registrar dump: {e}")
        
        # 3. Instala hook de exceção não-capturada
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._exception_handler
        
        self._installed = True
        
        logger = self._get_logger()
        if logger:
            logger.info("Hermes Diagnostic hooks instalados")
    
    def uninstall(self):
        """
        Remove hooks de diagnóstico.
        """
        if not self._installed:
            return
            
        # Restaura excepthook original
        if hasattr(self, '_original_excepthook'):
            sys.excepthook = self._original_excepthook
            
        # Cancela dump automático
        faulthandler.cancel_dump_traceback_later()
        
        self._installed = False
    
    def _exception_handler(self, exc_type, exc_value, exc_traceback):
        """
        Handler customizado para exceções não-capturadas.
        Faz dump completo antes de morrer.
        """
        # 1. Log via Hermes Logger
        logger = self._get_logger()
        if logger:
            logger.error(
                f"Uncaught exception: {exc_type.__name__}: {exc_value}"
            )
        
        # 2. Salva dump completo em disco
        self._save_crash_dump(exc_type, exc_value, exc_traceback)
        
        # 3. Chama handler original (geralmente printa e morre)
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_traceback)
    
    def _save_crash_dump(
        self, 
        exc_type: type, 
        exc_value: Exception, 
        exc_traceback: Any
    ):
        """
        Salva dump completo do crash em disco.
        """
        timestamp = datetime.now().isoformat()
        dump_file = self.diagnostic_dir / f'crash_{int(time.time())}.json'
        
        # Coleta informações do sistema
        dump_data = {
            'timestamp': timestamp,
            'exception': {
                'type': exc_type.__name__,
                'value': str(exc_value),
                'traceback': ''.join(traceback.format_tb(exc_traceback))
            },
            'system': {
                'python_version': sys.version,
                'platform': sys.platform,
                'executable': sys.executable,
                'path': sys.path,
                'modules_loaded': list(sys.modules.keys())[:100]
            },
            'environment': {
                key: value 
                for key, value in os.environ.items()
                if 'HERMES' in key or 'VULCAN' in key or 'DOXOADE' in key
            }
        }
        
        # Tenta adicionar informações do Hermes
        try:
            from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
            loader = HermesLoader(str(self.root))
            dump_data['hermes'] = {
                'cache_size': len(loader._code_cache),
                'cache_max': loader._cache_max_size
            }
        except Exception:
            pass
        
        # Salva em disco
        try:
            with open(dump_file, 'w', encoding='utf-8') as f:
                json.dump(dump_data, f, indent=2, ensure_ascii=False)
            
            print(f"[HERMES-DIAG] 💾 Crash dump salvo: {dump_file}")
        except Exception as e:
            print(f"[HERMES-DIAG] ❌ Falha ao salvar dump: {e}")
    
    def diagnose_module_load(self, module_name: str, hbc6_path: Path) -> Dict[str, Any]:
        """
        Diagnóstico completo do carregamento de um módulo HBC6.
        """
        result = {
            'module': module_name,
            'hbc6_path': str(hbc6_path),
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Check 1: Arquivo existe?
        result['checks']['file_exists'] = hbc6_path.exists()
        
        if not hbc6_path.exists():
            result['status'] = 'FAIL'
            result['error'] = 'Arquivo HBC6 não encontrado'
            return result
        
        # Check 2: Tamanho do arquivo
        result['checks']['file_size'] = hbc6_path.stat().st_size
        
        # Check 3: Magic bytes
        try:
            with open(hbc6_path, 'rb') as f:
                magic = f.read(4)
                result['checks']['magic'] = magic.decode('ascii', errors='replace')
                result['checks']['magic_valid'] = (magic == b'HBC6')
        except Exception as e:
            result['checks']['magic_error'] = str(e)
        
        # Check 4: Tenta carregar via Python fallback
        try:
            from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
            loader = HermesLoader(str(self.root))
            
            start = time.perf_counter()
            code_obj = loader.decompress_to_code(hbc6_path)
            elapsed = (time.perf_counter() - start) * 1000
            
            result['checks']['python_load'] = {
                'success': code_obj is not None,
                'time_ms': elapsed,
                'code_obj_type': type(code_obj).__name__ if code_obj else None
            }
        except Exception as e:
            result['checks']['python_load'] = {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
        
        # Check 5: Tenta carregar via Motor C
        try:
            from doxoade.tools.hermes_systems.native import hermes_bridge
            gd_path = self.root / '.doxoade' / 'hermes' / 'master.bin'
            
            start = time.perf_counter()
            code_obj_c = hermes_bridge.load_module(
                str(hbc6_path),
                str(gd_path) if gd_path.exists() else ""
            )
            elapsed = (time.perf_counter() - start) * 1000
            
            result['checks']['c_load'] = {
                'success': code_obj_c is not None,
                'time_ms': elapsed,
                'code_obj_type': type(code_obj_c).__name__ if code_obj_c else None
            }
        except Exception as e:
            result['checks']['c_load'] = {
                'success': False,
                'error': str(e)
            }
        
        # Status final
        python_ok = result['checks'].get('python_load', {}).get('success', False)
        c_ok = result['checks'].get('c_load', {}).get('success', False)
        
        if python_ok or c_ok:
            result['status'] = 'OK'
        else:
            result['status'] = 'FAIL'
        
        return result


def install_diagnostic_hooks(project_root: Optional[str] = None):
    """
    Instala hooks de diagnóstico globalmente.
    """
    if project_root is None:
        project_root = os.getcwd()
    
    diag = HermesDiagnostic(project_root)
    diag.install()
    
    return diag


def diagnose_hbc6_module(module_name: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Função de conveniência para diagnosticar um módulo HBC6 específico.
    """
    if project_root is None:
        project_root = os.getcwd()
    
    # Converte module_name para path
    module_path = module_name.replace('.', os.sep)
    hbc6_name = f"{module_path}.hbc6"
    
    root = Path(project_root).resolve()
    build_dir = root / '.doxoade' / 'hermes' / 'build'
    
    # Procura o arquivo HBC6
    hbc6_path = None
    for candidate in build_dir.glob(f"**/{hbc6_name}"):
        hbc6_path = candidate
        break
    
    if hbc6_path is None:
        for candidate in build_dir.glob(f"**/{module_path}_*.hbc6"):
            hbc6_path = candidate
            break
    
    if hbc6_path is None:
        return {
            'module': module_name,
            'status': 'FAIL',
            'error': f'Arquivo HBC6 não encontrado para {module_name}'
        }
    
    # Executa diagnóstico
    diag = HermesDiagnostic(project_root)
    return diag.diagnose_module_load(module_name, hbc6_path)