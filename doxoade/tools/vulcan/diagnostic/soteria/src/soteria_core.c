// doxoade/tools/vulcan/diagnostic/soteria/src/soteria_core.c
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

// Protótipos das novas funções de memória (em soteria_mem.c)
extern void soteria_dump_leaks();
extern void soteria_dump_arena_inventory();

LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info);
static volatile long g_panic_lock = 0;
static char g_command_line[512] = "doxoade_task";

// Registro de Hardware via Assembly Total (x64)
void soteria_dump_hardware_state() {
    unsigned long long r_ax, r_bx, r_cx, r_dx, r_sp, r_ip;
    __asm__ volatile (
        "movq %%rax, %0\n\t" "movq %%rbx, %1\n\t" "movq %%rcx, %2\n\t"
        "movq %%rdx, %3\n\t" "movq %%rsp, %4\n\t" "leaq (%%rip), %5\n\t"
        : "=r"(r_ax), "=r"(r_bx), "=r"(r_cx), "=r"(r_dx), "=r"(r_sp), "=r"(r_ip)
    );
    char h_buf[512];
    snprintf(h_buf, 511, "TAG_REG_RAX: 0x%llx\nTAG_REG_RBX: 0x%llx\nTAG_REG_RCX: 0x%llx\nTAG_REG_RDX: 0x%llx\nTAG_REG_RSP: 0x%llx\nTAG_REG_RIP: 0x%llx\n", 
             r_ax, r_bx, r_cx, r_dx, r_sp, r_ip);
    soteria_print_raw(h_buf);
}

// Handler de encerramento: Onde os Memory Leaks são revelados
void soteria_on_exit() {
    if (g_panic_lock == 0) {
        // 1. Executa a varredura de lixo na Arena Hades
        soteria_dump_leaks();

        // 2. Registro final de encerramento normal
        setvbuf(stdout, NULL, _IONBF, 0); 
        soteria_print_raw("\n@SOTERIA_BEGIN@\n");
        soteria_print_raw("TAG_LEVEL: EXIT_LOG\n");
        char cmd_buf[512];
        snprintf(cmd_buf, 511, "TAG_COMMAND: %s\n", g_command_line);
        soteria_print_raw(cmd_buf);
        
        char loc_buf[256];
        snprintf(loc_buf, 255, "TAG_RASTRO_LOC: %s\n", g_last_loc);
        soteria_print_raw(loc_buf);
        
        soteria_print_raw("@SOTERIA_END@\n");
        fflush(stdout);
    }
}

void soteria_init(int argc, char** argv) {
    (void)argc; (void)argv;
    setvbuf(stdout, NULL, _IONBF, 0); 
    setvbuf(stderr, NULL, _IONBF, 0);
    
    const char* cmd = GetCommandLineA();
    if (cmd) strncpy(g_command_line, cmd, 511);

    SymSetOptions(SYMOPT_LOAD_LINES | SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
    SymInitialize(GetCurrentProcess(), NULL, TRUE);
    AddVectoredExceptionHandler(1, (PVECTORED_EXCEPTION_HANDLER)soteria_exception_handler);
    atexit(soteria_on_exit);
}

LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info) {
    if (InterlockedExchange(&g_panic_lock, 1) == 1) return EXCEPTION_EXECUTE_HANDLER;
    PEXCEPTION_RECORD rec = info->ExceptionRecord;
    
    soteria_print_raw("\n@SOTERIA_BEGIN@\n");
    soteria_print_raw("TAG_LEVEL: FATAL\n");
    
    char pid_buf[64];
    snprintf(pid_buf, 63, "TAG_PID: %lu\n", GetCurrentProcessId());
    soteria_print_raw(pid_buf);

    soteria_print_raw("TAG_MOTIVO: CRITICAL_HARDWARE_EXCEPTION\n");
    
    char fault_buf[128];
    snprintf(fault_buf, 127, "TAG_FAULT_ADDR: 0x%p\nTAG_MOTIVO_HEX: 0x%lx\n", 
             (void*)rec->ExceptionAddress, rec->ExceptionCode);
    soteria_print_raw(fault_buf);
    
    // Mapeamento de desastres físicos
    if (rec->ExceptionCode == 0xc0000005) 
        soteria_print_raw("TAG_DETAIL: Access Violation (Ponteiro Nulo ou Escrita Proibida)\n");
    else if (rec->ExceptionCode == 0xC0000409) 
        soteria_print_raw("TAG_DETAIL: Stack Buffer Overrun (Stack Smashing detectado)\n");
    else if (rec->ExceptionCode == 0xc0000374)
        soteria_print_raw("TAG_DETAIL: Heap Corruption (Erro critico no gerenciador de memoria)\n");

    soteria_dump_hardware_state();
    soteria_dump_arena_inventory();
    soteria_dump_stack_trace();

    soteria_print_raw("@SOTERIA_END@\n");
    fflush(stdout); 

    // Sleep para garantir que o buffer de saída seja capturado pelo processo pai (Doxoade)
    Sleep(100);
    TerminateProcess(GetCurrentProcess(), rec->ExceptionCode);
    return EXCEPTION_EXECUTE_HANDLER;
}

void soteria_print_raw(const char* msg) {
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut != INVALID_HANDLE_VALUE) {
        DWORD written;
        WriteFile(hOut, msg, (DWORD)strlen(msg), &written, NULL);
    }
}

void soteria_io_trace(const char* op, const char* payload, const char* file, int line) {
    char buf[1024];
    snprintf(buf, 1023, "TAG_IO_EVENT: %s | Data: \"%.48s\" | Loc: %s:%d\n", 
             op, (payload ? payload : "N/A"), file, line);
    soteria_print_raw(buf);
}

void soteria_dispatch(soteria_level_t level, soteria_err_t reason, const char* context, 
                     const char* detail, const char* file, int line, const char* func) {
    
    // Evita reentrância se já estivermos em pânico
    if (InterlockedExchange(&g_panic_lock, 1) == 1) return;

    soteria_print_raw("\n@SOTERIA_BEGIN@\n");
    
    // 1. HARDWARE (ASM)
    soteria_dump_hardware_state();

    // 2. METADADOS DO ERRO LOGICO
    char meta[512];
    snprintf(meta, 511, "TAG_LEVEL: %s\nTAG_MOTIVO: %s\nTAG_DETAIL: %s\nTAG_RASTRO_LOC: %s:%d\nTAG_CONTEXTO: %s\n", 
             (level == SOTERIA_FATAL ? "FATAL" : "WARN"), context, detail, file, line, func);
    soteria_print_raw(meta);

    // 3. ARENA HADES E CALL STACK
    soteria_dump_arena_inventory();
    soteria_dump_stack_trace();

    soteria_print_raw("@SOTERIA_END@\n");
    fflush(stdout);

    if (level == SOTERIA_FATAL) {
        Sleep(200); 
        TerminateProcess(GetCurrentProcess(), 1);
    }
    
    // Se não for fatal, libera o lock para continuar a execução
    InterlockedExchange(&g_panic_lock, 0);
}

__attribute__((constructor)) void soteria_auto_ignite() { soteria_init(0, NULL); }