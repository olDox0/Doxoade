# doxoade/__main__.py
import sys
import os
import subprocess
import tempfile

def main():
    try:
        # Tenta importar o núcleo
        # Se houver SyntaxError ou ImportError no cli.py, falha aqui.
        from doxoade.cli import cli
        cli()
        
    except Exception:
        # Captura QUALQUER erro fatal que impeça o CLI de rodar
        import traceback
        err_msg = traceback.format_exc()
        
        # Caminho para o script de resgate
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rescue_script = os.path.join(current_dir, 'rescue.py')
        
        # Salva erro em temp para passar ao rescue
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(err_msg)
            
            # Chama o resgate em um NOVO processo limpo
            subprocess.run([sys.executable, rescue_script, path])
            
        finally:
            os.remove(path)
        
        sys.exit(1)

if __name__ == "__main__":
    main()