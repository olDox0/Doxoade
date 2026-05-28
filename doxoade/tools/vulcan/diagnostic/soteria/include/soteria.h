// doxoade\tools\vulcan\diagnostic\soteria\include\soteria.h
#ifndef SOTERIA_H
#define SOTERIA_H
#include <stddef.h>
#include <stdlib.h>
#include <stdint.h>
#include <windows.h>

#ifdef SOTERIA_CORE
    // Se estamos compilando o núcleo da Sotéria, as macros de rastro são vazias
    #define SOTERIA_ENTER(fn) 
    #define SOTERIA_VALIDATE(ptr)
#endif

extern volatile long g_forensic_lock;
extern volatile long g_forensic_active;

typedef enum { SOTERIA_INFO, SOTERIA_WARN, SOTERIA_FATAL } soteria_level_t;
typedef enum { SOT_ERR_MEM, SOT_ERR_LOGIC, SOT_ERR_SIGNAL, SOT_ERR_FREESTYLE } soteria_err_t;
typedef enum { SOT_SYNC_BARRIER, SOT_SYNC_MUTEX, SOT_SYNC_ATOMIC } sot_sync_t;

// Macro para o desenvolvedor gritar um erro customizado
#define SOTERIA_ALERT(id, detail) \
    soteria_dispatch(SOTERIA_FATAL, SOT_ERR_FREESTYLE, id, detail, __FILE__, __LINE__, __func__)

// API Global
void  soteria_payload(const char* level, const char* motive, const char* detail, const char* file, int line, const char* func);
void  soteria_init(int argc, char** argv);
void  soteria_push(const char* func, const char* file, int line);
void* soteria_malloc(size_t size, const char* file, int line);
void  soteria_free(void* ptr, const char* file, int line);
void  soteria_validate(void* ptr, const char* file, int line);
void  soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func);
void  soteria_mark(const char* msg, const char* file, int line);

// API de Threads
void soteria_thread_register(const char* name);
void soteria_sync_mark(sot_sync_t type, void* sync_obj);
void soteria_mark_ext(const char* msg, const char* file, int line, unsigned long tid);

// Internos para os módulos
void  soteria_payload(const char* level, const char* motive, const char* detail, const char* file, int line, const char* func);

// API de Rastro
void soteria_init(int argc, char** argv);
void soteria_mark(const char* msg, const char* file, int line);
void soteria_push(const char* func, const char* file, int line);

// API de Sentinela (Race Condition)
void soteria_access_probe(void* addr, const char* file, int line, int is_write);

// Função para imprimir a pilha no momento do desastre
void soteria_dump_stack_trace();
void soteria_payload(const char* level, const char* motive, const char* detail, const char* file, int line, const char* func);
void soteria_arena_report_alloc(const char* arena_name, const char* obj_type, size_t size);
void soteria_validate(void* ptr, const char* file, int line);
void soteria_dump_arena_inventory();
void soteria_dump_hardware_state();
void soteria_mark_var(const char* var_name, long long value, const char* file, int line);
void soteria_io_trace(const char* op, const char* file, int line);
void soteria_print_raw(const char* msg);

#ifndef SOTERIA_CORE
    #define malloc(sz) soteria_malloc(sz, __FILE__, __LINE__)
    #define free(ptr)  soteria_free(ptr, __FILE__, __LINE__)
    #define SOTERIA_WATCH(var) soteria_access_probe((void*)&var, __FILE__, __LINE__, 1)
    #define SOTERIA_ENTER(fn) soteria_push(fn, __FILE__, __LINE__)
    #define SOTERIA_VALIDATE(ptr) soteria_validate(ptr, __FILE__, __LINE__)
#endif

#endif