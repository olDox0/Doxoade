#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include "soteria.h"

// Cenário 1: Stack Smashing (Atropelando o endereço de retorno)
void falha_vulneravel_stack() {
    SOTERIA_ENTER("falha_vulneravel_stack");
    printf("■ [VETOR 1] Provocando colapso de pilha...\n");
    char buffer[5];
    // O rastro da Sotéria vai registrar esse passo antes da morte
    soteria_mark("PRE_STACK_SMASH", __FILE__, __LINE__);
    
    // Isso vai atropelar o 'Cookie' de segurança da stack do Windows (GS)
    memset(buffer, 'X', 100); 
    
    printf("■ Se voce ler isso, a stack sobreviveu (Inesperado).\n");
}

// Cenário 2: Race Condition (Concorrência sem trava)
int contador_global = 0;
DWORD WINAPI ThreadCaotica(LPVOID lpParam) {
    for(int i = 0; i < 1000; i++) {
        // Simulando acesso concorrente perigoso
        soteria_access_probe(&contador_global, __FILE__, __LINE__, 1);
        contador_global++;
    }
    return 0;
}

void falha_concorrencia() {
    SOTERIA_ENTER("falha_concorrencia");
    printf("■ [VETOR 2] Iniciando Guerra de Threads...\n");
    HANDLE h1 = CreateThread(NULL, 0, ThreadCaotica, NULL, 0, NULL);
    HANDLE h2 = CreateThread(NULL, 0, ThreadCaotica, NULL, 0, NULL);
    WaitForSingleObject(h1, INFINITE);
    WaitForSingleObject(h2, INFINITE);
    SOTERIA_ALERT("RACE_CONDITION_LIKELY", "O valor final do contador divergiu do esperado.");
}

// Cenário 3: Silent Corruption (Corrupção de Canário)
void falha_corrupcao_silenciosa() {
    SOTERIA_ENTER("falha_corrupcao_silenciosa");
    int *dados = (int*)soteria_malloc(sizeof(int) * 2, __FILE__, __LINE__);
    printf("■ [VETOR 3] Corrompendo a Zona de Guarda (Canário)...\n");
    
    // GUARD_SIZE é 16. Para chegar no canário (início do bloco):
    unsigned char *p = (unsigned char*)dados;
    p[-16] = 0x00; // ACERTO DIRETO NO CANÁRIO
    
    soteria_validate(dados, __FILE__, __LINE__);
}

int main(int argc, char** argv) {
    soteria_init(argc, argv);
    if (argc < 2) {
        printf("Uso: gordian_lab.exe <1-3>\n");
        return 1;
    }
    int modo = atoi(argv[1]);
    if (modo == 1) falha_vulneravel_stack();
    if (modo == 2) falha_concorrencia();
    if (modo == 3) falha_corrupcao_silenciosa();
    return 0;
}