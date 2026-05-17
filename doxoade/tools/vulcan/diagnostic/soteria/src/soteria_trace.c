#define SOTERIA_CORE
#include "../include/soteria.h"
#include <stdio.h>
#include <string.h>
#include <windows.h>

static const char* g_n_stack[16];
static const char* g_n_files[16];
static int g_n_lines[16];
static int g_s_ptr = 0;
static unsigned long g_cached_pid = 0;
static char g_cached_cmd[512] = "N/A";

// Captura a identidade no início (PASC 8.19 Fix)
void soteria_capture_identity() {
    if (g_cached_pid != 0) return;
    g_cached_pid = GetCurrentProcessId();
    strncpy(g_cached_cmd, GetCommandLineA(), 511);
}

void soteria_push(const char* func, const char* file, int line) {
    if (g_s_ptr < 16) {
        g_n_stack[g_s_ptr] = func; g_n_files[g_s_ptr] = file; g_n_lines[g_s_ptr] = line;
        g_s_ptr++;
    }
}

void soteria_payload(const char* level, const char* motive, const char* detail, const char* file, int line, const char* func) {
    if (g_cached_pid == 0) {
        g_cached_pid = GetCurrentProcessId();
        strncpy(g_cached_cmd, GetCommandLineA(), 511);
    }

    printf("\n@SOTERIA_BEGIN@\n");
    
    FILE *f = fopen(".doxoade/vulcan/last_crash.sot", "w");
    if (f) {
        fprintf(f, "TAG_LEVEL: %s\nTAG_PID: %lu\nTAG_MOTIVO: %s\nTAG_DETAIL: %s\nTAG_LOCAL: %s:%d\nTAG_FUNC: %s\n", 
                level, g_cached_pid, motive, detail, file, line, func);
        fclose(f);
    }

    for (int i = g_s_ptr - 1; i >= 0; i--) {
        printf("TAG_FRAME: %d | %s | %s:%d\n", i, g_n_stack[i], g_n_files[i], g_n_lines[i]);
    }
    
    if (g_s_ptr > 0) {
        printf("TAG_RASTRO_MSG: TRACEBACK: %s\nTAG_RASTRO_LOC: %s:%d\n", g_n_stack[g_s_ptr-1], g_n_files[g_s_ptr-1], g_n_lines[g_s_ptr-1]);
    }
    printf("@SOTERIA_END@\n");
    fflush(stdout);
}

void soteria_mark(const char* msg, const char* file, int line) {
    // Reutiliza a lógica de push para registrar o rastro no topo da pilha
    soteria_push(msg, file, line);
}