/* main.c — dispatch de comandos do doxreveng (Fases 1–4) */
#include "file_reader.h"
#include "pe_parser.h"
#include "pre_ir.h"
#include "decoder_backend.h"
#include "disasm.h"
#include "cfg.h"
#include "doctor.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void print_usage(const char *prog)
{
    fprintf(stderr,
        "uso: %s <arquivo.exe>                             -> parse PE (JSON)\n"
        "     %s disasm <exe> [--off N --len M] [--backend native|capstone]\n"
        "     %s cfg <exe> [--format text|dot] [--limit N] [--backend native|capstone]\n"
        "     %s doctor [<exe>]                              -> self-diagnóstico\n",
        prog, prog, prog, prog);
}

static DecoderBackend parse_backend(const char *s)
{
    if (s == NULL) return BACKEND_CAPSTONE;
    if (strcmp(s, "native") == 0) return BACKEND_NATIVE;
    return BACKEND_CAPSTONE;
}

int main(int argc, char **argv)
{
    if (argc < 2) { print_usage(argv[0]); return 1; }

    int mode = 0;  /* 0=json, 1=disasm, 2=cfg, 3=doctor */
    int argi = 1;
    if (strcmp(argv[1], "disasm") == 0) { mode = 1; argi = 2; }
    else if (strcmp(argv[1], "cfg") == 0) { mode = 2; argi = 2; }
    else if (strcmp(argv[1], "doctor") == 0) { mode = 3; argi = 2; }

    if (mode == 3) {
        const char *target = (argi < argc) ? argv[argi] : NULL;
        return doctor_run(target);
    }

    if (argi >= argc) { print_usage(argv[0]); return 1; }
    const char *path = argv[argi++];

    uint64_t off = 0, len = 0;
    int has_off = 0, has_len = 0;
    int fmt_dot = 0;
    uint32_t limit = 0;
    DecoderBackend backend = BACKEND_CAPSTONE;

    while (argi < argc) {
        if (strcmp(argv[argi], "--off") == 0 && argi + 1 < argc)
            { off = strtoull(argv[++argi], NULL, 0); has_off = 1; }
        else if (strcmp(argv[argi], "--len") == 0 && argi + 1 < argc)
            { len = strtoull(argv[++argi], NULL, 0); has_len = 1; }
        else if (strcmp(argv[argi], "--format") == 0 && argi + 1 < argc) {
            argi++;
            if (strcmp(argv[argi], "dot") == 0) fmt_dot = 1;
        }
        else if (strcmp(argv[argi], "--limit") == 0 && argi + 1 < argc)
            { limit = (uint32_t)strtoul(argv[++argi], NULL, 0); }
        else if (strcmp(argv[argi], "--backend") == 0 && argi + 1 < argc)
            { backend = parse_backend(argv[++argi]); }
        argi++;
    }

    /* Pre-flight: valida que a operação pode rodar. */
    if (mode == 1 || mode == 2) {
        const char *op = (mode == 1) ? "disasm" : "cfg";
        if (preflight_run(path, op, backend) != 0) {
            fprintf(stderr, "doxreveng: preflight falhou, abortando.\n");
            return 1;
        }
    }

    FileReader fr;
    char err[256] = {0};
    if (file_reader_open(path, &fr, err, sizeof(err)) != 0) {
        fprintf(stderr, "doxreveng: erro ao ler '%s': %s\n", path, err);
        return 1;
    }

    PreIR ir;
    if (pe_parse(&fr, &ir, err, sizeof(err)) != 0) {
        fprintf(stderr, "doxreveng: erro ao parsear '%s': %s\n", path, err);
        file_reader_close(&fr);
        return 1;
    }

    int rc = 0;
    if (mode == 1) {
        if (has_off && has_len)
            rc = disasm_range(&fr, off, len, ir.image_base, backend, &ir,
                              stdout, err, sizeof(err));
        else
            rc = disasm_text_section(&fr, &ir, backend, stdout, err, sizeof(err));
        if (rc < 0) fprintf(stderr, "doxreveng: erro: %s\n", err);
        else fprintf(stderr, "doxreveng: %d instruções desmontadas\n", rc);
    }
    else if (mode == 2) {
        const SectionEntry *text = NULL;
        for (uint32_t i = 0; i < ir.section_count; i++)
            if (strcmp(ir.sections[i].name, ".text") == 0) { text = &ir.sections[i]; break; }

        if (text == NULL) {
            fprintf(stderr, "doxreveng: seção .text não encontrada\n");
            rc = -1;
        } else {
            uint64_t va_base = ir.image_base + text->va - text->raw_offset;
            InsnList insns = {0};
            if (disasm_collect(&fr, text->raw_offset, text->raw_size,
                               va_base, backend, &insns, err, sizeof(err)) != 0) {
                fprintf(stderr, "doxreveng: erro no disasm: %s\n", err);
                rc = -1;
            } else {
                CFG cfg = {0};
                if (cfg_build(&insns, &cfg, err, sizeof(err)) != 0) {
                    fprintf(stderr, "doxreveng: erro no CFG: %s\n", err);
                    rc = -1;
                } else {
                    if (limit > 0 && cfg.block_count > limit) {
                        CFG tmp = cfg; tmp.block_count = limit;
                        if (fmt_dot) cfg_print_dot(&tmp, &insns, stdout);
                        else cfg_print_text(&tmp, &insns, stdout);
                    } else if (fmt_dot) {
                        cfg_print_dot(&cfg, &insns, stdout);
                    } else {
                        cfg_print_text(&cfg, &insns, stdout);
                    }
                    fprintf(stderr, "doxreveng: %u blocos básicos\n", cfg.block_count);
                    cfg_free(&cfg);
                }
                free(insns.insns);
            }
        }
    }
    else {
        if (pre_ir_print_json(&ir, stdout) != 0) {
            fprintf(stderr, "doxreveng: erro ao serializar JSON\n");
            rc = -1;
        }
    }

    pre_ir_free(&ir);
    file_reader_close(&fr);
    return rc < 0 ? 1 : 0;
}
