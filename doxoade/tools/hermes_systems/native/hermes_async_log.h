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
#define LOG_MAX_MSG_LEN 512
#define LOG_LEVEL_DEBUG 0
#define LOG_LEVEL_INFO  1
#define LOG_LEVEL_WARN  2
#define LOG_LEVEL_ERROR 3

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
    hermes_thread_t thread_handle; // 🛑 Adaptativo: void* no Windows, pthread_t no Linux/Android
    uint64_t start_time_us;        
    uint64_t total_logs;           
    uint64_t dropped_logs;         
} AsyncLogger;

HERMES_LOG_EXPORT void hermes_log_init(void);
HERMES_LOG_EXPORT void hermes_log_shutdown(void);
HERMES_LOG_EXPORT void hermes_log_push(uint8_t level, const char* fmt, ...);
HERMES_LOG_EXPORT void hermes_log_get_stats(uint64_t* total, uint64_t* dropped);

#define HERMES_LOG_DEBUG(fmt, ...) hermes_log_push(LOG_LEVEL_DEBUG, fmt, ##__VA_ARGS__)
#define HERMES_LOG_INFO(fmt, ...)  hermes_log_push(LOG_LEVEL_INFO, fmt, ##__VA_ARGS__)
#define HERMES_LOG_WARN(fmt, ...)  hermes_log_push(LOG_LEVEL_WARN, fmt, ##__VA_ARGS__)
#define HERMES_LOG_ERROR(fmt, ...) hermes_log_push(LOG_LEVEL_ERROR, fmt, ##__VA_ARGS__)

HERMES_LOG_EXPORT void hermes_log_py_init(void);
HERMES_LOG_EXPORT void hermes_log_py_shutdown(void);
HERMES_LOG_EXPORT void hermes_log_py_push(const char* message, uint8_t level);
HERMES_LOG_EXPORT const char* hermes_log_py_get_stats(void);
