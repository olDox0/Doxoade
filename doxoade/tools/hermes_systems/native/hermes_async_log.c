// doxoade/tools/hermes_systems/native/hermes_async_log.c
#define _GNU_SOURCE
#include "hermes_async_log.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>

#ifdef _WIN32
#include <winsock2.h>
#include <windows.h>
#include <process.h>
#pragma comment(lib, "ws2_32.lib")
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
#define WRITE_FD(fd, data, len) send((SOCKET)fd, data, len, 0)
#else
#include <pthread.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/socket.h>
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
#define WRITE_FD(fd, data, len) write(fd, data, len)
#endif

static AsyncLogger g_logger = {0};
static const char* g_level_names[] = {"DEBUG", "INFO", "WARN", "ERROR", "RAW"};
static const char* g_level_colors[] = {"\x1b[90m", "\x1b[32m", "\x1b[33m", "\x1b[31m", ""};

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

static THREAD_FUNC logger_consumer_thread(void* arg) {
    (void)arg;
    while (g_logger.running) {
        uint32_t head = atomic_load(&g_logger.head);
        uint32_t tail = atomic_load(&g_logger.tail);

        if (head == tail) {
#ifdef _WIN32
            Sleep(1);
#else
            usleep(1000);
#endif
            continue;
        }

        while (tail != head) {
            LogEntry* entry = &g_logger.entries[tail];
            
            if (g_logger.output_fd > 0) {
                // 🚀 MODO DAEMON: Envia direto para o Socket TCP
                if (entry->level == LOG_LEVEL_RAW) {
                    // Repasse cru (bytes do Click/Rich)
                    WRITE_FD(g_logger.output_fd, entry->message, entry->length);
                } else {
                    // Log formatado do sistema
                    char formatted[LOG_MAX_MSG_LEN + 64];
                    int len = snprintf(formatted, sizeof(formatted), "%s[%s]%s [%.3fms] %s\n",
                        g_level_colors[entry->level],
                        g_level_names[entry->level],
                        "\x1b[0m",
                        (entry->timestamp_us - g_logger.start_time_us) / 1000.0,
                        entry->message);
                    if (len > 0) WRITE_FD(g_logger.output_fd, formatted, len);
                }
            } else {
                // MODO LOCAL: Escreve no stderr do processo
                if (entry->level == LOG_LEVEL_RAW) {
                    fwrite(entry->message, 1, entry->length, stderr);
                } else {
                    fprintf(stderr, "%s[%s]%s [%.3fms] %s\n",
                        g_level_colors[entry->level],
                        g_level_names[entry->level],
                        "\x1b[0m",
                        (entry->timestamp_us - g_logger.start_time_us) / 1000.0,
                        entry->message);
                }
                fflush(stderr);
            }

            g_logger.total_logs++;
            tail = (tail + 1) % LOG_QUEUE_SIZE;
            atomic_store(&g_logger.tail, tail);
        }
    }
    return 0;
}

HERMES_LOG_EXPORT void hermes_log_init(void) {
    if (g_logger.running) return;
    memset(&g_logger, 0, sizeof(AsyncLogger));
    g_logger.start_time_us = GET_TIME_US();
    g_logger.output_fd = -1; // Padrão: stderr
    g_logger.running = true;

#ifdef _WIN32
    g_logger.thread_handle = (hermes_thread_t)_beginthreadex(NULL, 0, logger_consumer_thread, NULL, 0, NULL);
#else
    pthread_create(&g_logger.thread_handle, NULL, logger_consumer_thread, NULL);
#endif
}

static char g_stats_buffer[256]; // 🛑 DECLARADO ANTES DA FUNÇÃO!

HERMES_LOG_EXPORT const char* hermes_log_py_get_stats(void) {
    snprintf(g_stats_buffer, sizeof(g_stats_buffer),
             "{\"total\": %llu, \"dropped\": %llu, \"elapsed_ms\": %.3f}",
             (unsigned long long)g_logger.total_logs,
             (unsigned long long)g_logger.dropped_logs,
             (GET_TIME_US() - g_logger.start_time_us) / 1000.0);
    return g_stats_buffer;
}

HERMES_LOG_EXPORT void hermes_log_set_output_fd(int fd) {
    g_logger.output_fd = fd;
}

HERMES_LOG_EXPORT void hermes_log_push(uint8_t level, const char* fmt, ...) {
    if (!g_logger.running) return;
    uint32_t current_head = atomic_load(&g_logger.head);
    uint32_t next_head = (current_head + 1) % LOG_QUEUE_SIZE;
    uint32_t tail = atomic_load(&g_logger.tail);

    while (next_head == tail) { // Queue full
#ifdef _WIN32
        Sleep(0);
#else
        sched_yield();
#endif
        tail = atomic_load(&g_logger.tail);
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

HERMES_LOG_EXPORT void hermes_log_push_raw(const char* data, uint32_t len) {
    if (!g_logger.running || len == 0) return;
    uint32_t current_head = atomic_load(&g_logger.head);
    uint32_t next_head = (current_head + 1) % LOG_QUEUE_SIZE;
    uint32_t tail = atomic_load(&g_logger.tail);

    while (next_head == tail) {
#ifdef _WIN32
        Sleep(0);
#else
        sched_yield();
#endif
        tail = atomic_load(&g_logger.tail);
    }

    LogEntry* entry = &g_logger.entries[current_head];
    uint32_t copy_len = (len > LOG_MAX_MSG_LEN) ? LOG_MAX_MSG_LEN : len;
    memcpy(entry->message, data, copy_len);
    
    entry->length = copy_len;
    entry->level = LOG_LEVEL_RAW;
    entry->timestamp_us = GET_TIME_US();
    atomic_store(&g_logger.head, next_head);
}

// ... (Funções de shutdown e stats permanecem iguais) ...
HERMES_LOG_EXPORT void hermes_log_shutdown(void) {
    if (!g_logger.running) return;
    g_logger.running = false;
#ifdef _WIN32
    WaitForSingleObject((HANDLE)g_logger.thread_handle, INFINITE);
    CloseHandle((HANDLE)g_logger.thread_handle);
#else
    pthread_join(g_logger.thread_handle, NULL);
#endif
}

HERMES_LOG_EXPORT void hermes_log_py_init(void) { hermes_log_init(); }
HERMES_LOG_EXPORT void hermes_log_py_shutdown(void) { hermes_log_shutdown(); }
HERMES_LOG_EXPORT void hermes_log_py_push(const char* message, uint8_t level) {
    hermes_log_push(level, "%s", message);
}
HERMES_LOG_EXPORT void hermes_log_py_push_raw(const char* data, uint32_t len) {
    hermes_log_push_raw(data, len);
}
