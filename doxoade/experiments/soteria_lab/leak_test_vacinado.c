#include <stdio.h>
#include <stdlib.h>
#include "soteria.h"

void alocacao_esquecida() {
    SOTERIA_ENTER("alocacao_esquecida");
    SOTERIA_ENTER("alocacao_esquecida");
    printf("Alocando 512 bytes que nunca serao limpos...\n");
    void* lixo = malloc(512); 
    // O free(lixo) foi esquecido de proposito
}

int main() {
    printf("--- Iniciando Teste de Memory Leak ---\n");
    alocacao_esquecida();
    printf("Finalizando programa normalmente...\n");
    return 0;
}