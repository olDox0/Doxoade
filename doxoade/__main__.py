# doxoade/doxoade/__main__.py
import sys
import os
import tempfile
import subprocess
import traceback
from doxoade.tools.filesystem import _get_project_config

if os.environ.get('DOXOADE_HORUS_ACTIVE') == '1':
    try:
        from doxoade.tools.horus_scribe import activate_horus_shadow
        activate_horus_shadow()
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
#        traceback.print_exc()

def _detect_emergency_flags():
    """Detecta flags de bypass antes do boot dos motores."""
    flags = {
        'pure': "--pure" in sys.argv,
        'no_shadow': "--no-shadow" in sys.argv,
        'no_rescue': "--no-rescue" in sys.argv,
        'verbose': "--verbose" in sys.argv
    }
    
    # Limpa sys.argv para o Click não reclamar de flags desconhecidas
    for f in ["--pure", "--no-shadow", "--no-rescue", "--verbose"]:
        if f in sys.argv: sys.argv.remove(f)
        
    return flags

def _inject_internal_venv():
    """
    Localiza o venv interno do doxoade e o injeta no sys.path
    antes de carregar o restante do sistema.
    """
    # __file__ é .../doxoade/doxoade/__main__.py
    # package_dir é .../doxoade/doxoade
    package_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root é .../doxoade (onde fica a pasta /venv)
    project_root = os.path.dirname(package_dir)
    config = _get_project_config(start_path=project_root)
    # Caminho do site-packages no Windows
    venv_libs = os.path.join(project_root, 'venv', 'Lib', 'site-packages')
    
    if os.environ.get('DOXOADE_HORUS_ACTIVE') == '1' or config.get('shadow_runtime', False):
        try:
            from doxoade.tools.horus_scribe import activate_horus_shadow
            activate_horus_shadow()
        except Exception as e:
            # Fallback silencioso
            pass
    
    # Se não existir Lib (Linux/Mac), tenta o padrão posix
    if not os.path.exists(venv_libs):
        # Tenta achar algo como venv/lib/python3.x/site-packages
        lib_path = os.path.join(project_root, 'venv', 'lib')
        if os.path.exists(lib_path):
            for py_dir in os.listdir(lib_path):
                site_p = os.path.join(lib_path, py_dir, 'site-packages')
                if os.path.exists(site_p):
                    venv_libs = site_p
                    break

    if os.path.exists(venv_libs) and venv_libs not in sys.path:
        sys.path.insert(0, venv_libs)

def _early_setup(project_root: str):
    """Garante diretórios e executa os Portões de Segurança (NSR/Vulcan/ABI)."""
    try:
        # 1. Carrega configurações do TOML
        from doxoade.tools.filesystem import _get_project_config
        config = _get_project_config(start_path=project_root)
        
        # 2. Ativa o Shadow Runtime (NSR) se permitido
        if config.get('shadow_runtime', True) and os.environ.get('DOXOADE_SHADOW') != '0':
            from doxoade.tools.vulcan.shadow_runtime import install_shadow_runtime
            install_shadow_runtime(project_root)
            
        # 3. Executa o Portão ABI (Vulcan)
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        # Falha silenciosa no setup não deve impedir o boot, mas avisa em modo verbose
        if os.environ.get('VULCAN_VERBOSE') == '1':
            print(f'\x1b[33m ■ Aviso Setup: {e}\x1b[0m')
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            exc_trace(exc_tb)
            from doxoade.rescue import activate_protocol
            import traceback
            activate_protocol(traceback.format_exc())

def main():
    # 1. Configura o VENV primeiro de tudo
    _inject_internal_venv()
    
    # 2. Define o root do código do sistema
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 3. Setup de segurança
    flags = _detect_emergency_flags()
    package_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(package_dir)
    
    from doxoade.tools.filesystem import _get_project_config
    config = _get_project_config(start_path=project_root)
    
    try:
        _early_setup(project_root)
    except Exception as e:
        import traceback
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        from doxoade.rescue import activate_protocol
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
    
    shadow_wanted = config.get('shadow_runtime', True) or os.environ.get('DOXOADE_SHADOW') == '1'
#    if not flags['no_shadow'] and config.get('shadow_runtime', True):
#        try:
#            from doxoade.tools.vulcan.shadow_runtime import install_shadow_runtime
#            install_shadow_runtime(project_root)
#        except Exception: pass # Segurança de boot

    # 4. Sotéria/Lazarus Hook
    if not flags['no_rescue'] and config.get('soteria_active', True):
        try:
            from doxoade.tools.aegis.lazarus_hook import install_shield
            install_shield()
        except Exception: pass
    
    try:
        # 4. Importa o CLI apenas agora que o path está correto
        from doxoade.cli import cli
        cli()
    except Exception as e:
        import traceback
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        from doxoade.rescue import activate_protocol
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
        
        if flags['no_rescue']:
            traceback.print_exc()
            sys.exit(1)
            
        from doxoade.rescue import activate_protocol
        activate_protocol(traceback.format_exc(), exit_code=1)

        # Protocolo de resgate se houver crash fatal
        err_msg = traceback.format_exc()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rescue_script = os.path.join(current_dir, 'rescue.py')
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(err_msg)
            # Tenta rodar o rescue.py
            subprocess.run([sys.executable, rescue_script, path], check=False)
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            exc_trace(exc_tb)
        finally:
            try:
                os.remove(path)
            except: pass
        sys.exit(1)

if __name__ == '__main__':
    main()