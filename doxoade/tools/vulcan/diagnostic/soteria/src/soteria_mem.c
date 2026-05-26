// doxoade/tools/vulcan/diagnostic/soteria/src/soteria_mem.c

#define SOTERIA_CORE
#include "../include/soteria.h"
#include <string.h>
#include <stdio.h>
#include <stdint.h>

// Assinatura secreta do Nexus (NEXUSOAD)
#define NEXUS_CANARY 0x4E455855534F4144ULL 
#define GUARD_SIZE 16

typedef struct { void* user_ptr; void* real_ptr; size_t user_size; const char* file; int line; int is_live; } mem_rec_t;
typedef struct { char type[32]; size_t size; } arena_snapshot_t;
static mem_rec_t g_mem_db[512];
static int g_mem_ptr = 0;
static arena_snapshot_t g_arena_log[20]; // Rastreia as últimas 20 alocações
static int g_arena_idx = 0;
void soteria_arena_report_alloc(const char* arena_name, const char* obj_type, size_t size);
void soteria_dump_arena_inventory();

void soteria_arena_report_alloc(const char* arena_name, const char* obj_type, size_t size) {
    // Registro circular ultra-rápido
    strncpy(g_arena_log[g_arena_idx].type, obj_type, 31);
    g_arena_log[g_arena_idx].size = size;
    g_arena_idx = (g_arena_idx + 1) % 20;
}

void soteria_dump_arena_inventory() {
    // [PLATINA] Apenas as tags puras. O dispatch cuidará dos marcadores.
    for (int i = 0; i < 20; i++) {
        if (g_arena_log[i].size > 0) {
            fprintf(stdout, "TAG_ARENA_OBJ: %s | %zu bytes\n", 
                    g_arena_log[i].type, g_arena_log[i].size);
        }
    }
}

void soteria_access_probe(void* addr, const char* file, int line, int is_write) {
    // [NEXUS ATOMIC SENTINEL]
    static volatile void* g_last_addr = NULL;
    static volatile unsigned long g_last_tid = 0;
    
    unsigned long current_tid = GetCurrentThreadId();

    // Se duas threads diferentes tocarem no MESMO endereço em um intervalo curto
    if (g_last_addr == addr && g_last_tid != current_tid) {
        // Disparamos um alerta Freestyle que o Lazarus já sabe ler
        soteria_dispatch(SOTERIA_WARN, SOT_ERR_LOGIC, "CONCURRENCY_HAZARD", 
                         "Detecção de Condição de Corrida: Múltiplas threads acessando a mesma RAM.", 
                         file, line, "Sentinel");
        
        // Limpamos para não inundar o log
        g_last_addr = NULL; 
    } else {
        g_last_addr = addr;
        g_last_tid = current_tid;
    }
}

void* soteria_malloc(size_t size, const char* file, int line) {
    size_t total_size = size + (GUARD_SIZE * 2);
    unsigned char* real_p = (unsigned char*)(malloc)(total_size);
    if (!real_p) return NULL;

    *(unsigned long long*)real_p = NEXUS_CANARY;
    *(unsigned long long*)(real_p + GUARD_SIZE + size) = NEXUS_CANARY;

    void* user_p = (void*)(real_p + GUARD_SIZE);

//    soteria_arena_report_alloc("CORE_RUNTIME", "heap_block", size);
    soteria_arena_report_alloc("Gordian_Lab", "heap_block", size);
    fprintf(stdout, "TAG_ARENA_OBJ: heap_block | %zu bytes\n", size);

    if (g_mem_ptr < 512) {
        g_mem_db[g_mem_ptr++] = (mem_rec_t){user_p, real_p, size, file, line, 1};
    }
    
    // --- NEXUS FIX: Registra o bloco no inventário para o Lazarus ---
    soteria_arena_report_alloc("Soteria_Lab", "memory_block", size);
    
    return user_p;
}

void soteria_validate(void* ptr, const char* file, int line) {
    if (!ptr) return;
    // DEIXA O RASTRO ANTES DE VALIDAR
    soteria_mark("VALIDATING_MEMORY", file, line); 

    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr == ptr) {
            unsigned char* real_p = (unsigned char*)g_mem_db[i].real_ptr;
            if (*(unsigned long long*)real_p != NEXUS_CANARY) {
                soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "SILENT_CORRUPTION", 
                                 "Zona de Guarda Violada! O canario de segurança foi alterado.", 
                                 file, line, "Sentinel");
            }
            return;
        }
    }
}

void soteria_free(void* ptr, const char* file, int line) {
    if (!ptr) return;

    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr == ptr) {
            if (!g_mem_db[i].is_live) {
                soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "DOUBLE_FREE", 
                                 "Corrupcao de Heap: Tentativa de liberar o mesmo bloco duas vezes.", file, line, "Free");
            }
            g_mem_db[i].is_live = 0;
            (free)(g_mem_db[i].real_ptr);
            return;
        }
    }
    // Caso o ponteiro não esteja no nosso mapa (estrangeiro)
    (free)(ptr);
}