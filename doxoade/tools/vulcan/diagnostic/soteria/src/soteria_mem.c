// doxoade/tools/vulcan/diagnostic/soteria/src/soteria_mem.c

#define SOTERIA_CORE
#include "../include/soteria.h"
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <windows.h>

// --- CONSTANTES DE SEGURANÇA ---
#define NEXUS_CANARY 0x4E455855534F4144ULL 
#define GUARD_SIZE 16
#define MAX_MEM_RECORDS 1024

// --- PROTÓTIPOS INTERNOS (Evita warnings de declaração implícita) ---
void soteria_arena_report_alloc(const char* arena_name, const char* obj_type, size_t size);
void soteria_dump_arena_inventory();
void _mem_lock();
void _mem_unlock();

// --- ESTRUTURAS HADES ---
typedef struct { 
    void* user_ptr; 
    void* real_ptr; 
    size_t user_size; 
    int origin;         // ALLOC_MALLOC = 1, ALLOC_PYMEM = 2
    const char* file; 
    int line; 
    int is_live; 
} mem_rec_t;

typedef struct { char type[32]; size_t size; } arena_snapshot_t;

// --- ESTADO GLOBAL ---
static mem_rec_t g_mem_db[MAX_MEM_RECORDS];
static int g_mem_ptr = 0;
static arena_snapshot_t g_arena_log[20]; 
static int g_arena_idx = 0;
static volatile long g_mem_lock = 0;

// --- SINCRONIZAÇÃO ATÔMICA ---
void _mem_lock() { while (InterlockedExchange(&g_mem_lock, 1)); }
void _mem_unlock() { InterlockedExchange(&g_mem_lock, 0); }

// --- MOTOR DE ALOCAÇÃO EXTENDIDA ---

void* soteria_malloc_ext(size_t size, int origin, const char* file, int line) {
    size_t total_size = size + (GUARD_SIZE * 2);
    unsigned char* real_p = (unsigned char*)(malloc)(total_size);
    if (!real_p) return NULL;

    *(unsigned long long*)real_p = NEXUS_CANARY;
    *(unsigned long long*)(real_p + GUARD_SIZE + size) = NEXUS_CANARY;

    void* user_p = (void*)(real_p + GUARD_SIZE);

    _mem_lock();
    if (g_mem_ptr < MAX_MEM_RECORDS) {
        g_mem_db[g_mem_ptr++] = (mem_rec_t){user_p, real_p, size, origin, file, line, 1};
    }
    _mem_unlock();

    soteria_arena_report_alloc("Hades_Arena", (origin == 2 ? "PyMem_Block" : "C_Malloc_Block"), size);
    
    return user_p;
}

void soteria_free_ext(void* ptr, int current_origin, const char* file, int line) {
    if (!ptr) return;

    _mem_lock();
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr == ptr) {
            if (!g_mem_db[i].is_live) {
                _mem_unlock();
                soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "DOUBLE_FREE",
                                 "Tentativa de liberar memoria ja desalocada.", file, line, "Free");
                return;
            }
            if (g_mem_db[i].origin != current_origin) {
                char detail[128];
                snprintf(detail, 127, "Conflito: Alocado via %s, liberado via %s.", 
                         (g_mem_db[i].origin == 2 ? "PyMem" : "Malloc"),
                         (current_origin == 2 ? "PyMem" : "Malloc"));
                _mem_unlock();
                soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "MIXED_ALLOCATOR_USAGE",
                                 detail, file, line, "Free");
                return;
            }
            g_mem_db[i].is_live = 0;
            void* real_p = g_mem_db[i].real_ptr;
            size_t sz = g_mem_db[i].user_size;
            _mem_unlock();

            memset(ptr, 0xDE, sz); 
            (free)(real_p);
            return;
        }
    }
    _mem_unlock();

    soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "INVALID_FREE",
                     "O endereço nao foi retornado por um alocador rastreado.", file, line, "Free");
}

void soteria_dump_leaks() {
    int leaks = 0;
    size_t total_bytes = 0;
    soteria_print_raw("\n@SOTERIA_BEGIN@\nTAG_MOTIVO: MEMORY_LEAK_REPORT\n");

    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].is_live) {
            char buf[256];
            snprintf(buf, 255, "TAG_LEAK_ENTRY: %s:%d | %zu bytes | Type: %d\n", 
                     g_mem_db[i].file, g_mem_db[i].line, g_mem_db[i].user_size, g_mem_db[i].origin);
            soteria_print_raw(buf);
            leaks++;
            total_bytes += g_mem_db[i].user_size;
        }
    }
    if (leaks > 0) {
        char summary[128];
        snprintf(summary, 127, "TAG_DETAIL: Detectados %d vazamentos de memoria (%zu bytes).\n", leaks, total_bytes);
        soteria_print_raw(summary);
    }
    soteria_print_raw("@SOTERIA_END@\n");
}

void soteria_validate(void* ptr, const char* file, int line) {
    if (!ptr) {
        soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "NULL_POINTER",
                         "Tentativa de usar ponteiro NULO.", file, line, "Validate");
        return;
    }
    int stack_anchor; 
    uintptr_t current_rsp = (uintptr_t)&stack_anchor;
    uintptr_t target = (uintptr_t)ptr;
    long long diff = (long long)(target - current_rsp);
    if (diff > -2097152 && diff < 2097152) {
        if (target > current_rsp) {
             soteria_dispatch(SOTERIA_FATAL, SOT_ERR_LOGIC, "DANGLING_STACK",
                             "Variavel de funcao ja encerrada sendo acessada.", file, line, "Validate");
        }
        return; 
    }
    _mem_lock();
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr == ptr) {
            if (!g_mem_db[i].is_live) {
                _mem_unlock();
                soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "USE_AFTER_FREE",
                                 "Tentativa de usar memoria ja liberada (Ponteiro Zumbi).", file, line, "Validate");
            }
            _mem_unlock();
            return; 
        }
    }
    _mem_unlock();
}

void soteria_arena_report_alloc(const char* arena_name, const char* obj_type, size_t size) {
    _mem_lock();
    strncpy(g_arena_log[g_arena_idx].type, obj_type, 31);
    g_arena_log[g_arena_idx].size = size;
    g_arena_idx = (g_arena_idx + 1) % 20;
    _mem_unlock();
}

void soteria_dump_arena_inventory() {
    char buf[256];
    for (int i = 0; i < 20; i++) {
        if (g_arena_log[i].size > 0) {
            snprintf(buf, 255, "TAG_ARENA_OBJ: %s | %zu bytes\n", 
                     g_arena_log[i].type, g_arena_log[i].size);
            soteria_print_raw(buf);
        }
    }
}

void soteria_access_probe(void* addr, const char* file, int line, int is_write) {
    static volatile void* g_last_addr = NULL;
    static volatile unsigned long g_last_tid = 0;
    unsigned long current_tid = GetCurrentThreadId();
    if (g_last_addr == addr && g_last_tid != current_tid) {
        soteria_dispatch(SOTERIA_WARN, SOT_ERR_LOGIC, "CONCURRENCY_HAZARD", 
                         "Condicao de Corrida detectada.", file, line, "Sentinel");
        g_last_addr = NULL; 
    } else {
        g_last_addr = addr;
        g_last_tid = current_tid;
    }
}

void* soteria_malloc(size_t size, const char* file, int line) {
    return soteria_malloc_ext(size, 1, file, line);
}

void soteria_free(void* ptr, const char* file, int line) {
    soteria_free_ext(ptr, 1, file, line);
}