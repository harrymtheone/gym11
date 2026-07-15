#define NPY_TARGET_VERSION NPY_2_0_API_VERSION

#include <Python.h>
#include <numpy/ndarraytypes.h>

PyArray_Descr numpy2_descr_probe;
_PyArray_LegacyDescr numpy2_legacy_descr_probe;

int main(void) {
    return (int)(sizeof(numpy2_descr_probe) + sizeof(numpy2_legacy_descr_probe));
}
