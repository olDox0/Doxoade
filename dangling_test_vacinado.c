#include <stdio.h>
#include <stdlib.h>
#include "soteria.h"

void crime_de_memoria() {
    SOTERIA_ENTER("crime_de_memoria");
    SOTERIA_ENTER("crime_de_memoria");
    
    int* segredo = (int*)malloc(sizeof(int));
    *segredo = 123;
    printf("Valor inicial: %d\n", *segredo);

    printf("Liberando memoria...\n");
    free(segredo);

    // Tentativa de validar o ponteiro após o free
    printf("Validando ponteiro solto...\n");
    SOTERIA_VALIDATE(segredo); // A SOTÉRIA DEVE PEGAR ISSO AQUI
    
    printf("Este print nunca deve aparecer.\n");
}

int main() {
    crime_de_memoria();
    return 0;
}