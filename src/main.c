#include <stdio.h>
#include <string.h>

void versao_do_sistema();

int main() {
    printf("Iniciando Doxoade Nativo...\n");
    versao_do_sistema();
    
    // [TESTE DE ESTRESSE]
    printf("\n[!] Tentando acesso ilegal a memoria...\n");
    int *p = NULL;
    *p = 100; // Isso vai explodir no metal
    
    return 0;
}