// doxoade/experiments/soteria_lab/gordian_lab.c
/*
 * GORDIAN LAB v2.0 — Laboratório de Testes Sotéria
 * 4 vetores de crash para validação do sistema de diagnóstico.
 *
 * Build: doxoade metal build -t gordian_test -f
 * Run:   doxoade metal run gordian_test <1-4>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include "soteria.h"

/* ═══════════════════════════════════════════════════════════════════
 * VETOR 1: Stack Smashing (Buffer Overflow no retorno)
 * ═══════════════════════════════════════════════════════════════════ */
void falha_vulneravel_stack(void) {
    printf("■ [VETOR 1] Provocando colapso de pilha...\n");
    char buffer[5];
    soteria_mark("PRE_STACK_SMASH", __FILE__, __LINE__);
    /* Atropela o cookie de segurança da stack (GS) */
    memset(buffer, 'X', 100);
    printf("■ Se voce ler isso, a stack sobreviveu ao overflow (mas o retorno vai crashar).\n");
    /* O crash acontece AQUI, quando a função tenta retornar
       usando o endereço de retorno corrompido */
}

/* ═══════════════════════════════════════════════════════════════════
 * VETOR 2: Race Condition (Concorrência sem trava)
 * ═══════════════════════════════════════════════════════════════════ */
static int contador_global = 0;

DWORD WINAPI ThreadCaotica(LPVOID lpParam) {
    (void)lpParam;
    for (int i = 0; i < 1000; i++) {
        soteria_access_probe(&contador_global, __FILE__, __LINE__, 1);
        contador_global++;
    }
    return 0;
}

void falha_concorrencia(void) {
    printf("■ [VETOR 2] Iniciando Guerra de Threads...\n");
    HANDLE h1 = CreateThread(NULL, 0, ThreadCaotica, NULL, 0, NULL);
    HANDLE h2 = CreateThread(NULL, 0, ThreadCaotica, NULL, 0, NULL);
    WaitForSingleObject(h1, INFINITE);
    WaitForSingleObject(h2, INFINITE);
    CloseHandle(h1);
    CloseHandle(h2);
    SOTERIA_ALERT("RACE_CONDITION_LIKELY",
                  "O valor final do contador divergiu do esperado.");
}

/* ═══════════════════════════════════════════════════════════════════
 * VETOR 3: Silent Corruption (Corrupção de Canário)
 * ═══════════════════════════════════════════════════════════════════ */
void falha_corrupcao_silenciosa(void) {
    int *dados = (int *)soteria_malloc_ext(sizeof(int) * 2,
                                           ALLOC_MALLOC, __FILE__, __LINE__);
    printf("■ [VETOR 3] Corrompendo a Zona de Guarda (Canário)...\n");
    /* GUARD_SIZE é 16. p[-16] acerta o canário INICIAL */
    unsigned char *p = (unsigned char *)dados;
    p[-16] = 0x00;
    soteria_validate(dados, __FILE__, __LINE__);
    soteria_free_ext(dados, ALLOC_MALLOC, __FILE__, __LINE__);
}

/* ═══════════════════════════════════════════════════════════════════
 * VETOR 4: Stack Overflow (Recursão Infinita)
 * ═══════════════════════════════════════════════════════════════════ */
void provocar_colapso_pilha(int profundidade) {
    char buffer[1048576]; /* 1 MB na stack por chamada */
    SOTERIA_MARK_VAR(profundidade);
    buffer[0] = (char)profundidade; /* evita otimização do compilador */
    provocar_colapso_pilha(profundidade + 1);
}

/* ═══════════════════════════════════════════════════════════════════
 * MAIN
 * ═══════════════════════════════════════════════════════════════════ */
int main(int argc, char **argv) {
    soteria_init(argc, argv);

    if (argc < 2) {
        printf("Uso: gordian_lab.exe <1-4>\n");
        printf("  1 - Stack Smashing (Buffer Overflow)\n");
        printf("  2 - Race Condition\n");
        printf("  3 - Silent Corruption (Canário)\n");
        printf("  4 - Stack Overflow (Recursão Infinita)\n");
        return 1;
    }

    int vetor = atoi(argv[1]);

    switch (vetor) {
        case 1: falha_vulneravel_stack();    break;
        case 2: falha_concorrencia();        break;
        case 3: falha_corrupcao_silenciosa(); break;
        case 4: provocar_colapso_pilha(0);   break;
        default:
            printf("Vetor inválido: %d (use 1-4)\n", vetor);
            return 1;
    }

    return 0;
}