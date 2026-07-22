// doxoade/tools/vulcan/diagnostic/soteria/src/soteria_core.c
/*
 * SOTERIA CORE v5.0 — Motor de Diagnóstico Nativo
 * Vectored Exception Handler + Signal Handler + Stack Probe
 */
#define SOTERIA_CORE
#include "../include/soteria.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <setjmp.h>
#include <windows.h>
#include <psapi.h>
#include <dbghelp.h>

/* ═══════════════════════════════════════════════════════════════════
 * THREAD-LOCAL STORAGE
 * ═══════════════════════════════════════════════════════════════════ */
#ifdef _MSC_VER
extern __declspec(thread) char g_last_loc[256];
#else
extern __thread char g_last_loc[256];
#endif

/* ═══════════════════════════════════════════════════════════════════
 * VARIÁVEIS GLOBAIS
 * ═══════════════════════════════════════════════════════════════════ */
static volatile long g_panic_lock = 0;
static char g_command_line[512] = "doxoade_task";

/* Stack overflow recovery */
jmp_buf g_stack_overflow_jmpbuf;
volatile sig_atomic_t g_stack_overflow_caught = 0;

/* Declarada em soteria_mem.c */
extern volatile LONG g_race_count;

/* ═══════════════════════════════════════════════════════════════════
 * PROTÓTIPOS INTERNOS
 * ═══════════════════════════════════════════════════════════════════ */
extern void soteria_dump_leaks(void);
extern void soteria_dump_arena_inventory(void);
extern void soteria_dump_stack_trace(void);
extern void soteria_calibrate_stack(void);

static void soteria_on_exit(void);
static void setup_stack_overflow_handler(void);
static void soteria_signal_handler(int sig);
LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info);

/* ═══════════════════════════════════════════════════════════════════
 * DUMP DE HARDWARE (Assembly x64)
 * ═══════════════════════════════════════════════════════════════════ */
void soteria_dump_hardware_state(void) {
    unsigned long long r_ax, r_bx, r_cx, r_dx, r_sp, r_ip;
    __asm__ volatile (
        "movq %%rax, %0\n\t"
        "movq %%rbx, %1\n\t"
        "movq %%rcx, %2\n\t"
        "movq %%rdx, %3\n\t"
        "movq %%rsp, %4\n\t"
        "leaq (%%rip), %5\n\t"
        : "=r"(r_ax), "=r"(r_bx), "=r"(r_cx),
          "=r"(r_dx), "=r"(r_sp), "=r"(r_ip)
    );
    char h_buf[512];
    snprintf(h_buf, 511,
        "TAG_REG_RAX: 0x%llx\nTAG_REG_RBX: 0x%llx\nTAG_REG_RCX: 0x%llx\n"
        "TAG_REG_RDX: 0x%llx\nTAG_REG_RSP: 0x%llx\nTAG_REG_RIP: 0x%llx\n",
        r_ax, r_bx, r_cx, r_dx, r_sp, r_ip);
    soteria_print_raw(h_buf);
}

/* ═══════════════════════════════════════════════════════════════════
 * SIGNAL HANDLER (Stack Overflow via SIGSEGV/SIGABRT)
 * ═══════════════════════════════════════════════════════════════════ */
