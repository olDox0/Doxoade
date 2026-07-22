// doxoade/tools/async_log_systems/native/async_log.c
// Async Logger - Implementação Oficial com Backpressure (PASC 13.0)
#define _GNU_SOURCE
#include "async_log.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#ifdef _WIN32
#include <windows.h>
#include <process.h>
#define THREAD_FUNC unsigned __stdcall
#define THREAD_HANDLE HANDLE
#define THREAD_CREATE(func, arg) _beginthreadex(NULL, 0, func, arg, 0, NULL)
#define THREAD_JOIN(handle) WaitForSingleObject((HANDLE)handle, INFINITE)
#define THREAD_CLOSE(handle) CloseHandle((HANDLE)handle)
#define GET_TIME_US() ({ \
    LARGE_INTEGER freq, count; \
    QueryPerformanceFrequency(&freq); \
    QueryPerformanceCounter(&count); \
    (uint64_t)(count.QuadPart * 1000000 / freq.QuadPart); \
})
#define YIELD_CPU() Sleep(0)
#else
#include <pthread.h>
#include <unistd.h>
#include <sys/time.h>
#include <sched.h>
#define THREAD_FUNC void*
#define THREAD_HANDLE pthread_t
#define THREAD_CREATE(func, arg) ({ \
    pthread_t tid; \
    pthread_create(&tid, NULL, func, arg); \
    tid; \
})
#define THREAD_JOIN(handle) pthread_join(handle, NULL)
#define THREAD_CLOSE(handle) (void)0
#define GET_TIME_US() ({ \
    struct timeval tv; \
    gettimeofday(&tv, NULL); \
    (uint64_t)(tv.tv_sec * 1000000 + tv.tv_usec); \
})
#define YIELD_CPU() sched_yield()
#endif

// ═══════════════════════════════════════════════════════════════════
// INSTÂNCIA GLOBAL
// ═══════════════════════════════════════════════════════════════════
static AsyncLogger g_logger = {0};
static const char* g_level_names[]  = {"DEBUG", "INFO", "WARN", "ERROR"};
static const char* g_level_colors[] = {"\x1b[90m", "\x1b[32m", "\x1b[33m", "\x1b[31m"};

// ═══════════════════════════════════════════════════════════════════
// ATOMIC OPERATIONS (Lock-Free) - Windows x64 Compatible
// ═══════════════════════════════════════════════════════════════════
static inline uint32_t atomic_load(volatile uint32_t* ptr) {
#ifdef _WIN32
    // Cast para volatile LONG* (InterlockedCompareExchange espera signed)
    return (uint32_t)InterlockedCompareExchange((volatile LONG*)ptr, 0, 0);
#else
    return __atomic_load_n(ptr, __ATOMIC_ACQUIRE);
#endif
}

static inline void atomic_store(volatile uint32_t* ptr, uint32_t val) {
#ifdef _WIN32
    InterlockedExchange((volatile LONG*)ptr, (LONG)val);
#else
    __atomic_store_n(ptr, val, __ATOMIC_RELEASE);
#endif
}

