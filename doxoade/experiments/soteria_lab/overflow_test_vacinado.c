#include "soteria.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void rotina_vulneravel() {
    SOTERIA_ENTER("rotina_vulneravel");
    // SOTERIA_ENTER será injetado aqui pelo Scribe
    char buffer_pequeno[8];
    printf("■ Provocando estouro de buffer (Overflow)...\n");
    
    // Escreve 64 bytes em um espaço de 8.
    // Isso vai atropelar a stack e os metadados da Sotéria.
    for(int i = 0; i < 64; i++) {
        buffer_pequeno[i] = 'X'; 
    }
}

int main() {
    printf("--- Iniciando Teste de Estresse: Buffer Overflow ---\n");
    rotina_vulneravel();
    printf("Finalizando normalmente (Isso nao deve ocorrer)...\n");
    return 0;
}