static void soteria_signal_handler(int sig) {
    if (sig == SIGSEGV || sig == SIGABRT) {
        soteria_print_raw("\n@SOTERIA_BEGIN@\n");
        soteria_print_raw("TAG_LEVEL: FATAL\n");
        soteria_print_raw("TAG_MOTIVO: STACK_OVERFLOW\n");
        soteria_print_raw("TAG_DETAIL: A pilha de execução foi exaurida.\n");

        char sig_buf[64];
        snprintf(sig_buf, 63, "TAG_SIGNAL: %d\n", sig);
        soteria_print_raw(sig_buf);

        soteria_dump_hardware_state();
        soteria_print_raw("@SOTERIA_END@\n");
        fflush(stdout);

        if (g_stack_overflow_caught) {
            longjmp(g_stack_overflow_jmpbuf, 1);
        }
        TerminateProcess(GetCurrentProcess(), sig);
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * HANDLER DE ENCERRAMENTO (Memory Leak Report)
 * ═══════════════════════════════════════════════════════════════════ */
static void soteria_on_exit(void) {
    if (g_panic_lock == 0) {
        soteria_dump_leaks();

        /* Resumo de race conditions */
        if (g_race_count > 0) {
            char race_buf[256];
            snprintf(race_buf, 255,
                "\n[RESUMO] %ld race conditions detectadas "
                "(log: .doxoade/metalcraft/logs/race_conditions.log)\n",
                (long)g_race_count);
            soteria_print_raw(race_buf);
        }

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

/* ═══════════════════════════════════════════════════════════════════
 * SETUP DE PROTEÇÃO CONTRA STACK OVERFLOW
 * ═══════════════════════════════════════════════════════════════════ */
static void setup_stack_overflow_handler(void) {
    ULONG guarantee = 0x10000; /* 64 KB reservados */
    SetThreadStackGuarantee(&guarantee);
}

/* ═══════════════════════════════════════════════════════════════════
 * INICIALIZAÇÃO PRINCIPAL
 * ═══════════════════════════════════════════════════════════════════ */
void soteria_init(int argc, char **argv) {
    (void)argc; (void)argv;
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    soteria_calibrate_stack();

    const char *cmd = GetCommandLineA();
    if (cmd) strncpy(g_command_line, cmd, 511);

    /* Signal handlers */
    signal(SIGSEGV, soteria_signal_handler);
    signal(SIGABRT, soteria_signal_handler);

    /* Stack overflow protection */
    setup_stack_overflow_handler();

    /* Debug symbols */
    SymSetOptions(SYMOPT_LOAD_LINES | SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
    SymInitialize(GetCurrentProcess(), NULL, TRUE);

    /* Vectored exception handler (prioridade 1) */
    AddVectoredExceptionHandler(1,
        (PVECTORED_EXCEPTION_HANDLER)soteria_exception_handler);

    atexit(soteria_on_exit);
}

/* ═══════════════════════════════════════════════════════════════════
 * VECTORED EXCEPTION HANDLER
 * ═══════════════════════════════════════════════════════════════════ */
LONG WINAPI soteria_exception_handler(struct _EXCEPTION_POINTERS *info) {
    PEXCEPTION_RECORD rec = info->ExceptionRecord;

    /* Stack overflow — tratamento especial (stack pode estar corrompida) */
    if (rec->ExceptionCode == 0xC00000FD) {
        soteria_print_raw("\n@SOTERIA_BEGIN@\n");
        soteria_print_raw("TAG_LEVEL: FATAL\n");
        soteria_print_raw("TAG_MOTIVO: STACK_OVERFLOW\n");
        soteria_print_raw("TAG_DETAIL: A pilha de execução foi exaurida.\n");
        soteria_dump_hardware_state();
        soteria_print_raw("@SOTERIA_END@\n");
        fflush(stdout);
        TerminateProcess(GetCurrentProcess(), 0xC00000FD);
        return EXCEPTION_EXECUTE_HANDLER;
    }

    /* Panic lock — evita reentrância */
    if (InterlockedExchange(&g_panic_lock, 1) == 1)
        return EXCEPTION_EXECUTE_HANDLER;

    char pid_buf[64];
    snprintf(pid_buf, 63, "TAG_PID: %lu\n", GetCurrentProcessId());
    soteria_print_raw(pid_buf);

    soteria_print_raw("TAG_MOTIVO: CRITICAL_HARDWARE_EXCEPTION\n");

    char fault_buf[128];
    snprintf(fault_buf, 127, "TAG_FAULT_ADDR: 0x%p\nTAG_MOTIVO_HEX: 0x%lx\n",
             (void *)rec->ExceptionAddress, rec->ExceptionCode);
    soteria_print_raw(fault_buf);

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

    Sleep(100);
    TerminateProcess(GetCurrentProcess(), rec->ExceptionCode);
    return EXCEPTION_EXECUTE_HANDLER;
}

/* ═══════════════════════════════════════════════════════════════════
 * FUNÇÕES AUXILIARES
 * ═══════════════════════════════════════════════════════════════════ */
void soteria_print_raw(const char *msg) {
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut != INVALID_HANDLE_VALUE) {
        DWORD written;
        WriteFile(hOut, msg, (DWORD)strlen(msg), &written, NULL);
    }
}

void soteria_io_trace(const char *op, const char *payload,
                      const char *file, int line) {
    char buf[1024];
    snprintf(buf, 1023, "TAG_IO_EVENT: %s | Data: \"%.48s\" | Loc: %s:%d\n",
             op, (payload ? payload : "N/A"), file, line);
    soteria_print_raw(buf);
}

void soteria_dispatch(soteria_level_t level, soteria_err_t reason,
                      const char *context, const char *detail,
                      const char *file, int line, const char *func) {
    if (InterlockedExchange(&g_panic_lock, 1) == 1) return;

    soteria_print_raw("\n@SOTERIA_BEGIN@\n");
    soteria_dump_hardware_state();

    char meta[512];
    snprintf(meta, 511,
        "TAG_LEVEL: %s\nTAG_MOTIVO: %s\nTAG_DETAIL: %s\n"
        "TAG_RASTRO_LOC: %s:%d\nTAG_CONTEXTO: %s\n",
        (level == SOTERIA_FATAL ? "FATAL" : "WARN"),
        context, detail, file, line, func);
    soteria_print_raw(meta);

    soteria_dump_arena_inventory();
    soteria_dump_stack_trace();
    soteria_print_raw("@SOTERIA_END@\n");
    fflush(stdout);

    if (level == SOTERIA_FATAL) {
        Sleep(200);
        TerminateProcess(GetCurrentProcess(), 1);
    }

    InterlockedExchange(&g_panic_lock, 0);
}

/* Auto-ignição */
__attribute__((constructor)) void soteria_auto_ignite(void) {
    soteria_init(0, NULL);
}