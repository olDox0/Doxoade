
import sys
# def soma ( data , data ) : return data + data

if __name__ == "__main__":
    try:
        assert soma(2, 3) == 5
        print("SUCESSO_TESTES")
    except AssertionError:
        print("FALHA_ASSERT")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)
