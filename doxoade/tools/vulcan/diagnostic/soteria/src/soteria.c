#include "../include/soteria.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h> 
#include <dbghelp.h> 
#include <psapi.h> 

static char g_cmd_line[512] = "OADE_INTERNAL";
//static char g_last_mark[256] = "Nenhum marco registrado.";
static char g_last_msg[256] = "Nenhum marco";
static char g_last_file[512] = "N/A";
static int  g_last_line = 0;

void soteria_mark(const char* step, const char* file, int line) {
    if (!step || !file) return;
    strncpy(g_last_msg, step, 255);
    strncpy(g_last_file, file, 511);
    g_last_line = line;
}

LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info) {
    HANDLE process = GetCurrentProcess();
    SymRefreshModuleList(process);

    void* stack[15];
    unsigned short frames = CaptureStackBackTrace(2, 10, stack, NULL);
    
    // CORREÇÃO: Usando 'info' que é o nome do parâmetro
    void* fault_addr = info->ExceptionRecord->ExceptionAddress;
    
    printf("\n@SOTERIA_BEGIN@\n");
    printf("TAG_LEVEL: FATAL\n");
    printf("TAG_PID: %lu\n", GetCurrentProcessId());
    printf("TAG_DETAIL: EXCECAO 0x%lx em %p\n", info->ExceptionRecord->ExceptionCode, fault_addr);

    SYMBOL_INFO* sym = (SYMBOL_INFO*)calloc(sizeof(SYMBOL_INFO) + 256, 1);
    sym->MaxNameLen = 255; sym->SizeOfStruct = sizeof(SYMBOL_INFO);
    IMAGEHLP_LINE64 line_info = { .SizeOfStruct = sizeof(IMAGEHLP_LINE64) };
    DWORD disp = 0;

    // Localização Geográfica do Impacto
    if (SymGetLineFromAddr64(process, (DWORD64)fault_addr, &disp, &line_info)) {
        printf("TAG_LOCAL: %s:%lu\n", line_info.FileName, line_info.LineNumber);
    } else {
        printf("TAG_LOCAL: 0x%p\n", fault_addr);
    }

    // Peças do Quebra-Cabeça (Stack)
    for (int i = 0; i < frames; i++) {
        const char* fn = (SymFromAddr(process, (DWORD64)stack[i], 0, sym)) ? sym->Name : "???";
        if (SymGetLineFromAddr64(process, (DWORD64)stack[i], &disp, &line_info)) {
            printf("TAG_FRAME: %d | %s | %s:%lu\n", i, fn, line_info.FileName, line_info.LineNumber);
        } else {
            printf("TAG_FRAME: %d | %s | (externo)\n", i, fn);
        }
    }

    printf("TAG_RASTRO_MSG: %s\n", g_last_msg);
    printf("TAG_RASTRO_LOC: %s:%d\n", g_last_file, g_last_line);
    printf("@SOTERIA_END@\n");
    
    fflush(stdout);
    free(sym);
    exit(1);
}

void soteria_init(int argc, char** argv) {
    HANDLE process = GetCurrentProcess();
    SymSetOptions(SYMOPT_LOAD_LINES | SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
    
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    char* last_slash = strrchr(path, '\\');
    if (last_slash) *last_slash = '\0';

    SymInitialize(process, path, TRUE); 
    AddVectoredExceptionHandler(1, soteria_exception_handler);
}

void soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func) {
    static const char* R_STR[] = {"MEMORIA", "LOGIC", "SINAL", "VULCAN"};
    printf("\n@SOTERIA_BEGIN@\nTAG_LEVEL: %s\nTAG_COMMAND: %s\nTAG_FUNC: %s\nTAG_MOTIVO: %s\nTAG_SUBSIS: %s\nTAG_DETAIL: %s\nTAG_LOCAL: %s:%d\nTAG_RASTRO_MSG: %s\nTAG_RASTRO_LOC: %s:%d\n@SOTERIA_END@\n",
           (level == SOTERIA_FATAL) ? "FATAL" : "AVISO", g_cmd_line, func, R_STR[reason], context, detail, file, line, g_last_msg, g_last_file, g_last_line);
    fflush(stdout);
    if (level == SOTERIA_FATAL) exit(1);
}

__attribute__((constructor)) void soteria_auto_ignite() { soteria_init(0, NULL); }