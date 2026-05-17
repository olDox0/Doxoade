#define SOTERIA_CORE
#include "../include/soteria.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h> 
#include <dbghelp.h> 

// 1. ESTADO INTERNO ÚNICO (PASC 8.12)
typedef struct { 
    void* ptr; 
    size_t size; 
    const char* file; 
    int line; 
    int is_live; 
} mem_rec_t;

static mem_rec_t g_mem_db[512];
static int g_mem_ptr = 0;
static const char* g_n_stack[16];
static const char* g_n_files[16];
static int g_n_lines[16];
static int g_s_ptr = 0;
static unsigned long g_cached_pid = 0;
static char g_cached_cmd[512] = "N/A";

// 2. EMISSOR DE EVIDÊNCIAS (Apolo/Hórus)
void soteria_payload(const char* level, const char* motive, const char* detail, const char* file, int line, const char* func) {
    printf("\n@SOTERIA_BEGIN@\n");
    printf("TAG_LEVEL: %s\n", level);
    printf("TAG_PID: %lu\n", GetCurrentProcessId());
    printf("TAG_COMMAND: %s\n", GetCommandLineA());
    printf("TAG_MOTIVO: %s\n", motive);
    printf("TAG_DETAIL: %s\n", detail);
    printf("TAG_LOCAL: %s:%d\n", file, line);
    printf("TAG_FUNC: %s\n", func);

    // Pilha de Software (Traceback Nativo do Scribe)
    for (int i = g_s_ptr - 1; i >= 0; i--) {
        printf("TAG_FRAME: %d | %s | %s:%d\n", i, g_n_stack[i], g_n_files[i], g_n_lines[i]);
    }

    // Marca para triangulação do Python
    if (g_s_ptr > 0) {
        printf("TAG_RASTRO_MSG: TRACEBACK: %s\n", g_n_stack[g_s_ptr-1]);
        printf("TAG_RASTRO_LOC: %s:%d\n", g_n_files[g_s_ptr-1], g_n_lines[g_s_ptr-1]);
    }
    printf("@SOTERIA_END@\n");
    fflush(stdout);
}

// 3. GESTÃO DE MEMÓRIA (Anúbis Mode)
void* soteria_malloc(size_t size, const char* file, int line) {
    void* p = (malloc)(size);
    if (p && g_mem_ptr < 512) {
        g_mem_db[g_mem_ptr++] = (mem_rec_t){p, size, file, line, 1};
    }
    return p;
}

void soteria_free(void* ptr, const char* file, int line) {
    if (!ptr) return;
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].ptr == ptr) {
            if (!g_mem_db[i].is_live) 
                soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "DOUBLE_FREE", "Tentativa de liberar memoria ja morta.", file, line, "free");
            
            memset(ptr, 0xCC, g_mem_db[i].size); // Poisoning
            g_mem_db[i].is_live = 0;
            (free)(ptr); return;
        }
    }
    (free)(ptr);
}

void soteria_validate(void* ptr, const char* file, int line) {
    for (int i = 0; i < g_mem_ptr; i++) {
        if (g_mem_db[i].ptr == ptr && !g_mem_db[i].is_live)
            soteria_dispatch(SOTERIA_FATAL, SOT_ERR_MEM, "DANGLING_POINTER", "Acesso a ponteiro solto (memoria liberada).", file, line, "validate");
    }
}

// 4. RASTREIO E HANDLERS
void soteria_push(const char* func, const char* file, int line) {
    if (g_s_ptr < 16) {
        g_n_stack[g_s_ptr] = func; g_n_files[g_s_ptr] = file; g_n_lines[g_s_ptr] = line;
        g_s_ptr++;
    }
}

void soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func) {
    const char* lvl = (level == SOTERIA_FATAL) ? "FATAL" : "WARNING";
    soteria_payload(lvl, context, detail, file, line, func);
    if (level == SOTERIA_FATAL) exit(1);
}

LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info) {
    char det[128];
    sprintf(det, "Falha Critica 0x%lx em %p", info->ExceptionRecord->ExceptionCode, info->ExceptionRecord->ExceptionAddress);
    soteria_payload("FATAL", "SIGNAL", det, "N/A", 0, "KERNEL");
    return EXCEPTION_EXECUTE_HANDLER;
}

void soteria_init(int argc, char** argv) {
    g_cached_pid = GetCurrentProcessId();
    strncpy(g_cached_cmd, GetCommandLineA(), 511);
    AddVectoredExceptionHandler(1, soteria_exception_handler);
}

__attribute__((constructor)) void soteria_auto_ignite() { soteria_init(0, NULL); }

__attribute__((destructor)) void soteria_check_leaks() {
    int leaks = 0;
    for (int i = 0; i < g_mem_ptr; i++) if (g_mem_db[i].is_live) leaks++;
    if (leaks == 0) return;
    printf("\n@SOTERIA_BEGIN@\nTAG_LEVEL: WARNING\nTAG_MOTIVO: MEMORY_LEAK\nTAG_DETAIL: %d blocos orfaos.\n", leaks);
    for (int i = 0; i < g_mem_ptr; i++)
        if (g_mem_db[i].is_live) printf("TAG_LEAK: %zu bytes em %s:%d\n", g_mem_db[i].size, g_mem_db[i].file, g_mem_db[i].line);
    printf("@SOTERIA_END@\n");
    fflush(stdout);
}