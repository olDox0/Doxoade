#define SOTERIA_CORE
#include "../include/soteria.h"
#include <stdio.h>
#include <windows.h>
#include <psapi.h>
#include <dbghelp.h>

#ifdef _MSC_VER
    extern __declspec(thread) char g_last_loc[256];
#else
    extern __thread char g_last_loc[256];
#endif

LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info);
static volatile long g_panic_lock = 0;
static char g_command_line[512] = "doxoade_task";

void soteria_on_exit() {
    if (g_panic_lock == 0) {
        // IonBF garante que não haverá resíduo no buffer
        setvbuf(stdout, NULL, _IONBF, 0); 
        fprintf(stdout, "\n@SOTERIA_BEGIN@\n");
        fprintf(stdout, "TAG_LEVEL: EXIT_LOG\n");
        fprintf(stdout, "TAG_COMMAND: %s\n", g_command_line);
        fprintf(stdout, "TAG_RASTRO_LOC: %s\n", g_last_loc);
        fprintf(stdout, "@SOTERIA_END@\n");
        fflush(stdout);
        // Removido o Sleep longo para evitar travas em loops de teste
    }
}

void soteria_init(int argc, char** argv) {
    (void)argc; (void)argv; // Silencia C-LINT
    setvbuf(stdout, NULL, _IONBF, 0); 
    setvbuf(stderr, NULL, _IONBF, 0);
    
    const char* cmd = GetCommandLineA();
    if (cmd) strncpy(g_command_line, cmd, 511);

    SymSetOptions(SYMOPT_LOAD_LINES | SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
    SymInitialize(GetCurrentProcess(), NULL, TRUE);
    AddVectoredExceptionHandler(1, soteria_exception_handler);
    atexit(soteria_on_exit);
}

LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info) {
    if (InterlockedExchange(&g_panic_lock, 1) == 1) return EXCEPTION_EXECUTE_HANDLER;
    PEXCEPTION_RECORD rec = info->ExceptionRecord;
    
    fprintf(stdout, "\n@SOTERIA_BEGIN@\n");
    fprintf(stdout, "TAG_LEVEL: FATAL\n");
    fprintf(stdout, "TAG_PID: %lu\n", GetCurrentProcessId());
    fprintf(stdout, "TAG_COMMAND: %s\n", g_command_line);
    fprintf(stdout, "TAG_FAULT_ADDR: 0x%p\n", (void*)rec->ExceptionAddress);
    fprintf(stdout, "TAG_MOTIVO: 0x%lx\n", rec->ExceptionCode);
    
    // --- NEXUS FIX: MAPEAMENTO DE STACK SMASHING ---
    if (rec->ExceptionCode == 0xc0000005 || rec->ExceptionCode == 0xC0000409) {
        soteria_dump_arena_inventory(); }
        
    if (rec->ExceptionCode == 0xc0000005) 
        fprintf(stdout, "TAG_DETAIL: Access Violation (Ponteiro Nulo ou Endereco Invalido)\n");
    if (rec->ExceptionCode == 0xC0000409) 
        fprintf(stdout, "TAG_DETAIL: Stack Buffer Overrun: A integridade da pilha foi violada.\n");
    // -----------------------------------------------

    soteria_dump_stack_trace();
    fprintf(stdout, "@SOTERIA_END@\n");
    fflush(stdout); 
    TerminateProcess(GetCurrentProcess(), rec->ExceptionCode);
    return EXCEPTION_EXECUTE_HANDLER;
}

void soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func) {
    
    // 1. Desativa buffers para garantir que a mensagem saia antes do processo ser morto
    setvbuf(stdout, NULL, _IONBF, 0); 
    fprintf(stdout, "\n@SOTERIA_BEGIN@\n");
    
    // 2. Captura de Registradores de Hardware (Snapshot do momento)
    CONTEXT ctx;
    ctx.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
    if (GetThreadContext(GetCurrentThread(), &ctx)) {
        fprintf(stdout, "TAG_REG_RIP: 0x%llx\n", (unsigned long long)ctx.Rip);
        fprintf(stdout, "TAG_REG_RAX: 0x%llx\n", (unsigned long long)ctx.Rax);
        fprintf(stdout, "TAG_REG_RSP: 0x%llx\n", (unsigned long long)ctx.Rsp);
    }

    // 3. Despeja o Inventário da Arena (O que estava na RAM)
    soteria_dump_arena_inventory();

    fprintf(stdout, "TAG_LEVEL: %s\n", (level == SOTERIA_FATAL) ? "FATAL" : "WARNING");
    fprintf(stdout, "TAG_MOTIVO: %s\n", context);
    fprintf(stdout, "TAG_DETAIL: %s\n", detail);
    fprintf(stdout, "TAG_LOCAL: %s:%d\n", file, line);
    fprintf(stdout, "TAG_FUNC: %s\n", func);
    
    soteria_dump_stack_trace();
    fprintf(stdout, "@SOTERIA_END@\n");
    fflush(stdout); 

    if (level == SOTERIA_FATAL) {
        TerminateProcess(GetCurrentProcess(), 1);
    }
}

__attribute__((constructor)) void soteria_auto_ignite() { soteria_init(0, NULL); }