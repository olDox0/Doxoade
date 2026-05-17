#define SOTERIA_CORE
#include "../include/soteria.h"
#include <stdio.h>
#include <windows.h>
#ifdef _WIN32
#include <dbghelp.h>
#endif

LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info) {
    char det[128];
    sprintf(det, "Falha Critica de Hardware 0x%lx em %p", info->ExceptionRecord->ExceptionCode, info->ExceptionRecord->ExceptionAddress);
    soteria_payload("FATAL", "SIGNAL", det, "N/A", 0, "KERNEL");
    return EXCEPTION_EXECUTE_HANDLER;
}

void soteria_init(int argc, char** argv) {
    #ifdef _WIN32
    HANDLE process = GetCurrentProcess();
    // Configura opções de rastro de linhas
    SymSetOptions(SYMOPT_LOAD_LINES | SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
    SymInitialize(process, NULL, TRUE);
    
    AddVectoredExceptionHandler(1, soteria_exception_handler);
    #endif
}

void soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func) {
    soteria_payload((level == SOTERIA_FATAL) ? "FATAL" : "WARNING", context, detail, file, line, func);
    if (level == SOTERIA_FATAL) exit(1);
}

__attribute__((constructor)) void soteria_auto_ignite() { soteria_init(0, NULL); }