// doxoade\tools\vulcan\diagnostic\soteria\include\soteria.h
#ifndef SOTERIA_H
#define SOTERIA_H

#include <stddef.h>
#include <stdlib.h>
#include <stdint.h>
#include <windows.h>

#ifdef SOTERIA_CORE
    // Se estamos compilando o núcleo da Sotéria, as macros de rastro são vazias para evitar recursão
    #define SOTERIA_ENTER(fn) 
    #define SOTERIA_VALIDATE(ptr)
#endif

// --- SINALIZADORES GLOBAIS ---
extern volatile long g_forensic_lock;
extern volatile long g_forensic_active;

// --- DEFINIÇÕES DE TAXONOMIA ---

typedef enum { 
    SOTERIA_INFO, 
    SOTERIA_WARN, 
    SOTERIA_FATAL 
} soteria_level_t;

typedef enum { 
    SOT_ERR_MEM, 
    SOT_ERR_LOGIC, 
    SOT_ERR_SIGNAL, 
    SOT_ERR_FREESTYLE 
} soteria_err_t;

// Identificadores de alocadores para detecção de Mixed Usage
typedef enum {
    ALLOC_MALLOC = 1,
    ALLOC_PYMEM  = 2,
    ALLOC_NATIVE_NEW = 3 
} alloc_origin_t;

typedef enum {
    SOT_SYNC_BARRIER, 
    SOT_SYNC_MUTEX, 
    SOT_SYNC_ATOMIC 
} sot_sync_t;

// --- API DE GERENCIAMENTO DE MEMÓRIA (HADES ARENA) ---

void* soteria_malloc_ext(size_t size, int origin, const char* file, int line);
void  soteria_free_ext(void* ptr, int origin, const char* file, int line);
void  soteria_validate(void* ptr, const char* file, int line);
void  soteria_dump_leaks(); // Relatório final de vazamentos
void  soteria_dump_arena_inventory();

// --- API DE RASTREIO E FLUXO (HORUS ENGINE) ---

void  soteria_init(int argc, char** argv);
void  soteria_push(const char* func, const char* file, int line);
void  soteria_mark(const char* msg, const char* file, int line);
void  soteria_mark_var(const char* var_name, long long value, const char* file, int line);
void  soteria_io_trace(const char* op, const char* payload, const char* file, int line);
void  soteria_dump_stack_trace();

// --- SISTEMA DE PÂNICO E HARDWARE ---

void  soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func);
void  soteria_dump_hardware_state();
void  soteria_print_raw(const char* msg);

// API de Sentinela (Race Condition)
void  soteria_access_probe(void* addr, const char* file, int line, int is_write);

// --- MACROS TÁTICAS ---

// Alerta customizado para falhas de lógica de negócio
#define SOTERIA_ALERT(id, detail) \
    soteria_dispatch(SOTERIA_FATAL, SOT_ERR_FREESTYLE, id, detail, __FILE__, __LINE__, __func__)

#ifndef SOTERIA_CORE
    // Redirecionamento transparente para captura de contexto em C Puro
    #undef malloc
    #define malloc(sz) soteria_malloc_ext(sz, ALLOC_MALLOC, __FILE__, __LINE__)
    
    #undef free
    #define free(ptr)  soteria_free_ext(ptr, ALLOC_MALLOC, __FILE__, __LINE__)

    // Atalhos para vigilância
    #define SOTERIA_WATCH(var) soteria_access_probe((void*)&var, __FILE__, __LINE__, 1)
    #define SOTERIA_ENTER(fn)  soteria_push(fn, __FILE__, __LINE__)
    #define SOTERIA_VALIDATE(ptr) soteria_validate(ptr, __FILE__, __LINE__)
#endif

#endif // SOTERIA_H