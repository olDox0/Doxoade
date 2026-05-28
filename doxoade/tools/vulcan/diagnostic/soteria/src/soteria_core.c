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

// Protótipo interno
void soteria_dump_hardware_state() {
    unsigned long long r_ax, r_bx, r_cx, r_dx, r_sp, r_ip;

    // [CHIEF-GOLD] Captura atômica via Registradores Reais
    __asm__ volatile (
        "movq %%rax, %0\n\t"
        "movq %%rbx, %1\n\t"
        "movq %%rcx, %2\n\t"
        "movq %%rdx, %3\n\t"
        "movq %%rsp, %4\n\t"
        "leaq (%%rip), %5\n\t"
        : "=r"(r_ax), "=r"(r_bx), "=r"(r_cx), "=r"(r_dx), "=r"(r_sp), "=r"(r_ip)
    );

    char h_buf[512];
    // Enviamos com o prefixo TAG_REG_ para o analyze_crash.py capturar
    snprintf(h_buf, 511, 
             "TAG_REG_RAX: 0x%llx\nTAG_REG_RBX: 0x%llx\n"
             "TAG_REG_RCX: 0x%llx\nTAG_REG_RDX: 0x%llx\n"
             "TAG_REG_RSP: 0x%llx\nTAG_REG_RIP: 0x%llx\n", 
             r_ax, r_bx, r_cx, r_dx, r_sp, r_ip);
    
    soteria_print_raw(h_buf); // Grito direto via WinAPI
}

// Chame soteria_dump_hardware_state() dentro da soteria_dispatch
// logo após o fprintf @SOTERIA_BEGIN@.

// Chame esta função dentro do soteria_dispatch, antes do dump_stack_trace

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

// Escrita atômica que ignora o buffer do C-Runtime
void soteria_print_raw(const char* msg) {
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut != INVALID_HANDLE_VALUE) {
        DWORD written;
        WriteFile(hOut, msg, (DWORD)strlen(msg), &written, NULL);
    }
}

void soteria_io_trace(const char* op, const char* file, int line) {
    char buf[256];
    snprintf(buf, 255, "TAG_IO_EVENT: %s em %s:%d\n", op, file, line);
    soteria_print_raw(buf);
}

void soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func) {
    
    soteria_print_raw("\n@SOTERIA_BEGIN@\n");

    // 1. Hardware Snapshot (A única fonte da verdade)
    soteria_dump_hardware_state();

    // 2. Metadados
    char meta[512];
    snprintf(meta, 511, "TAG_MOTIVO: %s\nTAG_LEVEL: %s\nTAG_DETAIL: %s\nTAG_RASTRO_LOC: %s:%d\n", 
             context, (level == SOTERIA_FATAL ? "FATAL" : "WARN"), detail, file, line);
    soteria_print_raw(meta);

    // 3. Inventário e Pilha
    soteria_dump_arena_inventory();
    soteria_dump_stack_trace();

    soteria_print_raw("@SOTERIA_END@\n");

    if (level == SOTERIA_FATAL) {
        Sleep(200); // Dá tempo ao Python para ler o pipe
        TerminateProcess(GetCurrentProcess(), 1);
    }
}

__attribute__((constructor)) void soteria_auto_ignite() { soteria_init(0, NULL); }