#include <stdio.h>
#include <stdlib.h>
#include "soteria.h"

void rotina_duplicada() {
    SOTERIA_ENTER("rotina_duplicada");
    
    void* bloco = malloc(1024);
    printf("■ Memoria alocada em: %p\n", bloco);

    printf("■ Primeira liberacao...\n");
    free(bloco);

    printf("■ Tentativa de segunda liberacao (O CRIME)...\n");
    free(bloco); // A SOTÉRIA DEVE INTERCEPTAR AQUI
}

int main() {
    printf("--- Inciando Teste de Double Free ---\n");
    rotina_duplicada();
    return 0;
}