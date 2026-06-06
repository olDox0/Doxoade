// doxoade/experiments/soteria_lab/pointer_chaos.c

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "soteria.h"

void null_dereference() {
    SOTERIA_ENTER("null_dereference");
    int *p = NULL;
    printf("■ [VETOR:NULL] Acessando endereço zero...\n");
    *p = 123; // Crash imediato 0xC0000005
}

void use_after_free() {
    SOTERIA_ENTER("use_after_free");
    int *p = (int*)malloc(sizeof(int));
    *p = 42;
    free(p);
    printf("■ [VETOR:UAF] Usando ponteiro após free...\n");
    // O sistema deve detectar que 'p' está na lista de 'fantasmas'
    SOTERIA_VALIDATE(p); 
    *p = 99; 
}

// Função que limpa os vestígios da stack anterior
void sujar_stack() {
    // Cria um array grande na pilha e preenche com lixo (Poisoning)
    int v[100];
    for(int i=0; i<100; i++) v[i] = 0xDEADBEEF; 
    soteria_io_trace("stack_poison", "Sujando a cena do crime", __FILE__, __LINE__);
}

void dangling_pointer() {
    SOTERIA_ENTER("dangling_pointer");
    int *p_dangling;
    {
        int stack_var = 10;
        p_dangling = &stack_var;
        printf("■ [VETOR:DANGLING] Endereço da variável: %p\n", (void*)p_dangling);
    } 
    
    // O Vândalo entra aqui. Ele vai usar o mesmo espaço que 'stack_var' usava.
    sujar_stack(); 
    
    printf("■ [VETOR:DANGLING] Tentando ler variável de escopo morto...\n");
    
    // A Sotéria deve perceber que o endereço aponta para uma zona "morta" da pilha
    SOTERIA_VALIDATE(p_dangling); 
    
    printf("Valor capturado (deve ser lixo): %d\n", *p_dangling);
}

int main(int argc, char** argv) {
    soteria_init(argc, argv);
    if(argc < 2) return 1;
    if(argv[1][0] == '1') null_dereference();
    if(argv[1][0] == '2') use_after_free();
    if(argv[1][0] == '3') dangling_pointer();
    return 0;
}