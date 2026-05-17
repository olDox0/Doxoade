// Contrato de Segurança
// doxoade\tools\vulcan\native\soteria\soteria.c
#ifndef SOTERIA_H
#define SOTERIA_H

#include <stddef.h>
#include <stdlib.h>

typedef enum { SOTERIA_INFO, SOTERIA_WARN, SOTERIA_FATAL } soteria_level_t;
typedef enum { SOT_ERR_MEM, SOT_ERR_LOGIC, SOT_ERR_SIGNAL } soteria_err_t;

// API Global
void  soteria_init(int argc, char** argv);
void  soteria_push(const char* func, const char* file, int line);
void* soteria_malloc(size_t size, const char* file, int line);
void  soteria_free(void* ptr, const char* file, int line);
void  soteria_validate(void* ptr, const char* file, int line);
void  soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func);
void  soteria_mark(const char* msg, const char* file, int line);

// Internos para os módulos
void  soteria_payload(const char* level, const char* motive, const char* detail, const char* file, int line, const char* func);

#ifndef SOTERIA_CORE
    #define malloc(sz) soteria_malloc(sz, __FILE__, __LINE__)
    #define free(ptr)  soteria_free(ptr, __FILE__, __LINE__)
    #define SOTERIA_ENTER(fn) soteria_push(fn, __FILE__, __LINE__)
    #define SOTERIA_VALIDATE(ptr) soteria_validate(ptr, __FILE__, __LINE__)
#endif

#endif