#include <Python.h>
#include <stdio.h>
#include <string.h>

/* 
   Busca ultra-rápida de substrings em arquivos para o Smart Skip.
   Retorna 1 se encontrar a tag, 0 caso contrário.
*/
static int fast_search_in_file(const char *filename, const char **patterns, int num_patterns) {
    FILE *fp = fopen(filename, "rb");
    if (!fp) return 0;

    char buffer[8192];
    size_t bytes_read = fread(buffer, 1, sizeof(buffer), fp);
    fclose(fp);

    if (bytes_read == 0) return 0;

    for (int i = 0; i < num_patterns; i++) {
        if (memmem(buffer, bytes_read, patterns[i], strlen(patterns[i])) != NULL) {
            return 1;
        }
    }
    return 0;
}

static PyObject* vulcan_fast_scan(PyObject* self, PyObject* args) {
    PyObject *file_list;
    if (!PyArg_ParseTuple(args, "O", &file_list)) return NULL;

    const char *patterns[] = {"@click.", "[VULCAN-SKIP]", "import click"};
    PyObject *result_list = PyList_New(0);

    Py_ssize_t n = PyList_Size(file_list);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = PyList_GetItem(file_list, i);
        const char *filename = PyUnicode_AsUTF8(item);

        if (fast_search_in_file(filename, patterns, 3)) {
            PyList_Append(result_list, item);
        }
    }
    return result_list;
}

static PyMethodDef VulcanMethods[] = {
    {"fast_scan", vulcan_fast_scan, METH_VARARGS, "Scan de arquivos para Smart Skip"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef vulcan_acc_module = {
    PyModuleDef_HEAD_INIT, "vulcan_accelerator", NULL, -1, VulcanMethods
};

PyMODINIT_FUNC PyInit_vulcan_accelerator(void) {
    return PyModuleCreate(&vulcan_acc_module);
}