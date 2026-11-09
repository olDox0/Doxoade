// doxoade/tools/rev_eng/src/main.c
/* main.c — dispatch de comandos do doxreveng (Degrau 0)
 *
 * Uso:
 *   doxreveng <arquivo.exe>           → parse PE, emite JSON em stdout
 *   doxreveng                         → mostra uso
 */
#include "file_reader.h"
#include "pe_parser.h"
#include "pre_ir.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void print_usage(const char *prog)
{
    fprintf(stderr,
            "uso: %s <arquivo.exe>\n"
            "  Lê o PE e emite pré-IR (JSON) em stdout.\n", prog);
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    const char *path = argv[1];

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

    if (pre_ir_print_json(&ir, stdout) != 0) {
        fprintf(stderr, "doxreveng: erro ao serializar JSON\n");
        pre_ir_free(&ir);
        file_reader_close(&fr);
        return 1;
    }

    pre_ir_free(&ir);
    file_reader_close(&fr);
    return 0;
}
