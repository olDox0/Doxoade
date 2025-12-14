
import sys

# Codigo Gerado:
def <UNK> (data,  val): return data + val

if __name__ == "__main__":
    try:
        pass
        print("SUCESSO_TESTES")
    except AssertionError:
        print("FALHA_ASSERT")
        sys.exit(1)
    except NameError as ne:
        print(f"ERRO_NOME: {ne}") 
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)
