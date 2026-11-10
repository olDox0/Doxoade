/* pre_ir.c — implementação da IR arcaica */
#include "pre_ir.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void json_escape(const char *s, FILE *out)
{
    if (s == NULL) { fputs("\"\"", out); return; }
    fputc('"', out);
    for (const unsigned char *p = (const unsigned char *)s; *p; p++) {
        switch (*p) {
            case '"':  fputs("\\\"", out); break;
            case '\\': fputs("\\\\", out); break;
            case '\n': fputs("\\n",  out); break;
            case '\r': fputs("\\r",  out); break;
            case '\t': fputs("\\t",  out); break;
            default:
                if (*p < 0x20) fprintf(out, "\\u%04x", *p);
                else fputc(*p, out);
                break;
        }
    }
    fputc('"', out);
}

int pre_ir_print_json(const PreIR *ir, FILE *out)
{
    if (ir == NULL || out == NULL) return -1;
    fputc('{', out);

    fputs("\"file\":", out); json_escape(ir->file_path, out);
    fputs(",\"format\":", out); json_escape(ir->format, out);
    fprintf(out, ",\"image_base\":\"0x%llx\"", (unsigned long long)ir->image_base);
    fprintf(out, ",\"entry_va\":\"0x%08x\"", ir->entry_va);

    fputs(",\"sections\":[", out);
    for (uint32_t i = 0; i < ir->section_count; i++) {
        const SectionEntry *s = &ir->sections[i];
        if (i > 0) fputc(',', out);
        fputc('{', out);
        fputs("\"name\":", out); json_escape(s->name, out);
        fprintf(out,
                ",\"va\":\"0x%08x\""
                ",\"virtual_size\":%u"
                ",\"raw_offset\":%u"
                ",\"raw_size\":%u"
                ",\"characteristics\":\"0x%08x\"",
                s->va, s->virtual_size, s->raw_offset, s->raw_size,
                s->characteristics);
        fputc('}', out);
    }
    fputc(']', out);

    fputs(",\"imports\":[", out);
    for (uint32_t i = 0; i < ir->import_count; i++) {
        const ImportEntry *imp = &ir->imports[i];
        if (i > 0) fputc(',', out);
        fputc('{', out);
        fputs("\"dll\":", out); json_escape(imp->dll, out);
        fputs(",\"funcs\":[", out);
        for (uint32_t j = 0; j < imp->func_count; j++) {
            if (j > 0) fputc(',', out);
            json_escape(imp->funcs[j], out);
        }
        fputs("]}", out);
    }
    fputc(']', out);

    fputs(",\"symbols\":[", out);
    for (uint32_t i = 0; i < ir->symbol_count; i++) {
        if (i > 0) fputc(',', out);
        fputc('{', out);
        fprintf(out, "\"va\":\"0x%llx\"", (unsigned long long)ir->symbols[i].va);
        fputs(",\"name\":", out);
        json_escape(ir->symbols[i].name, out);
        fputc('}', out);
    }
    fputc(']', out);

    fputs("}\n", out);
    return 0;
}

void pre_ir_free(PreIR *ir)
{
    if (ir == NULL) return;
    if (ir->sections) { free(ir->sections); ir->sections = NULL; }
    ir->section_count = 0;
    if (ir->imports) {
        for (uint32_t i = 0; i < ir->import_count; i++) {
            ImportEntry *imp = &ir->imports[i];
            if (imp->funcs) {
                for (uint32_t j = 0; j < imp->func_count; j++) free(imp->funcs[j]);
                free(imp->funcs);
                imp->funcs = NULL;
            }
            imp->func_count = 0;
        }
        free(ir->imports);
        ir->imports = NULL;
    }
    ir->import_count = 0;
    if (ir->symbols) {
        for (uint32_t i = 0; i < ir->symbol_count; i++) free(ir->symbols[i].name);
        free(ir->symbols);
        ir->symbols = NULL;
    }
    ir->symbol_count = 0;
}
