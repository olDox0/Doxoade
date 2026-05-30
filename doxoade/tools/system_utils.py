# doxoade/doxoade/tools/system_utils.py
import os

def is_termux():
    """Detecta se está rodando no Termux"""
    return os.path.exists('/data/data/com.termux')
    
def auto_vaccinate_env():
    """Vacina o venv para que 'python script.py' acione o Lazarus."""
    import sysconfig
    import os
    import sys
    from pathlib import Path
    
    # Só vacina se estiver em um ambiente virtual
    if not (sys.prefix != sys.base_prefix or 'VIRTUAL_ENV' in os.environ):
        return

    try:
        # Localiza o site-packages do venv
        sp_dir = Path(sysconfig.get_path('purelib'))
        site_customize = sp_dir / "sitecustomize.py"
        
        # Localiza a raiz do seu projeto Doxoade
        # (Subindo 3 níveis de system_utils.py -> tools -> doxoade -> raiz)
        project_root = Path(__file__).resolve().parents[2]
        
        signature = "# [DOXOADE:LAZARUS_SHIELD_V2]"
        
        # O código injetado agora garante que o projeto está no path
        hook_code = (
            f"\n{signature}\n"
            "import sys\n"
            "import os\n"
            f"project_root = r'{str(project_root)}'\n"
            "if project_root not in sys.path: sys.path.insert(0, project_root)\n"
            "try:\n"
            "    import doxoade.tools.aegis.lazarus_hook as lz\n"
            "    lz.install()\n"
            "except Exception: pass\n"
            f"{signature}_END\n"
        )

        if site_customize.exists():
            content = site_customize.read_text(encoding='utf-8', errors='ignore')
            if signature in content:
                return 
            with open(site_customize, "a", encoding='utf-8') as f:
                f.write(hook_code)
        else:
            site_customize.write_text(hook_code, encoding='utf-8')
            
        print(f"\033[94m[*] Lazarus Shield instalado em: {site_customize}\033[0m")
    except Exception as e:
        # Se falhar aqui, mostramos o erro de forma elegante
        print(f"\033[93m[!] Falha na vacinação automática: {e}\033[0m")