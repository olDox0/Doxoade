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
    static __declspec(thread) char g_last_var[128] = "N/A";
    static __declspec(thread) char g_last_var_snap[128] = "N/A";
#else
    static __thread const char* g_n_stack[16];
    static __thread const char* g_n_files[16];
    static __thread int         g_n_lines[16];
    static __thread int         g_s_ptr = 0;
    __thread char g_last_loc[256] = "N/A";
    static __thread char g_last_var[128] = "N/A";
    static __thread char g_last_var_snap[128] = "N/A";
#endif

// Estrutura de frame expandida
typedef struct {
    const char* func;
    const char* file;
    int line;
    char var_name[32];
    long long var_val;
} sot_frame_t;

// Função chamada pelo Scribe quando encontra um ponto de risco com variável
void soteria_mark_var(const char* var_name, long long value, const char* file, int line) {
    // Salva o estado da variável no buffer da thread
    snprintf(g_last_var_snap, 127, "%s = %lld (0x%llx)", var_name, value, value);
    // Atualiza o local do rastro para precisão
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

    // Apenas gravação em memória. Zero I/O de disco/terminal aqui.
    if (g_s_ptr < 16) {
        g_n_stack[g_s_ptr] = func;
        g_n_files[g_s_ptr] = file;
        g_n_lines[g_s_ptr] = line;
        g_s_ptr++;
    }

    in_soteria = 0;
}

// Certifique-se de que a variável g_last_loc está sendo preenchida:
void soteria_mark(const char* msg, const char* file, int line) {
    if (!file) return;
    // Salva o local exato na memória (Thread Safe)
    snprintf(g_last_loc, 255, "%s:%d", file, line);
    
    // Opcional: empilha no rastro se for um marco importante
   // soteria_push(msg, file, line);
}

// Na função de dump, garanta a impressão da tag:
void soteria_dump_stack_trace() {
    if (g_s_ptr > 0) {
        fprintf(stdout, "TAG_RASTRO_LOC: %s\n", g_last_loc);
        for (int i = g_s_ptr - 1; i >= 0; i--) {
            fprintf(stdout, "TAG_FRAME: %d | %s | %s:%d\n", i, g_n_stack[i], g_n_files[i], g_n_lines[i]);
            // Se for o frame do topo (onde o erro ocorreu), envia o valor da variável
            if (i == g_s_ptr - 1 && strcmp(g_last_var_snap, "N/A") != 0) {
                fprintf(stdout, "TAG_FRAME_VAR_%d: %s\n", i, g_last_var_snap);
            }
        }
    }
    // No dump_stack_trace, imprimir a variável se ela existir:
    if (g_n_stack[i].var_val != 0) {
        fprintf(stdout, "TAG_FRAME_VAR: %s = %lld (0x%llx)\n", 
                g_n_stack[i].var_name, g_n_stack[i].var_val, g_n_stack[i].var_val);
    }
}