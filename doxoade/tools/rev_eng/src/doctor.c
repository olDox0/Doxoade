/* doctor.c — self-diagnóstico e pre-flight do doxreveng */
#include "doctor.h"
#include "file_reader.h"
#include "pe_parser.h"
#include "pre_ir.h"
#include "decoder_backend.h"
#include "disasm.h"
#include "cfg.h"
#include "functions.h"
#include "patterns.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PASS "[ OK ]"
#define FAIL "[FAIL]"
#define WARN "[WARN]"
#define INFO "[INFO]"

static int g_fail = 0;

static void report(const char *status, const char *fmt, ...)
{
    va_list ap;
    printf("  %s ", status);
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
}

/* ---------- 1. Build ---------- */
static int test_build(void)
{
    printf("[BUILD]\n");
    report(INFO, "doxreveng — Fase 4 (parser PE + disasm + CFG + symbols)");
    report(INFO, "Compilador: " __VERSION__);

#ifdef HAVE_CAPSTONE
    report(INFO, "Backend Capstone: habilitado (compile-time)");
    {
        DecodedInsn dummy;
        FileReader fake = {0};
        uint8_t buf[16] = {0x90};
        fake.data = buf; fake.size = 16;
        char err[64] = {0};
        int n = decode_one_backend(BACKEND_CAPSTONE, &fake, 0, 0,
                                   &dummy, err, sizeof(err));
        if (n > 0) report(PASS, "Backend Capstone inicializa e decodifica 'nop'");
        else { report(FAIL, "Backend Capstone não decodifica 'nop': %s", err); g_fail++; }
    }
#else
    report(WARN, "Backend Capstone desabilitado (compile com -DHAVE_CAPSTONE)");
#endif

    {
        DecodedInsn dummy;
        FileReader fake = {0};
        uint8_t buf[16] = {0x90};
        fake.data = buf; fake.size = 16;
        char err[64] = {0};
        int n = decode_one_backend(BACKEND_NATIVE, &fake, 0, 0,
                                   &dummy, err, sizeof(err));
        if (n > 0 && dummy.length == 1) report(PASS, "Backend nativo decodifica 'nop' (1 byte)");
        else { report(FAIL, "Backend nativo falhou"); g_fail++; }
    }
    return 0;
}

/* ---------- 2. File reader ---------- */
static int test_file_reader(const char *path)
{
    printf("[FILE READER]\n");
    if (path == NULL) { report(INFO, "sem arquivo alvo, pulando"); return 0; }
    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        report(FAIL, "abrir '%s': %s", path, err); g_fail++; return -1;
    }
    report(PASS, "abriu '%s' (%zu bytes)", path, fr.size);
    const uint8_t *p = file_reader_at(&fr, fr.size, 1);
    if (p == NULL) report(PASS, "file_reader_at valida bounds (fim do arquivo)");
    else { report(FAIL, "file_reader_at não validou bounds"); g_fail++; }
    file_reader_close(&fr);
    return 0;
}

/* ---------- 3. PE parser ---------- */
static int test_pe_parser(const char *path, PreIR *out_ir)
{
    printf("[PE PARSER]\n");
    if (path == NULL) { report(INFO, "sem arquivo alvo, pulando"); return -1; }
    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        report(FAIL, "abrir: %s", err); g_fail++; return -1;
    }
    PreIR ir;
    if (pe_parse(&fr, &ir, err, sizeof(err)) != 0) {
        report(FAIL, "parse: %s", err);
        file_reader_close(&fr);
        g_fail++;
        return -1;
    }
    report(PASS, "format=%s, image_base=0x%llx, entry=0x%x",
           ir.format, (unsigned long long)ir.image_base, ir.entry_va);
    report(PASS, "%u seções, %u DLLs, %u símbolos",
           ir.section_count, ir.import_count, ir.symbol_count);

    int has_text = 0;
    for (uint32_t i = 0; i < ir.section_count; i++)
        if (strcmp(ir.sections[i].name, ".text") == 0) has_text = 1;
    if (has_text) report(PASS, "seção .text presente");
    else { report(FAIL, "sem .text"); g_fail++; }

    if (out_ir != NULL) {
        *out_ir = ir;
    } else {
        pre_ir_free(&ir);
        file_reader_close(&fr);
    }
    return 0;
}

