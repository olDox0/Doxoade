// doxoade/tools/hermes_systems/native/hermes_async_log.h
#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef _WIN32
#define HERMES_LOG_EXPORT __declspec(dllexport)
typedef void* hermes_thread_t;
#else
#define HERMES_LOG_EXPORT __attribute__((visibility("default")))
#include <pthread.h>
typedef pthread_t hermes_thread_t;
#endif

#define LOG_QUEUE_SIZE 8192
#define LOG_MAX_MSG_LEN 4096 // Aumentado para suportar linhas longas do Rich/Click
#define LOG_LEVEL_DEBUG 0
#define LOG_LEVEL_INFO  1
#define LOG_LEVEL_WARN  2
#define LOG_LEVEL_ERROR 3
#define LOG_LEVEL_RAW   4 // Novo nível: Repasse cru de bytes (sem prefixo)

typedef struct {
    char message[LOG_MAX_MSG_LEN];
    uint32_t length;
    uint8_t level;
    uint64_t timestamp_us;
} LogEntry;

typedef struct {
    LogEntry entries[LOG_QUEUE_SIZE];
    volatile uint32_t head;
    volatile uint32_t tail;
    volatile bool running;
    hermes_thread_t thread_handle;
    uint64_t start_time_us;
    uint64_t total_logs;
    uint64_t dropped_logs;
    int output_fd; // -1 = stderr, >0 = socket fd
} AsyncLogger;

HERMES_LOG_EXPORT void hermes_log_init(void);
HERMES_LOG_EXPORT void hermes_log_shutdown(void);
HERMES_LOG_EXPORT void hermes_log_push(uint8_t level, const char* fmt, ...);
HERMES_LOG_EXPORT void hermes_log_get_stats(uint64_t* total, uint64_t* dropped);

// 🚀 NOVAS FUNÇÕES PARA O DAEMON (Pilar 2)
HERMES_LOG_EXPORT void hermes_log_set_output_fd(int fd);
HERMES_LOG_EXPORT void hermes_log_push_raw(const char* data, uint32_t len);

// API Python
HERMES_LOG_EXPORT void hermes_log_py_init(void);
HERMES_LOG_EXPORT void hermes_log_py_shutdown(void);
HERMES_LOG_EXPORT void hermes_log_py_push(const char* message, uint8_t level);
HERMES_LOG_EXPORT void hermes_log_py_push_raw(const char* data, uint32_t len);
HERMES_LOG_EXPORT const char* hermes_log_py_get_stats(void);
