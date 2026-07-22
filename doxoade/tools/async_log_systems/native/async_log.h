// doxoade/tools/async_log_systems/native/async_log.h
// Async Logger - Sistema Oficial de I/O Não-Bloqueante (PASC 13.0)
#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef _WIN32
#define ASYNC_LOG_EXPORT __declspec(dllexport)
#else
#define ASYNC_LOG_EXPORT __attribute__((visibility("default")))
#endif

// ═══════════════════════════════════════════════════════════════════
// CONFIGURAÇÕES DO RING BUFFER (Backpressure + Buffer Expandido)
// ═══════════════════════════════════════════════════════════════════
#define LOG_QUEUE_SIZE 32768          // 4x maior (32K slots)
#define LOG_BATCH_SIZE 256            // Processa 256 logs de uma vez
#define LOG_MAX_MSG_LEN 1024         // Suporta f-strings longas

#define LOG_LEVEL_DEBUG 0
#define LOG_LEVEL_INFO  1
#define LOG_LEVEL_WARN  2
#define LOG_LEVEL_ERROR 3

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURA DE ENTRADA DO LOG
// ═══════════════════════════════════════════════════════════════════
typedef struct {
    char message[LOG_MAX_MSG_LEN];
    uint32_t length;
    uint8_t level;
    uint64_t timestamp_us;
} LogEntry;

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURA DO LOGGER (SPSC Ring Buffer)
// ═══════════════════════════════════════════════════════════════════
typedef struct {
    LogEntry entries[LOG_QUEUE_SIZE];
    volatile uint32_t head;
    volatile uint32_t tail;
    volatile bool running;
    void* thread_handle;
    uint64_t start_time_us;
    uint64_t total_logs;
    uint64_t backpressure_count;  // Quantas vezes o Python precisou esperar
} AsyncLogger;

// ═══════════════════════════════════════════════════════════════════
// API PYTHON (via ctypes)
// ═══════════════════════════════════════════════════════════════════
ASYNC_LOG_EXPORT void async_log_init(void);
ASYNC_LOG_EXPORT void async_log_shutdown(void);
ASYNC_LOG_EXPORT void async_log_push(const char* message, uint8_t level);
ASYNC_LOG_EXPORT const char* async_log_get_stats(void);
ASYNC_LOG_EXPORT void async_log_drain(void);