/* ---------- 4. Decoder ---------- */
static int test_decoder(const char *path, const PreIR *ir)
{
    printf("[DECODER]\n");
    if (path == NULL || ir == NULL) { report(INFO, "sem alvo, pulando"); return 0; }

    const SectionEntry *text = NULL;
    for (uint32_t i = 0; i < ir->section_count; i++)
        if (strcmp(ir->sections[i].name, ".text") == 0) { text = &ir->sections[i]; break; }
    if (text == NULL) { report(WARN, "sem .text, pulando"); return 0; }

    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        report(FAIL, "abrir: %s", err); g_fail++; return -1;
    }

    int fails = 0;
    for (int b = 0; b < 2; b++) {
        DecoderBackend backend = b ? BACKEND_CAPSTONE : BACKEND_NATIVE;
        const char *bname = b ? "capstone" : "native";
        uint64_t off = text->raw_offset;
        int ok = 0;
        for (int k = 0; k < 5; k++) {
            DecodedInsn insn;
            int n = decode_one_backend(backend, &fr, off, 0, &insn, err, sizeof(err));
            if (n <= 0) break;
            ok++;
            off += n;
        }
        if (ok >= 3) report(PASS, "backend %s decodificou %d/5 instruções", bname, ok);
        else { report(FAIL, "backend %s: %d/5 instruções", bname, ok); fails++; }
    }
    if (fails) g_fail++;
    file_reader_close(&fr);
    return fails ? -1 : 0;
}

/* ---------- 5. CFG ---------- */
static int test_cfg(const char *path, const PreIR *ir)
{
    printf("[CFG]\n");
    if (path == NULL || ir == NULL) { report(INFO, "sem alvo, pulando"); return 0; }

    const SectionEntry *text = NULL;
    for (uint32_t i = 0; i < ir->section_count; i++)
        if (strcmp(ir->sections[i].name, ".text") == 0) { text = &ir->sections[i]; break; }
    if (text == NULL) { report(WARN, "sem .text, pulando"); return 0; }

    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        report(FAIL, "abrir: %s", err); g_fail++; return -1;
    }
    uint64_t va_base = ir->image_base + text->va - text->raw_offset;
    InsnList insns = {0};
    if (disasm_collect(&fr, text->raw_offset, text->raw_size, va_base,
                       BACKEND_NATIVE, &insns, err, sizeof(err)) != 0) {
        report(FAIL, "disasm_collect: %s", err);
        file_reader_close(&fr);
        g_fail++;
        return -1;
    }
    report(PASS, "%u instruções coletadas", insns.count);

    CFG cfg = {0};
    if (cfg_build(&insns, &cfg, err, sizeof(err)) != 0) {
        report(FAIL, "cfg_build: %s", err);
        free(insns.insns);
        file_reader_close(&fr);
        g_fail++;
        return -1;
    }
    report(PASS, "%u blocos básicos", cfg.block_count);

    uint32_t total_succ = 0;
    for (uint32_t i = 0; i < cfg.block_count; i++)
        total_succ += cfg.blocks[i].succ_count;
    if (total_succ > 0) report(PASS, "%u arestas no CFG", total_succ);
    else report(WARN, "nenhuma aresta (binário trivial?)");

    cfg_free(&cfg);
    free(insns.insns);
    file_reader_close(&fr);
    return 0;
}

/* ---------- 6. Symbols ---------- */
static int test_symbols(const PreIR *ir)
{
    printf("[SYMBOLS]\n");
    if (ir == NULL) { report(INFO, "sem alvo, pulando"); return 0; }
    if (ir->symbol_count > 0) {
        report(PASS, "%u símbolos extraídos", ir->symbol_count);
        for (uint32_t i = 0; i < ir->symbol_count && i < 3; i++)
            printf("        0x%llx %s\n",
                   (unsigned long long)ir->symbols[i].va,
                   ir->symbols[i].name);
    } else {
        report(WARN, "sem símbolos (binário stripped?)");
    }
    return 0;
}

