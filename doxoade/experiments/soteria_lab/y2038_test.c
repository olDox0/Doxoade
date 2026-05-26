#include <stdio.h>
#include <stdint.h>
#include "soteria.h" // O compilador agora vai achar este arquivo

void testar_tempo() {
    SOTERIA_ENTER("testar_tempo");
    int32_t tempo = 0x7FFFFFFF; // Limite de 32 bits
    printf("■ Simulando data limite: %d\n", tempo);
    
    int32_t estouro = tempo + 1;
    if (estouro < 0) {
        // Diagnóstico Freestyle em ação
        SOTERIA_ALERT("Y2038_OVERFLOW", "O carimbo de tempo estourou e tornou-se negativo.");
    }
}

int main() {
    soteria_init(0, NULL);
    testar_tempo();
    return 0;
}