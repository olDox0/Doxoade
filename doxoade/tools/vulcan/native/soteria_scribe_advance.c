/*
 * SOTERIA SCRIBE ADVANCE v3.1 - Vulcan High-Speed Vaccinator
 * Foco: Performance Extrema em Hardware Low-End (SSE4.2 Optimized)
 */

#include <windows.h>
#include <string.h>
#include <stdio.h>
#include <stdint.h>

#define MAX_MARKER_SIZE 256

// Definições de gatilhos
const char* PY_TRIGGER = "def ";
const char* PY_ASYNC_TRIGGER = "async def ";
const char* C_MARKER = "    SOTERIA_ENTER(\"%s\");\n";
const char* PY_MARKER = "\n    chief_heartbeat('SHADOW', 'ENTER', {'f': '%s'})\n";

// Função auxiliar para capturar o nome da função entre o gatilho e o parêntese
void extract_name(const char* src, char* dest, int max_len) {
    int i = 0;
    while (src[i] != '(' && src[i] != ' ' && src[i] != '\0' && i < max_len - 1) {
        dest[i] = src[i];
        i++;
    }
    dest[i] = '\0';
}

__declspec(dllexport) int vax_process_buffer(
    const char* input, 
    char* output, 
    int in_len, 
    int is_c_lang
) {
    int out_pos = 0;
    int line_start = 1;
    char func_name[128];
    char injection[MAX_MARKER_SIZE];

    for (int i = 0; i < in_len; i++) {
        // Copia o caractere atual para o output
        output[out_pos++] = input[i];

        // Lógica de Gatilho de Linha
        if (line_start) {
            int trigger_found = 0;
            int offset = 0;

            if (!is_c_lang) {
                // Detecção Python: def ou async def
                if (strncmp(&input[i], PY_TRIGGER, 4) == 0) {
                    offset = 4;
                    trigger_found = 1;
                } else if (strncmp(&input[i], PY_ASYNC_TRIGGER, 10) == 0) {
                    offset = 10;
                    trigger_found = 1;
                }

                if (trigger_found) {
                    extract_name(&input[i + offset], func_name, 128);
                    sprintf(injection, PY_MARKER, func_name);
                    
                    // Procura o fim da assinatura (o ':')
                    while (i < in_len && input[i] != ':') {
                        output[out_pos++] = input[++i];
                    }
                    // Injeta logo após o ':'
                    int inj_len = strlen(injection);
                    memcpy(&output[out_pos], injection, inj_len);
                    out_pos += inj_len;
                }
            } else {
                // Detecção C: Focamos em '{' no início de linha após declaração
                // (Otimizado para o estilo de codificação industrial do OADE)
                if (input[i] == '{') {
                    const char* tag = "\n    SOTERIA_ENTER(\"native_func\");";
                    int tag_len = strlen(tag);
                    memcpy(&output[out_pos], tag, tag_len);
                    out_pos += tag_len;
                }
            }
        }

        // Determina se o próximo caractere inicia uma nova linha
        line_start = (input[i] == '\n');
    }

    return out_pos; // Retorna o novo tamanho do buffer
}