/* ---------- 7. Functions ---------- */
static int test_functions(const char *path, const PreIR *ir)
{
    printf("[FUNCTIONS]\n");
    if (path == NULL || ir == NULL) { report(INFO, "sem alvo, pulando"); return 0; }

    const SectionEntry *text = NULL;
    for (uint32_t i = 0; i < ir->section_count; i++)
        if (strcmp(ir->sections[i].name, ".text") == 0) { text = &ir->sections[i]; break; }
    if (text == NULL) { report(WARN, "sem .text, pulando"); return 0; }

    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        report(FAIL, "abrir: %s", err); g_fail++; return -1;
    }
    uint64_t va_base = ir->image_base + text->va - text->raw_offset;
    InsnList insns = {0};
    if (disasm_collect(&fr, text->raw_offset, text->raw_size, va_base,
                       BACKEND_NATIVE, &insns, err, sizeof(err)) != 0) {
        report(FAIL, "disasm_collect: %s", err);
        file_reader_close(&fr); g_fail++; return -1;
    }
    CFG cfg = {0};
    if (cfg_build(&insns, &cfg, err, sizeof(err)) != 0) {
        report(FAIL, "cfg_build: %s", err);
        free(insns.insns); file_reader_close(&fr); g_fail++; return -1;
    }
    FunctionList fl = {0};
    if (functions_build(&insns, &cfg, ir, &fl, err, sizeof(err)) != 0) {
        report(FAIL, "functions_build: %s", err);
        cfg_free(&cfg); free(insns.insns); file_reader_close(&fr);
        g_fail++; return -1;
    }
    report(PASS, "%u funções identificadas (%u chamadas externas)",
           fl.count, fl.external_calls);
    if (fl.count > 0) {
        report(INFO, "primeira: 0x%llx %s (%u blocos, %u calls)",
               (unsigned long long)fl.entries[0].start_va,
               fl.entries[0].name,
               fl.entries[0].block_count,
               fl.entries[0].call_count);
    }
    functions_free(&fl);
    cfg_free(&cfg);
    free(insns.insns);
    file_reader_close(&fr);
    return 0;
}

/* ---------- 8. Patterns ---------- */
static int test_patterns(const char *path, const PreIR *ir)
{
    printf("[PATTERNS]\n");
    if (path == NULL || ir == NULL) { report(INFO, "sem alvo, pulando"); return 0; }

    const SectionEntry *text = NULL;
    for (uint32_t i = 0; i < ir->section_count; i++)
        if (strcmp(ir->sections[i].name, ".text") == 0) { text = &ir->sections[i]; break; }
    if (text == NULL) { report(WARN, "sem .text, pulando"); return 0; }

    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        report(FAIL, "abrir: %s", err); g_fail++; return -1;
    }
    uint64_t va_base = ir->image_base + text->va - text->raw_offset;
    InsnList insns = {0};
    if (disasm_collect(&fr, text->raw_offset, text->raw_size, va_base,
                       BACKEND_NATIVE, &insns, err, sizeof(err)) != 0) {
        report(FAIL, "disasm_collect: %s", err);
        file_reader_close(&fr); g_fail++; return -1;
    }
    CFG cfg = {0};
    if (cfg_build(&insns, &cfg, err, sizeof(err)) != 0) {
        report(FAIL, "cfg_build: %s", err);
        free(insns.insns); file_reader_close(&fr); g_fail++; return -1;
    }
    FunctionList fl = {0};
    if (functions_build(&insns, &cfg, ir, &fl, err, sizeof(err)) != 0) {
        report(FAIL, "functions_build: %s", err);
        cfg_free(&cfg); free(insns.insns); file_reader_close(&fr); g_fail++; return -1;
    }
    if (patterns_analyze(&insns, &cfg, ir, &fl, err, sizeof(err)) != 0) {
        report(FAIL, "patterns_analyze: %s", err);
    } else {
        uint32_t fp = 0, canary = 0, tail = 0, sw = 0, leaf = 0;
        for (uint32_t i = 0; i < fl.count; i++) {
            uint32_t f = fl.entries[i].flags;
            if (f & FUNC_FLAG_FP) fp++;
            if (f & FUNC_FLAG_CANARY) canary++;
            if (f & FUNC_FLAG_TAILCALL) tail++;
            if (f & FUNC_FLAG_SWITCH) sw++;
            if (f & FUNC_FLAG_LEAF) leaf++;
        }
        report(PASS, "%u funções analisadas", fl.count);
        report(INFO, "fp=%u canary=%u tail=%u switch=%u leaf=%u",
               fp, canary, tail, sw, leaf);
    }
    functions_free(&fl);
    cfg_free(&cfg);
    free(insns.insns);
    file_reader_close(&fr);
    return 0;
}

