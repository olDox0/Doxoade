// doxoade/tools/vulcan/diagnostic/soteria/src/soteria_mem.c
/*
 * SOTERIA MEM v5.0 — Arena Hades (Memory Tracking + Canary Guards)
 */
#define SOTERIA_CORE
#include "../include/soteria.h"
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <windows.h>

/* ═══════════════════════════════════════════════════════════════════
 * CONSTANTES
 * ═══════════════════════════════════════════════════════════════════ */
#define NEXUS_CANARY    0x4E455855534F4144ULL
#define GUARD_SIZE      16
#define MAX_MEM_RECORDS 4096
#define MAX_ARENA_LOG   64

/* ═══════════════════════════════════════════════════════════════════
 * TIMER (Windows / POSIX)
 * ═══════════════════════════════════════════════════════════════════ */
#ifdef _WIN32
#define GET_TIME_US() ({                                        \
    LARGE_INTEGER freq, count;                                  \
    QueryPerformanceFrequency(&freq);                           \
    QueryPerformanceCounter(&count);                            \
    (uint64_t)(count.QuadPart * 1000000 / freq.QuadPart);       \
})
#else
#include <sys/time.h>
#define GET_TIME_US() ({                                        \
    struct timeval tv;                                          \
    gettimeofday(&tv, NULL);                                    \
    (uint64_t)(tv.tv_sec * 1000000 + tv.tv_usec);              \
})
#endif

/* ═══════════════════════════════════════════════════════════════════
 * ESTRUTURAS
 * ═══════════════════════════════════════════════════════════════════ */
typedef struct {
    void       *user_ptr;
    void       *real_ptr;
    size_t      user_size;
    int         origin;
    const char *file;
    int         line;
    int         is_live;
} mem_rec_t;

typedef struct {
    char   type[32];
    size_t size;
} arena_snapshot_t;

/* ═══════════════════════════════════════════════════════════════════
 * ESTADO GLOBAL
 * ═══════════════════════════════════════════════════════════════════ */
static mem_rec_t       g_mem_db[MAX_MEM_RECORDS];
static int             g_mem_ptr = 0;
static arena_snapshot_t g_arena_log[MAX_ARENA_LOG];
static int             g_arena_idx = 0;
static volatile long   g_mem_lock = 0;

/* Contador global de race conditions (acessível pelo soteria_core.c) */
volatile LONG g_race_count = 0;

/* ═══════════════════════════════════════════════════════════════════
 * SINCRONIZAÇÃO
 * ═══════════════════════════════════════════════════════════════════ */
static void _mem_lock(void)   { while (InterlockedExchange(&g_mem_lock, 1)); }
static void _mem_unlock(void) { InterlockedExchange(&g_mem_lock, 0); }

/* ═══════════════════════════════════════════════════════════════════
 * PROTÓTIPOS INTERNOS
 * ═══════════════════════════════════════════════════════════════════ */
static void soteria_arena_report_alloc(const char *arena_name,
                                       const char *obj_type, size_t size);

/* ═══════════════════════════════════════════════════════════════════
 * ALOCAÇÃO COM CANÁRIOS
 * ═══════════════════════════════════════════════════════════════════ */
void *soteria_malloc_ext(size_t size, int origin,
                         const char *file, int line) {
    size_t total_size = size + (GUARD_SIZE * 2);
    unsigned char *real_p = (unsigned char *)(malloc)(total_size);
    if (!real_p) return NULL;

    /* Canário inicial e final */
    *(unsigned long long *)real_p = NEXUS_CANARY;
    *(unsigned long long *)(real_p + GUARD_SIZE + size) = NEXUS_CANARY;

    void *user_p = (void *)(real_p + GUARD_SIZE);

    _mem_lock();
    if (g_mem_ptr < MAX_MEM_RECORDS) {
        g_mem_db[g_mem_ptr++] = (mem_rec_t){
            user_p, real_p, size, origin, file, line, 1
        };
    }
    _mem_unlock();

    soteria_arena_report_alloc("Hades_Arena",
        (origin == 2 ? "PyMem_Block" : "C_Malloc_Block"), size);
    return user_p;
}

/* ═══════════════════════════════════════════════════════════════════
 * LIBERAÇÃO COM VERIFICAÇÃO DE CANÁRIO
 * ═══════════════════════════════════════════════════════════════════ */
