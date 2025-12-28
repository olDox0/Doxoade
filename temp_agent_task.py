import sys
import os

def integra ( arquivo ) : return arquivo

if __name__ == '__main__':
    try:
        import os
        try: os.remove('teste_io.txt')
        except: pass
        salvar_arquivo('teste_io.txt', 'Ola Doxoade')
        assert os.path.exists('teste_io.txt') or os.path.exists('file.txt')
        with open('teste_io.txt' if os.path.exists('teste_io.txt') else 'file.txt', 'r') as f: assert 'Ola' in f.read()
        print('SUCESSO_TESTES')
    except Exception as e:
        print(f'FALHA_ASSERT: {e}')
        sys.exit(1)
