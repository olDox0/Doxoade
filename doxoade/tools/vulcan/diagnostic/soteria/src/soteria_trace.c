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

// Variável global para armazenar o topo da stack (setada no init)
static uintptr_t g_stack_base = 0;
static uintptr_t g_stack_limit = 0;

// 🆕 Chamada uma vez no init para calibrar os limites da stack
void soteria_calibrate_stack(void) {
    int anchor;
    g_stack_base = (uintptr_t)&anchor;
    
    // Stack padrão do Windows é 1MB. Define limite de segurança em 64KB antes do fim.
    // A stack cresce PARA BAIXO, então o limite é base - (1MB - 64KB)
    g_stack_limit = g_stack_base - (1024 * 1024 - 64 * 1024);
}

void soteria_push(const char* func, const char* file, int line) {
#ifdef _MSC_VER
    static __declspec(thread) int in_soteria = 0;
#else
    static __thread int in_soteria = 0;
#endif
    if (in_soteria) return;
    in_soteria = 1;
    
    // 🆕 STACK PROBE: Verifica se estamos perto do limite da stack
    if (g_stack_base != 0) {
        int probe_var;
        uintptr_t current_sp = (uintptr_t)&probe_var;
        
        // Se SP está abaixo do limite (stack quase cheia)
        if (current_sp < g_stack_limit + (128 * 1024)) { // 128KB de margem
            // Stack está perigosamente cheia — reporta ANTES do overflow
            char detail[256];
            snprintf(detail, 255, 
                "Stack probe critico: SP=0x%llx, Base=0x%llx, Limite=0x%llx, Uso=%lluKB. "
                "Funcao '%s' em %s:%d pode causar stack overflow.",
                (unsigned long long)current_sp,
                (unsigned long long)g_stack_base,
                (unsigned long long)g_stack_limit,
                (unsigned long long)((g_stack_base - current_sp) / 1024),
                func, file, line);
            
            soteria_print_raw("\n@SOTERIA_BEGIN@\n");
            soteria_print_raw("TAG_LEVEL: FATAL\n");
            soteria_print_raw("TAG_MOTIVO: STACK_OVERFLOW_IMMINENT\n");
            
            char detail_tag[512];
            snprintf(detail_tag, 511, "TAG_DETAIL: %s\n", detail);
            soteria_print_raw(detail_tag);
            
            char loc_tag[256];
            snprintf(loc_tag, 255, "TAG_RASTRO_LOC: %s:%d\n", file, line);
            soteria_print_raw(loc_tag);
            
            // Dump da call stack acumulada
            if (g_s_ptr > 0) {
                for (int i = g_s_ptr - 1; i >= 0; i--) {
                    char frame_tag[512];
                    snprintf(frame_tag, 511, "TAG_FRAME: %d | %s | %s:%d\n", 
                             i, g_n_stack[i], g_n_files[i], g_n_lines[i]);
                    soteria_print_raw(frame_tag);
                }
            }
            
            soteria_print_raw("@SOTERIA_END@\n");
            fflush(stdout);
            
            // Termina ANTES do overflow real acontecer
            TerminateProcess(GetCurrentProcess(), 0xC00000FD);
        }
    }
    
    // Push normal na call stack
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