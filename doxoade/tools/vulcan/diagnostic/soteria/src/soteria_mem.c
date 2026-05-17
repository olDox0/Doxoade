// doxoade/tools/vulcan/diagnostic/soteria/src/soteria_mem.c

#define SOTERIA_CORE
#include "../include/soteria.h"
#include <string.h>
#include <stdio.h>
#include <stdint.h>

// Assinatura secreta do Nexus (NEXUSOAD)
#define NEXUS_CANARY 0x4E455855534F4144ULL 
#define GUARD_SIZE 8

typedef struct { void* user_ptr; void* real_ptr; size_t user_size; const char* file; int line; int is_live; } mem_rec_t;
static mem_rec_t g_mem_db[512];
static int g_mem_ptr = 0;

void* soteria_malloc(size_t size, const char* file, int line) {
    // Aloca: [8b CANARY] + [USER DATA] + [8b CANARY]
    size_t total_size = size + (GUARD_SIZE * 2);
    unsigned char* real_p = (unsigned char*)(malloc)(total_size);
    
    if (!real_p) return NULL;

    // Instala os Canários (Zonas de Guarda)
    *(unsigned long long*)real_p = NEXUS_CANARY; // Início
    *(unsigned long long*)(real_p + GUARD_SIZE + size) = NEXUS_CANARY; // Fim

    void* user_p = (void*)(real_p + GUARD_SIZE);

    if (g_mem_ptr < 512) {
        g_mem_db[g_mem_ptr++] = (mem_rec_t){user_p, real_p, size, file, line, 1};
    }
    return user_p;
}

void soteria_validate(void* ptr, const char* file, int line) {
    if (!ptr) return;

    // 1. CHECAGEM DE ALINHAMENTO (CRÍTICO PARA SSE4.2 / N2808)
    if (((uintptr_t)ptr % 16) != 0) {
        char detail[256];
        sprintf(detail, "PONTEIRO DESALINHADO: Endereço %p não é múltiplo de 16. "
                        "Risco de crash em kernels SSE4.2/AVX.", ptr);
        
        soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "HARDWARE_ALIGNMENT", 
                         detail, file, line, "SoteriaProbe");
    }

    // 2. CHECAGEM DE CANÁRIO (O que já temos)
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr == ptr && g_mem_db[i].is_live) {
            unsigned char* real_p = (unsigned char*)g_mem_db[i].real_ptr;
            size_t sz = g_mem_db[i].user_size;
            if (*(unsigned long long*)real_p != NEXUS_CANARY || *(unsigned long long*)(real_p + GUARD_SIZE + sz) != NEXUS_CANARY) {
                soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "CORRUPTION", "Zona de Guarda violada!", file, line, "validate");
            }
            return;
        }
    }
}

void soteria_free(void* ptr, const char* file, int line) {
    if (!ptr) return;
    soteria_validate(ptr, file, line); // Valida antes de liberar

    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr == ptr && g_mem_db[i].is_live) {
            g_mem_db[i].is_live = 0;
            (free)(g_mem_db[i].real_ptr);
            return;
        }
    }
    (free)(ptr);
}