from library import soma_simples, comando_cli
# [ERRO 1] Importando algo que não existe (Link Quebrado)
from library import funcao_removida 

def executar_testes():
    # [ERRO 2] Chamada com poucos argumentos (soma exige 2)
    print(soma_simples(10)) 
    
    # [OK] Chamada correta
    print(soma_simples(10, 20))

    # [OK] Chamada de função Click (deve ser ignorada pela validação de args)
    comando_cli() 

if __name__ == "__main__":
    executar_testes()