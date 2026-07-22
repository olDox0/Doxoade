// doxoade/tools/hermes_systems/native/hermes_async_log.c
#define _GNU_SOURCE
#include "hermes_async_log.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>

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
#else
    #include <pthread.h>
    #include <unistd.h>
    #include <sys/time.h>
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
#endif

// ═══════════════════════════════════════════════════════════════════
// INSTÂNCIA GLOBAL DO LOGGER
// ═══════════════════════════════════════════════════════════════════
static AsyncLogger g_logger = {0};
static const char* g_level_names[] = {"DEBUG", "INFO", "WARN", "ERROR"};
static const char* g_level_colors[] = {"\x1b[90m", "\x1b[32m", "\x1b[33m", "\x1b[31m"};

// ═══════════════════════════════════════════════════════════════════
// ATOMIC OPERATIONS (Lock-Free)
// ═══════════════════════════════════════════════════════════════════
static inline uint32_t atomic_load(volatile uint32_t* ptr) {
#ifdef _WIN32
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
// THREAD CONSUMIDORA (Background I/O)
// ═══════════════════════════════════════════════════════════════════
static THREAD_FUNC logger_consumer_thread(void* arg) {
    (void)arg;
    
    while (g_logger.running) {
        uint32_t head = atomic_load(&g_logger.head);
        uint32_t tail = atomic_load(&g_logger.tail);
        
        if (head == tail) {
            // Buffer vazio, dorme um pouco para não consumir CPU
#ifdef _WIN32
            Sleep(1);  // 1ms
#else
            usleep(1000);  // 1ms
#endif
            continue;
        }
        
        // Processa todas as mensagens disponíveis
        while (tail != head) {
            LogEntry* entry = &g_logger.entries[tail];
            
            // Formata e imprime a mensagem
            fprintf(stderr, "%s[%s]%s [%.3fms] %s\n",
                    g_level_colors[entry->level],
                    g_level_names[entry->level],
                    "\x1b[0m",
                    (entry->timestamp_us - g_logger.start_time_us) / 1000.0,
                    entry->message);
            
            fflush(stderr);
            g_logger.total_logs++;
            
            // Avança o tail
            tail = (tail + 1) % LOG_QUEUE_SIZE;
            atomic_store(&g_logger.tail, tail);
        }
    }
    
    return 0;
}

// ═══════════════════════════════════════════════════════════════════
// INICIALIZAÇÃO E SHUTDOWN
// ═══════════════════════════════════════════════════════════════════
HERMES_LOG_EXPORT void hermes_log_init(void) {
    if (g_logger.running) return;  // Já inicializado
    
    memset(&g_logger, 0, sizeof(AsyncLogger));
    g_logger.start_time_us = GET_TIME_US();
    g_logger.running = true;
    
    // Cria a thread consumidora
    g_logger.thread_handle = (THREAD_HANDLE)THREAD_CREATE(logger_consumer_thread, NULL);
}

HERMES_LOG_EXPORT void hermes_log_shutdown(void) {
    if (!g_logger.running) return;
    
    g_logger.running = false;
    
    // Aguarda a thread terminar
    THREAD_JOIN((THREAD_HANDLE)g_logger.thread_handle);
    THREAD_CLOSE((THREAD_HANDLE)g_logger.thread_handle);
    
    // Imprime estatísticas finais
    fprintf(stderr, "\n[HERMES-LOG] Shutdown: %llu logs processed, %llu dropped\n",
            (unsigned long long)g_logger.total_logs,
            (unsigned long long)g_logger.dropped_logs);
}

// ═══════════════════════════════════════════════════════════════════
// PUSH (Produtor - Lock-Free)
// ═══════════════════════════════════════════════════════════════════
HERMES_LOG_EXPORT void hermes_log_push(uint8_t level, const char* fmt, ...) {
    if (!g_logger.running) return;
    
    uint32_t current_head = atomic_load(&g_logger.head);
    uint32_t next_head = (current_head + 1) % LOG_QUEUE_SIZE;
    uint32_t tail = atomic_load(&g_logger.tail);
    
    // 🛡️ BACKPRESSURE: Se o buffer estiver cheio, espera o C consumir (Nunca dropa!)
    while (next_head == tail) {
        #ifdef _WIN32
        Sleep(0);  // Yield para a thread do Windows
        #else
        sched_yield(); // Yield para o POSIX
        #endif
        tail = atomic_load(&g_logger.tail); // Relê o tail
    }
    
    LogEntry* entry = &g_logger.entries[current_head];
    va_list args;
    va_start(args, fmt);
    int len = vsnprintf(entry->message, LOG_MAX_MSG_LEN, fmt, args);
    va_end(args);
    
    if (len < 0) len = 0;
    if (len >= LOG_MAX_MSG_LEN) len = LOG_MAX_MSG_LEN - 1;
    entry->length = (uint32_t)len;
    entry->level = level;
    entry->timestamp_us = GET_TIME_US();
    
    atomic_store(&g_logger.head, next_head);
}

// ═══════════════════════════════════════════════════════════════════
// ESTATÍSTICAS
// ═══════════════════════════════════════════════════════════════════
HERMES_LOG_EXPORT void hermes_log_get_stats(uint64_t* total, uint64_t* dropped) {
    if (total) *total = g_logger.total_logs;
    if (dropped) *dropped = g_logger.dropped_logs;
}

// ═══════════════════════════════════════════════════════════════════
// API PYTHON (via ctypes)
// ═══════════════════════════════════════════════════════════════════
static char g_stats_buffer[256];

HERMES_LOG_EXPORT void hermes_log_py_init(void) {
    hermes_log_init();
}

HERMES_LOG_EXPORT void hermes_log_py_shutdown(void) {
    hermes_log_shutdown();
}

HERMES_LOG_EXPORT void hermes_log_py_push(const char* message, uint8_t level) {
    hermes_log_push(level, "%s", message);
}

HERMES_LOG_EXPORT const char* hermes_log_py_get_stats(void) {
    snprintf(g_stats_buffer, sizeof(g_stats_buffer),
             "{\"total\": %llu, \"dropped\": %llu, \"elapsed_ms\": %.3f}",
             (unsigned long long)g_logger.total_logs,
             (unsigned long long)g_logger.dropped_logs,
             (GET_TIME_US() - g_logger.start_time_us) / 1000.0);
    return g_stats_buffer;
}