/* ---------- doctor_run ---------- */
int doctor_run(const char *target)
{
    printf("=== doxreveng doctor ===\n\n");
    test_build();
    printf("\n");
    test_file_reader(target);
    printf("\n");

    PreIR ir;
    memset(&ir, 0, sizeof(ir));
    int have_ir = (test_pe_parser(target, &ir) == 0);
    printf("\n");

    if (have_ir) {
        test_decoder(target, &ir);
        printf("\n");
        test_cfg(target, &ir);
        printf("\n");
        test_symbols(&ir);
        printf("\n");
        test_functions(target, &ir);
        printf("\n");
        test_patterns(target, &ir);
        printf("\n");
        pre_ir_free(&ir);
    }

    printf("=== %s ===\n", g_fail == 0 ? "TODOS OS TESTES PASSARAM" : "FALHAS DETECTADAS");
    return g_fail == 0 ? 0 : 1;
}

/* ---------- preflight_run ---------- */
int preflight_run(const char *path, const char *operation,
                  DecoderBackend backend)
{
    if (path == NULL) {
        fprintf(stderr, "[PREFLIGHT] caminho NULL\n");
        return 1;
    }
    if (operation == NULL) operation = "parse";

    /* 1. Arquivo existe e é legível? */
    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        fprintf(stderr, "[PREFLIGHT] falha ao abrir '%s': %s\n", path, err);
        return 1;
    }

    /* 2. É um PE válido? */
    PreIR ir;
    if (pe_parse(&fr, &ir, err, sizeof(err)) != 0) {
        fprintf(stderr, "[PREFLIGHT] '%s' não é PE válido: %s\n", path, err);
        file_reader_close(&fr);
        return 1;
    }

    /* 3. Backend escolhido está disponível? */
    {
        DecodedInsn dummy;
        uint8_t one_byte = 0x90;  /* nop */
        FileReader fake = {0};
        fake.data = &one_byte;
        fake.size = 1;
        int n = decode_one_backend(backend, &fake, 0, 0, &dummy, err, sizeof(err));
        if (n <= 0) {
            fprintf(stderr, "[PREFLIGHT] backend %s indisponível: %s\n",
                    backend == BACKEND_CAPSTONE ? "capstone" : "native", err);
            pre_ir_free(&ir);
            file_reader_close(&fr);
            return 1;
        }
    }

    /* 4. Se a operação precisa de .text, ele existe e tem tamanho? */
    if (strcmp(operation, "disasm") == 0 || strcmp(operation, "cfg") == 0) {
        const SectionEntry *text = NULL;
        for (uint32_t i = 0; i < ir.section_count; i++)
            if (strcmp(ir.sections[i].name, ".text") == 0) { text = &ir.sections[i]; break; }
        if (text == NULL) {
            fprintf(stderr, "[PREFLIGHT] seção .text ausente em '%s'\n", path);
            pre_ir_free(&ir);
            file_reader_close(&fr);
            return 1;
        }
        if (text->raw_size == 0) {
            fprintf(stderr, "[PREFLIGHT] .text vazio em '%s'\n", path);
            pre_ir_free(&ir);
            file_reader_close(&fr);
            return 1;
        }
        /* entry point está dentro do .text? (aviso, não erro) */
        uint32_t text_end = text->va + text->virtual_size;
        if (ir.entry_va < text->va || ir.entry_va >= text_end) {
            fprintf(stderr,
                    "[PREFLIGHT] aviso: entry_va=0x%x fora do .text [0x%x-0x%x)\n",
                    ir.entry_va, text->va, text_end);
        }
    }

    pre_ir_free(&ir);
    file_reader_close(&fr);
    return 0;
}
