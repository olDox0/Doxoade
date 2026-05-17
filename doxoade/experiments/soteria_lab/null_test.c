#include <stdio.h>

void sub_rotina_profunda() {
    // SOTERIA_ENTER injetado aqui
    int *p = NULL;
    printf("■ Preparando acesso a memoria nula...\n");
    
    // Acionamento de Sekhmet: O processador vai travar aqui
    int valor = *p; 
    
    printf("Valor capturado: %d\n", valor);
}

int main() {
    printf("--- Teste de Estresse: Ponteiro Nulo ---\n");
    sub_rotina_profunda();
    return 0;
}