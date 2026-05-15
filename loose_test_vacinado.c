#include "soteria.h"
#include <stdio.h>

void funcao_perigosa() {
    SOTERIA_ENTER("funcao_perigosa");
    printf("[C-SOLTO] Executando logica sem protecao manual...\n");
    int *corrupcao = NULL;
    *corrupcao = 404; // VAI DISPARAR SIGSEGV
}

int main(int argc, char** argv) {
    printf("--- Iniciando Binario Nativo ---\n");
    funcao_perigosa();
    return 0;
}