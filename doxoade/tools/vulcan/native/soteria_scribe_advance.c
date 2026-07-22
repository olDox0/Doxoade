// doxoade\tools\vulcan\native\soteria_scribe_advance.c
/*
 * SOTERIA SCRIBE ADVANCE v4.0 - Vulcan High-Speed Vaccinator
 * Foco: Performance Extrema + Buffer Safety (Bounds Checking)
 */
#include <windows.h>
#include <string.h>
#include <stdio.h>
#include <stdint.h>

#define MAX_MARKER_SIZE 512
#define MAX_FUNC_NAME   256

const char* PY_TRIGGER       = "def ";
const char* PY_ASYNC_TRIGGER = "async def ";
const char* C_MARKER         = "    SOTERIA_ENTER(\"%s\");\n";
const char* PY_MARKER        = "\nchief_heartbeat('SHADOW', 'ENTER', {'f': '%s'})\n";

/* ═══════════════════════════════════════════════════════════════════
 * extract_name - Extrai nome de função com bounds checking
 * ═══════════════════════════════════════════════════════════════════ */
void extract_name(const char* src, char* dest, int max_len) {
    if (max_len <= 0) {
        if (max_len == 0) return;
        dest[0] = '\0';
        return;
    }
    
    int i = 0;
    while (src[i] != '(' && src[i] != ' ' && src[i] != '\0' && i < max_len - 1) {
        dest[i] = src[i];
        i++;
    }
    dest[i] = '\0';
}

/* ═══════════════════════════════════════════════════════════════════
 * vax_process_buffer - Vaccinator com Bounds Checking Completo
 * 
 * CORREÇÃO v4.0: Adicionado parâmetro out_len para proteção contra
 * buffer overflow. Todas as escritas em output são verificadas.
 * ═══════════════════════════════════════════════════════════════════ */
__declspec(dllexport) int vax_process_buffer(
    const char* input,
    char* output,
    int in_len,
    int out_len,      /* 🆕 NOVO: Tamanho do buffer de saída */
    int is_c_lang
) {
    /* Validação de entrada */
    if (!input || !output || in_len <= 0 || out_len <= 0) return -1;
    
    int out_pos = 0;
    int line_start = 1;
    char func_name[MAX_FUNC_NAME];
    char injection[MAX_MARKER_SIZE];

    for (int i = 0; i < in_len; i++) {
        /* 🛡️ Bounds check: espaço para o caractere atual */
        if (out_pos >= out_len - 1) break;
        
        output[out_pos++] = input[i];

        if (line_start) {
            int trigger_found = 0;
            int offset = 0;

            if (!is_c_lang) {
                // Verifica triggers Python com bounds check no input
                if (i + 4 <= in_len && strncmp(&input[i], PY_TRIGGER, 4) == 0) {
                    offset = 4;
                    trigger_found = 1;
                } else if (i + 11 <= in_len && strncmp(&input[i], "async def ", 11) == 0) {
                    offset = 11;  // Tamanho de "async def "
                    trigger_found = 1;
                }

                if (trigger_found) {
                    extract_name(&input[i + offset], func_name, MAX_FUNC_NAME);
                    snprintf(injection, MAX_MARKER_SIZE, PY_MARKER, func_name);

                    /* Avança até ':' com bounds check */
                    while (i < in_len && input[i] != ':' && out_pos < out_len - 1) {
                        output[out_pos++] = input[++i];
                    }

                    /* 🛡️ Bounds check: espaço para a injeção */
                    int inj_len = (int)strlen(injection);
                    if (out_pos + inj_len < out_len) {
                        memcpy(&output[out_pos], injection, inj_len);
                        out_pos += inj_len;
                    }
                }
            } else {
                if (input[i] == '{') {
                    // 🛡️ Lookahead: verifica se já existe SOTERIA_ENTER nas próximas linhas
                    int has_soteria = 0;
                    int lookahead_pos = i + 1;
                    // Pula whitespace e newline
                    while (lookahead_pos < in_len && (input[lookahead_pos] == ' ' || 
                           input[lookahead_pos] == '\t' || input[lookahead_pos] == '\n' || 
                           input[lookahead_pos] == '\r')) {
                        lookahead_pos++;
                    }
                    // Verifica se a próxima coisa não-vazia é SOTERIA_ENTER
                    if (lookahead_pos + 13 < in_len && 
                        strncmp(&input[lookahead_pos], "SOTERIA_ENTER", 13) == 0) {
                        has_soteria = 1;
                    }
                    
                    if (!has_soteria) {
                        const char* tag = "\n    SOTERIA_ENTER(\"native_func\");";
                        int tag_len = (int)strlen(tag);
                        if (out_pos + tag_len < out_len) {
                            memcpy(&output[out_pos], tag, tag_len);
                            out_pos += tag_len;
                        }
                    }
                }
            }

        }
        line_start = (input[i] == '\n');
    }
    
    /* Null-terminate se houver espaço */
    if (out_pos < out_len) {
        output[out_pos] = '\0';
    } else {
        output[out_len - 1] = '\0';
    }
    
    return out_pos;
}