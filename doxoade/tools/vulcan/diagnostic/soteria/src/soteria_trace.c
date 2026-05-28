// doxoade\tools\vulcan\diagnostic\soteria\src\soteria_trace.c
#define SOTERIA_CORE
#include "../include/soteria.h"
#include <stdio.h>
#include <string.h>
#include <windows.h>

// --- ESTADO ISOLADO POR THREAD (Pilha de Software) ---
#ifdef _MSC_VER
    static __declspec(thread) const char* g_n_stack[16];
    static __declspec(thread) const char* g_n_files[16];
    static __declspec(thread) int         g_n_lines[16];
    static __declspec(thread) int         g_s_ptr = 0;
    __declspec(thread) char g_last_loc[256] = "N/A";
    static __declspec(thread) char g_last_var_val[128] = "N/A";
#else
    static __thread const char* g_n_stack[16];
    static __thread const char* g_n_files[16];
    static __thread int         g_n_lines[16];
    static __thread int         g_s_ptr = 0;
    __thread char g_last_loc[256] = "N/A";
    static __thread char g_last_var_val[128] = "N/A";
#endif

// Função chamada pelo Scribe quando encontra um ponto de risco com variável
void soteria_mark_var(const char* var_name, long long value, const char* file, int line) {
    // Salva o valor da variável para o Lazarus ler
    snprintf(g_last_var_val, 127, "%s = %lld (0x%llx)", var_name, value, value);
    // Atualiza o local do rastro
    snprintf(g_last_loc, 255, "%s:%d", file, line);
}

void soteria_push(const char* func, const char* file, int line) {
    #ifdef _MSC_VER
        static __declspec(thread) int in_soteria = 0;
    #else
        static __thread int in_soteria = 0;
    #endif

    if (in_soteria) return; 
    in_soteria = 1;

    if (g_s_ptr < 16) {
        g_n_stack[g_s_ptr] = func;
        g_n_files[g_s_ptr] = file;
        g_n_lines[g_s_ptr] = line;
        g_s_ptr++;
    }

    in_soteria = 0;
}

void soteria_mark(const char* msg, const char* file, int line) {
    if (!file) return;
    snprintf(g_last_loc, 255, "%s:%d", file, line);
}

void soteria_dump_stack_trace() {
    if (g_s_ptr > 0) {
        for (int i = g_s_ptr - 1; i >= 0; i--) {
            fprintf(stdout, "TAG_FRAME: %d | %s | %s:%d\n", i, g_n_stack[i], g_n_files[i], g_n_lines[i]);
            
            // Se houver rastro de variável para o frame do impacto
            if (i == g_s_ptr - 1 && strcmp(g_last_var_val, "N/A") != 0) {
                fprintf(stdout, "TAG_FRAME_VAR_%d: %s\n", i, g_last_var_val);
            }
        }
    }
}