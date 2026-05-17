#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "soteria.h"

void processo_matematico() {
    SOTERIA_ENTER("processo_matematico");

    // Alocamos memória (malloc garante alinhamento básico)
    float *buffer = (float*)malloc(10 * sizeof(float));
    printf("■ Buffer alinhado em: %p\n", (void*)buffer);

    // Provocamos o desalinhamento: saltamos 1 byte à frente
    // Agora o ponteiro não é mais múltiplo de 16 (ou mesmo de 4)
    float *p_torto = (float*)((uint8_t*)buffer + 1);
    printf("■ Ponteiro 'torto' (desalinhado): %p\n", (void*)p_torto);

    printf("■ Validando alinhamento antes de operacao SSE...\n");
    SOTERIA_VALIDATE(p_torto); // A SOTÉRIA DEVE INTERCEPTAR AQUI
}

int main() {
    processo_matematico();
    return 0;
}