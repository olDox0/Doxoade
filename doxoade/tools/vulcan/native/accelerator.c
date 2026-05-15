#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>

/* --- PROTÓTIPOS EXTERNOS (ASM SSE2) --- */

// RCX = buf, RDX = len, R8 = target
extern long long nexus_asm_fast_tag_check(const char* buf, size_t len, char target);

// RCX = buf, RDX = len
extern long long nexus_asm_structural_weight(const char* buf, size_t len);

/* --- AUXILIARES INTERNOS (C PURO) --- */

static void *nexus_memmem(const void *haystack, size_t h_len, const void *needle, size_t n_len) {
    if (n_len == 0) return (void *)haystack;
    if (h_len < n_len) return NULL;
    const unsigned char *h = (const unsigned char *)haystack;
    const unsigned char *n = (const unsigned char *)needle;
    for (size_t i = 0; i <= h_len - n_len; i++) {
        if (h[i] == n[0] && memcmp(&h[i], n, n_len) == 0) return (void *)&h[i];
    }
    return NULL;
}

static int fast_search_in_file(const char *filename, const char **patterns, int num_patterns) {
    FILE *fp = fopen(filename, "rb");
    if (!fp) return 0;
    char buffer[8192];
    size_t bytes_read = fread(buffer, 1, sizeof(buffer), fp);
    fclose(fp);
    if (bytes_read == 0) return 0;
    for (int i = 0; i < num_patterns; i++) {
        if (nexus_memmem(buffer, bytes_read, patterns[i], strlen(patterns[i])) != NULL) return 1;
    }
    return 0;
}

/* --- FUNÇÕES EXPOSTAS AO PYTHON --- */

// 1. Limpeza de código .pyx (Otimização de RAM)
/**
 * vulcan_native_strip: Limpeza de código com Zero-Allocation Python.
 * Processa o buffer bruto e remove comentários/espaços em um único passo.
 */
static PyObject* vulcan_native_strip(PyObject* self, PyObject* args) {
    const char *input;
    Py_ssize_t len;
    if (!PyArg_ParseTuple(args, "s#", &input, &len)) return NULL;

    // Alocação única no heap do C (muito mais rápida que strings Python)
    char *output = (char *)malloc(len + 1);
    if (!output) return PyErr_NoMemory();

    const char *p_in = input;
    char *p_out = output;
    int in_comment = 0;

    while (*p_in) {
        if (!in_comment && *p_in == '#' && strncmp(p_in, "# cython:", 8) != 0) {
            in_comment = 1;
        }
        
        if (in_comment) {
            if (*p_in == '\n') {
                in_comment = 0;
                *p_out++ = *p_in;
            }
        } else {
            // Remove linhas vazias redundantes (Economia de parser)
            if (*p_in == '\n' && *(p_in + 1) == '\n') {
                p_in++;
                continue;
            }
            *p_out++ = *p_in;
        }
        p_in++;
    }
    *p_out = '\0';

    PyObject *result = PyUnicode_FromString(output);
    free(output); // Libera a memória C imediatamente
    return result;
}

// 2. Scan em lote de arquivos CLI (Otimização de Ciclos)
static PyObject* vulcan_fast_scan(PyObject* self, PyObject* args) {
    PyObject *file_list;
    if (!PyArg_ParseTuple(args, "O", &file_list)) return NULL;
    const char *patterns[] = {"@click.", "[VULCAN-SKIP]", "import click"};
    PyObject *result_list = PyList_New(0);
    Py_ssize_t n = PyList_Size(file_list);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = PyList_GetItem(file_list, i);
        const char *filename = PyUnicode_AsUTF8AndSize(item, NULL);
        if (fast_search_in_file(filename, patterns, 3)) PyList_Append(result_list, item);
    }
    return result_list;
}

// 3. Diagnose de Peso Estrutural (Motor ASM)
static PyObject* vulcan_native_diagnose(PyObject* self, PyObject* args) {
    const char *buf;
    Py_ssize_t len;
    if (!PyArg_ParseTuple(args, "y#", &buf, &len)) return NULL;
    long long packed = nexus_asm_structural_weight(buf, (size_t)len);
    return Py_BuildValue("{sI,sI}", "nodes", (unsigned int)(packed & 0xFFFFFFFF), "loops", (unsigned int)(packed >> 32));
}

// 4. Diagnose Zero-Allocation (Segurança de RAM)
static PyObject* vulcan_zero_alloc_diagnose(PyObject* self, PyObject* args) {
    const char *buffer;
    Py_ssize_t length;
    if (!PyArg_ParseTuple(args, "s#", &buffer, &length)) return NULL;
    uint32_t n=0, l=0, d=0, cur_d=0;
    const char *p = buffer;
    const char *end = buffer + length;
    while (p < end) {
        char c = *p;
        if (c=='(' || c=='[' || c=='{' || c=='=') n++;
        else if (c==':') { cur_d++; if (cur_d > d) d = cur_d; }
        else if (c=='\n') cur_d = 0;
        if (c == 'f' && (p+3 < end) && p[1]=='o' && p[2]=='r' && p[3]==' ') { l++; p+=3; }
        p++;
    }
    return Py_BuildValue("{sI,sI,sI}", "nodes", n, "loops", l, "depth", d);
}