void soteria_free_ext(void *ptr, int current_origin,
                      const char *file, int line) {
    if (!ptr) return;

    _mem_lock();
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr != ptr) continue;

        /* Double free */
        if (!g_mem_db[i].is_live) {
            _mem_unlock();
            soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "DOUBLE_FREE",
                "Tentativa de liberar memoria ja desalocada.",
                file, line, "Free");
            return;
        }

        /* Mixed allocator */
        if (g_mem_db[i].origin != current_origin) {
            char detail[128];
            snprintf(detail, 127, "Conflito: Alocado via %s, liberado via %s.",
                (g_mem_db[i].origin == 2 ? "PyMem" : "Malloc"),
                (current_origin == 2 ? "PyMem" : "Malloc"));
            _mem_unlock();
            soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM,
                "MIXED_ALLOCATOR_USAGE", detail, file, line, "Free");
            return;
        }

        /* Verificação de canário ANTES do free */
        unsigned char *rp = (unsigned char *)g_mem_db[i].real_ptr;
        size_t sz = g_mem_db[i].user_size;
        unsigned long long *canary_start = (unsigned long long *)rp;
        unsigned long long *canary_end   = (unsigned long long *)(rp + GUARD_SIZE + sz);

        if (*canary_start != NEXUS_CANARY || *canary_end != NEXUS_CANARY) {
            g_mem_db[i].is_live = 0;
            _mem_unlock();
            soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "SILENT_CORRUPTION",
                "Canario corrompido detectado no momento do free! "
                "Overflow ocorreu durante uso.",
                file, line, "Free");
            return;
        }

        /* Liberação segura */
        g_mem_db[i].is_live = 0;
        void *real_p = g_mem_db[i].real_ptr;
        _mem_unlock();

        memset(ptr, 0xDE, sz);
        (free)(real_p);
        return;
    }
    _mem_unlock();

    soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "INVALID_FREE",
        "O endereco nao foi retornado por um alocador rastreado.",
        file, line, "Free");
}

/* ═══════════════════════════════════════════════════════════════════
 * VALIDAÇÃO DE PONTEIRO
 * ═══════════════════════════════════════════════════════════════════ */
void soteria_validate(void *ptr, const char *file, int line) {
    if (!ptr) {
        soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "NULL_POINTER",
            "Tentativa de usar ponteiro NULO.", file, line, "Validate");
        return;
    }

    _mem_lock();
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].user_ptr != ptr || !g_mem_db[i].is_live) continue;

        unsigned char *rp = (unsigned char *)g_mem_db[i].real_ptr;
        unsigned long long *cs = (unsigned long long *)rp;
        unsigned long long *ce = (unsigned long long *)(rp + GUARD_SIZE + g_mem_db[i].user_size);

        if (*cs != NEXUS_CANARY) {
            _mem_unlock();
            soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "SILENT_CORRUPTION",
                "Canario INICIAL corrompido! Buffer overflow retrogrado.",
                file, line, "Validate");
            return;
        }
        if (*ce != NEXUS_CANARY) {
            _mem_unlock();
            soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "SILENT_CORRUPTION",
                "Canario FINAL corrompido! Buffer overflow frontal.",
                file, line, "Validate");
            return;
        }

        /* Dangling stack check */
        int stack_anchor;
        uintptr_t current_rsp = (uintptr_t)&stack_anchor;
        uintptr_t target = (uintptr_t)ptr;
        long long diff = (long long)(target - current_rsp);
        if (diff > -2097152 && diff < 2097152 && target > current_rsp) {
            _mem_unlock();
            soteria_dispatch(SOTERIA_FATAL, SOT_ERR_LOGIC, "DANGLING_STACK",
                "Variavel de funcao ja encerrada sendo acessada.",
                file, line, "Validate");
            return;
        }

        _mem_unlock();
        return;
    }
    _mem_unlock();

    soteria_dispatch(SOTERIA_WARN, SOT_ERR_MEM, "UNKNOWN_POINTER",
        "Ponteiro nao rastreado pela Arena Hades.", file, line, "Validate");
}

/* ═══════════════════════════════════════════════════════════════════
 * DUMP DE LEAKS
 * ═══════════════════════════════════════════════════════════════════ */
