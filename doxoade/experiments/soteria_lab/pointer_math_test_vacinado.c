#include <stdio.h>
#include <stdlib.h>
#include "soteria.h"

void demonstracao_corrupcao() {
    SOTERIA_ENTER("demonstracao_corrupcao");
    SOTERIA_ENTER("demonstracao_corrupcao");

    // Alocamos espaço para 2 inteiros (8 bytes)
    int *dados = (int*)malloc(2 * sizeof(int));
    
    printf("■ Modificando dados alem do limite...\n");
    
    // Aritmética agressiva: Vamos escrever na posição 3 (que não existe)
    // O array só tem índices 0 e 1. O índice 2 e 3 são a Zona de Guarda!
    dados[2] = 999; 

    printf("■ Validando integridade...\n");
    SOTERIA_VALIDATE(dados); // A SOTÉRIA DEVE PEGAR O CANÁRIO MORTO AQUI
}

int main() {
    demonstracao_corrupcao();
    return 0;
}