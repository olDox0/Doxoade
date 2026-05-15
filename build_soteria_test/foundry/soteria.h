// Contrato de Segurança
// doxoade\tools\vulcan\native\soteria\soteria.c

#ifndef SOTERIA_H
#define SOTERIA_H

#include <stddef.h>

// Níveis de Diagnóstico (OSL-15)
typedef enum {
    SOTERIA_INFO,
    SOTERIA_WARN,
    SOTERIA_FATAL
} soteria_level_t;

// Categorias de Falha
typedef enum {
    SOT_ERR_MEM,    // Exaustão de recursos
    SOT_ERR_LOGIC,  // Erro de contrato/asserção
    SOT_ERR_SIGNAL, // Falha de Kernel (Segfault, etc)
    SOT_ERR_VULCAN  // Erro interno na forja nativa
} soteria_err_t;

// API Interna Sotéria
void soteria_init(int argc, char** argv);
void soteria_mark(const char* step, const char* file, int line);
void soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func);

// Macros Nexus para o Desenvolvedor
#define SOTERIA_MARK(msg) soteria_mark(msg, __FILE__, __LINE__)
#define SOTERIA_DIE(reason, ctx, det) soteria_dispatch(SOTERIA_FATAL, reason, ctx, det, __FILE__, __LINE__, __func__)
#define SOTERIA_WARN(reason, ctx, det) soteria_dispatch(SOTERIA_WARN, reason, ctx, det, __FILE__, __LINE__, __func__)

#endif