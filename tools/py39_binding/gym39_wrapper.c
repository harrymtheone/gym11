#include <Python.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

typedef PyObject *(*module_init_fn)(void);

static void *payload_handle;

PyMODINIT_FUNC PyInit_gym_39(void) {
    Dl_info wrapper_info;
    char payload_path[PATH_MAX];
    char *separator;
    module_init_fn initialize;

    if (dladdr((void *)&PyInit_gym_39, &wrapper_info) == 0 ||
        wrapper_info.dli_fname == NULL) {
        PyErr_SetString(PyExc_ImportError, "cannot locate gym_39.so");
        return NULL;
    }

    if (strlen(wrapper_info.dli_fname) >= sizeof(payload_path)) {
        PyErr_SetString(PyExc_ImportError, "gym_39.so path is too long");
        return NULL;
    }
    strcpy(payload_path, wrapper_info.dli_fname);
    separator = strrchr(payload_path, '/');
    if (separator == NULL) {
        strcpy(payload_path, "_gym_38_py39.so");
    } else {
        strcpy(separator + 1, "_gym_38_py39.so");
    }

    payload_handle = dlopen(payload_path, RTLD_NOW | RTLD_GLOBAL);
    if (payload_handle == NULL) {
        PyErr_Format(PyExc_ImportError, "cannot load %s: %s", payload_path, dlerror());
        return NULL;
    }

    dlerror();
    initialize = (module_init_fn)dlsym(payload_handle, "PyInit_gym_38");
    if (initialize == NULL) {
        PyErr_Format(
            PyExc_ImportError,
            "cannot resolve PyInit_gym_38 from %s: %s",
            payload_path,
            dlerror()
        );
        return NULL;
    }
    return initialize();
}
