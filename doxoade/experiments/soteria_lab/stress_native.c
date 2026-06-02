#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "soteria.h"

// Forçamos o compilador a não otimizar esta função
void __attribute__((optimize("O0"))) provocar_colapso() {
    SOTERIA_ENTER("provocar_colapso");
    
    char buffer_pequeno[10];
    printf("■ [VETOR:SMASH] Atropelando a pilha...\n");
    
    // Atropelamos com um valor que certamente não é um endereço válido (0x585858...)
    // Usamos um loop manual para evitar que o compilador use uma versão segura de memset
    for(int i = 0; i < 150; i++) {
        buffer_pequeno[i] = 'X';
    }

    printf("■ Marco pós-atropelamento (Aguardando retorno da função)...\n");
}

int main() {
    soteria_init(0, NULL);
    provocar_colapso();
    printf("■ Falha: O sistema sobreviveu ao colapso.\n");
    return 0;
}