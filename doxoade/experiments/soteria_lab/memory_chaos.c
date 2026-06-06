#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "soteria.h"

void provovar_overflow() {
    SOTERIA_ENTER("provovar_overflow");
    char buffer[10];
    printf("■ [VETOR:OVERFLOW] Escrevendo 20 bytes em buffer de 10...\n");
    // O Scribe deve detectar o risco aqui
    strcpy(buffer, "ESTOURO_DE_BUFFER_NEXUS"); 
}

void provocar_heap_corruption() {
    SOTERIA_ENTER("provocar_heap_corruption");
    void *ptr = malloc(16);
    printf("■ [VETOR:HEAP] Corrompendo metadados e forçando double free...\n");
    free(ptr);
    free(ptr); // CRIME DE NÍVEL 1
}

int main(int argc, char** argv) {
    soteria_init(argc, argv);
    if(argc < 2) return 1;
    if(argv[1][0] == '1') provovar_overflow();
    if(argv[1][0] == '2') provocar_heap_corruption();
    return 0;
}