void soteria_dump_leaks(void) {
    _mem_lock();
    int leaks = 0;
    size_t total_bytes = 0;

    soteria_print_raw("\n@SOTERIA_BEGIN@\nTAG_MOTIVO: MEMORY_LEAK_REPORT\n");
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].is_live) {
            char buf[256];
            snprintf(buf, 255, "TAG_LEAK_ENTRY: %s:%d | %zu bytes | Type: %d\n",
                g_mem_db[i].file, g_mem_db[i].line,
                g_mem_db[i].user_size, g_mem_db[i].origin);
            soteria_print_raw(buf);
            leaks++;
            total_bytes += g_mem_db[i].user_size;
        }
    }
    if (leaks > 0) {
        char summary[128];
        snprintf(summary, 127,
            "TAG_DETAIL: Detectados %d vazamentos (%zu bytes).\n",
            leaks, total_bytes);
        soteria_print_raw(summary);
    }
    soteria_print_raw("@SOTERIA_END@\n");
    _mem_unlock();
}

/* ═══════════════════════════════════════════════════════════════════
 * ARENA INVENTORY
 * ═══════════════════════════════════════════════════════════════════ */
static void soteria_arena_report_alloc(const char *arena_name,
                                       const char *obj_type, size_t size) {
    (void)arena_name;
    _mem_lock();
    strncpy(g_arena_log[g_arena_idx].type, obj_type, 31);
    g_arena_log[g_arena_idx].type[31] = '\0';
    g_arena_log[g_arena_idx].size = size;
    g_arena_idx = (g_arena_idx + 1) % MAX_ARENA_LOG;
    _mem_unlock();
}

void soteria_dump_arena_inventory(void) {
    char buf[256];
    for (int i = 0; i < MAX_ARENA_LOG; i++) {
        if (g_arena_log[i].size > 0) {
            snprintf(buf, 255, "TAG_ARENA_OBJ: %s | %zu bytes\n",
                g_arena_log[i].type, g_arena_log[i].size);
            soteria_print_raw(buf);
        }
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * ACCESS PROBE (Race Condition Detection + Rate Limiting)
 * ═══════════════════════════════════════════════════════════════════ */
void soteria_access_probe(void *addr, const char *file, int line, int is_write) {
    static volatile long long g_last_access_time  = 0;
    static void *volatile     g_last_access_addr  = NULL;
    static volatile LONG      g_last_access_write = 0;
    static volatile LONG      g_displayed_count   = 0;
    #define MAX_DISPLAY 5

    if (!addr) {
        soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "NULL_POINTER",
            "Tentativa de acessar endereco NULO.", file, line, "AccessProbe");
        return;
    }

    long long current_time = (long long)GET_TIME_US();

    void *prev_addr = InterlockedExchangePointer(
        (void *volatile *)&g_last_access_addr, addr);
    long long prev_time = InterlockedExchange64(
        &g_last_access_time, current_time);
    int prev_write = (int)InterlockedExchange(
        &g_last_access_write, (LONG)is_write);

    if (prev_addr == addr && (current_time - prev_time) < 100) {
        long count     = InterlockedIncrement(&g_race_count);
        long displayed = InterlockedIncrement(&g_displayed_count);

        /* Log em arquivo (sempre) */
        char log_buf[512];
        snprintf(log_buf, 511,
            "[%ld] RACE: addr=%p write=%d prev_write=%d delta=%lldus loc=%s:%d\n",
            count, addr, is_write, prev_write,
            current_time - prev_time, file, line);
        FILE *log_file = fopen(".doxoade/metalcraft/logs/race_conditions.log", "a");
        if (log_file) {
            fprintf(log_file, "%s", log_buf);
            fclose(log_file);
        }

        /* Console: apenas primeiras N ocorrências */
        if (displayed <= MAX_DISPLAY) {
            char detail[256];
            snprintf(detail, 255,
                "Acesso concorrente: addr=%p, write=%d, prev_write=%d, delta=%lldus",
                addr, is_write, prev_write, current_time - prev_time);
            soteria_dispatch(SOTERIA_WARN, SOT_ERR_LOGIC, "CONCURRENCY_HAZARD",
                detail, file, line, "AccessProbe");
        }
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * WRAPPERS SIMPLIFICADOS
 * ═══════════════════════════════════════════════════════════════════ */
void *soteria_malloc(size_t size, const char *file, int line) {
    return soteria_malloc_ext(size, 1, file, line);
}

void soteria_free(void *ptr, const char *file, int line) {
    soteria_free_ext(ptr, 1, file, line);
}