static inline bool atomic_cas(volatile uint32_t* ptr, uint32_t* expected, uint32_t desired) {
#ifdef _WIN32
    uint32_t old = (uint32_t)InterlockedCompareExchange((volatile LONG*)ptr, (LONG)desired, (LONG)*expected);
    if (old == *expected) return true;
    *expected = old;
    return false;
#else
    return __atomic_compare_exchange_n(ptr, expected, desired, false,
                                       __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
#endif
}
// ═══════════════════════════════════════════════════════════════════
// THREAD CONSUMIDORA (Background I/O) - BATCH FLUSHING
// ═══════════════════════════════════════════════════════════════════
#define BATCH_SIZE 256  // Acumula até 256 logs antes de flushar

static THREAD_FUNC logger_consumer_thread(void* arg) {
    (void)arg;
    
    // Buffer de batch (alocado uma vez)
    char batch_buffer[BATCH_SIZE * (LOG_MAX_MSG_LEN + 128)];
    int batch_count = 0;
    size_t batch_offset = 0;
    
    while (g_logger.running || batch_count > 0) {
        uint32_t head = atomic_load(&g_logger.head);
        uint32_t tail = atomic_load(&g_logger.tail);
        
        if (head == tail && batch_count == 0) {
            // Buffer vazio e batch vazio, dorme um pouco
#ifdef _WIN32
            Sleep(1);
#else
            usleep(1000);
#endif
            continue;
        }
        
        // Processa logs disponíveis, acumulando no batch
        while (tail != head && batch_count < BATCH_SIZE) {
            LogEntry* entry = &g_logger.entries[tail];
            
            // Formata a mensagem no buffer de batch
            int written = snprintf(batch_buffer + batch_offset, 
                                   sizeof(batch_buffer) - batch_offset,
                                   "%s[%s]%s [%.3fms] %s\n",
                                   g_level_colors[entry->level],
                                   g_level_names[entry->level],
                                   "\x1b[0m",
                                   (entry->timestamp_us - g_logger.start_time_us) / 1000.0,
                                   entry->message);
            
            if (written > 0) {
                batch_offset += written;
                batch_count++;
            }
            
            g_logger.total_logs++;
            tail = (tail + 1) % LOG_QUEUE_SIZE;
        }
        
        // Atualiza o tail uma única vez por batch
        atomic_store(&g_logger.tail, tail);
        
        // Flush do batch inteiro (uma única syscall)
        if (batch_count > 0) {
            fwrite(batch_buffer, 1, batch_offset, stderr);
            fflush(stderr);
            
            batch_count = 0;
            batch_offset = 0;
        }
    }
    
    return 0;
}

// ═══════════════════════════════════════════════════════════════════
// INIT / SHUTDOWN
// ═══════════════════════════════════════════════════════════════════
ASYNC_LOG_EXPORT void async_log_init(void) {
    if (g_logger.running) return;
    memset(&g_logger, 0, sizeof(AsyncLogger));
    g_logger.start_time_us = GET_TIME_US();
    g_logger.running = true;
    g_logger.thread_handle = (THREAD_HANDLE)THREAD_CREATE(logger_consumer_thread, NULL);
}

ASYNC_LOG_EXPORT void async_log_shutdown(void) {
    if (!g_logger.running) return;
    g_logger.running = false;
    THREAD_JOIN((THREAD_HANDLE)g_logger.thread_handle);
    THREAD_CLOSE((THREAD_HANDLE)g_logger.thread_handle);
    
    fprintf(stderr, "\n\x1b[90m[ASYNC-LOG] Shutdown: %llu logs, %llu backpressures\x1b[0m\n",
            (unsigned long long)g_logger.total_logs,
            (unsigned long long)g_logger.backpressure_count);
}

// ═══════════════════════════════════════════════════════════════════
// DRENO SÍNCRONO (Espera o buffer esvaziar)
// ═══════════════════════════════════════════════════════════════════
ASYNC_LOG_EXPORT void async_log_drain(void) {
    if (!g_logger.running) return;
    // Spin-wait: Cede a CPU até que a thread C consuma tudo (head == tail)
    while (atomic_load(&g_logger.head) != atomic_load(&g_logger.tail)) {
        YIELD_CPU(); 
    }
    fflush(stderr); // Garante que o último lote foi para o terminal
}

// ═══════════════════════════════════════════════════════════════════
// PUSH (Produtor com BACKPRESSURE - Nunca dropa!)
// ═══════════════════════════════════════════════════════════════════
ASYNC_LOG_EXPORT void async_log_push(const char* message, uint8_t level) {
    if (!g_logger.running) return;
    
    uint32_t current_head = atomic_load(&g_logger.head);
    uint32_t next_head = (current_head + 1) % LOG_QUEUE_SIZE;
    uint32_t tail = atomic_load(&g_logger.tail);
    
    // 🛡️ BACKPRESSURE: Espera o C consumir (Nunca dropa mensagens!)
    while (next_head == tail) {
        g_logger.backpressure_count++;
        YIELD_CPU();
        tail = atomic_load(&g_logger.tail);
    }
    
    LogEntry* entry = &g_logger.entries[current_head];
    int len = snprintf(entry->message, LOG_MAX_MSG_LEN, "%s", message);
    if (len < 0) len = 0;
    if (len >= LOG_MAX_MSG_LEN) len = LOG_MAX_MSG_LEN - 1;
    
    entry->length = (uint32_t)len;
    entry->level = level;
    entry->timestamp_us = GET_TIME_US();
    
    atomic_store(&g_logger.head, next_head);
}

// ═══════════════════════════════════════════════════════════════════
// STATS
// ═══════════════════════════════════════════════════════════════════
static char g_stats_buffer[256];
ASYNC_LOG_EXPORT const char* async_log_get_stats(void) {
    snprintf(g_stats_buffer, sizeof(g_stats_buffer),
             "{\"total\": %llu, \"backpressure\": %llu, \"elapsed_ms\": %.3f}",
             (unsigned long long)g_logger.total_logs,
             (unsigned long long)g_logger.backpressure_count,
             (GET_TIME_US() - g_logger.start_time_us) / 1000.0);
    return g_stats_buffer;
}