// 5. Busca simples SSE2
static PyObject* vulcan_asm_check(PyObject* self, PyObject* args) {
    const char *buf;
    Py_ssize_t len;
    char target;
    if (!PyArg_ParseTuple(args, "s#c", &buf, &len, &target)) return NULL;
    return nexus_asm_fast_tag_check(buf, (size_t)len, target) ? Py_True : Py_False;
}

/**
 * vulcan_get_hot_vars: Varredura linear de alta velocidade.
 * Identifica nomes de variáveis que são alvos de atribuição ou loops.
 */
static PyObject* vulcan_get_hot_vars(PyObject* self, PyObject* args) {
    const char *code;
    Py_ssize_t len;
    if (!PyArg_ParseTuple(args, "y#", &code, &len)) return NULL;

    PyObject *var_set = PySet_New(NULL);
    const char *p = code;
    const char *end = code + len;

    while (p < end) {
        // Busca simples por 'for ' ou '=' 
        if ((*p == 'f' && memcmp(p, "for ", 4) == 0) || (*p == '=')) {
            const char *start = p;
            // Lógica de retrocesso para capturar o nome da variável (Zero-Allocation)
            if (*p == '=') {
                start--;
                while (start > code && (*start == ' ' || *start == '\t')) start--;
                const char *v_end = start + 1;
                while (start > code && *start != ' ' && *start != '\n' && *start != '\t') start--;
                PyObject *v = PyUnicode_FromStringAndSize(start + 1, v_end - start - 1);
                PySet_Add(var_set, v);
                Py_DECREF(v);
            }
        }
        p++;
    }
    return var_set;
}

/* --- TABELA DE MÉTODOS --- */

static PyMethodDef VulcanMethods[] = {
    {"native_strip",    vulcan_native_strip,    METH_VARARGS, "Limpa código .pyx em C"},
    {"fast_scan",       vulcan_fast_scan,       METH_VARARGS, "Scan de Smart Skip"},
    {"native_diagnose", vulcan_native_diagnose, METH_VARARGS, "Raio-X de Hardware via ASM"},
    {"zero_alloc_diagnose", vulcan_zero_alloc_diagnose, METH_VARARGS, "Diagnóstico sem RAM"},
    {"asm_check",       vulcan_asm_check,       METH_VARARGS, "Busca SSE2"},
    {"get_hot_vars",       vulcan_get_hot_vars, METH_VARARGS, "variaveis "},
    {NULL, NULL, 0, NULL}
};

/* --- DEFINIÇÃO DO MÓDULO --- */

static struct PyModuleDef vulcan_acc_module = {
    PyModuleDef_HEAD_INIT, "vulcan_accelerator", "Nexus Hardware Accelerator", -1, VulcanMethods
};

PyMODINIT_FUNC PyInit_vulcan_accelerator(void) {
    return PyModule_Create(&vulcan_acc_module);
}

/**
 * vulcan_fast_read_strip: O ápice da economia de RAM para o N2808.
 * Abre o arquivo, limpa o código em RAM C e entrega ao Python apenas o necessário.
 */
static PyObject* vulcan_fast_read_strip(PyObject* self, PyObject* args) {
    const char *filename;
    if (!PyArg_ParseTuple(args, "s", &filename)) return NULL;

    FILE *f = fopen(filename, "rb");
    if (!f) return PyErr_SetFromErrno(PyExc_IOError);

    // Medição de tamanho para alocação única
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    // Buffer para leitura bruta
    char *raw_buf = (char *)malloc(size + 1);
    if (!raw_buf) {
        fclose(f);
        return PyErr_NoMemory();
    }
    
    size_t bytes_read = fread(raw_buf, 1, size, f);
    fclose(f);
    raw_buf[bytes_read] = '\0';

    // Buffer para o resultado limpo (mesmo tamanho por segurança)
    char *clean_buf = (char *)malloc(size + 1);
    if (!clean_buf) {
        free(raw_buf);
        return PyErr_NoMemory();
    }

    const char *p_in = raw_buf;
    char *p_out = clean_buf;
    int in_comment = 0;

    // Loop de Passada Única (O(n))
    while (*p_in) {
        // Detecta início de comentário (preserva diretivas cython)
        if (!in_comment && *p_in == '#' && strncmp(p_in, "# cython:", 8) != 0) {
            in_comment = 1;
        }
        
        if (in_comment) {
            if (*p_in == '\n') {
                in_comment = 0;
                *p_out++ = *p_in; // Mantém a quebra de linha para o parser
            }
        } else {
            // Remove linhas vazias redundantes ( \n\n -> \n )
            if (*p_in == '\n' && (*(p_in + 1) == '\n' || *(p_in + 1) == '\r')) {
                p_in++;
                continue;
            }
            *p_out++ = *p_in;
        }
        p_in++;
    }
    *p_out = '\0';

    // Cria o objeto Python final
    PyObject *py_string = PyUnicode_FromString(clean_buf);

    // [VITAL] Libera toda a memória C antes de voltar ao Python
    free(raw_buf);
    free(clean_buf);

    return py_string;
}