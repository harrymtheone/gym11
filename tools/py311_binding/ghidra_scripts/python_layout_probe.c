#include <Python.h>

PyTypeObject pytype_probe;
PyHeapTypeObject heaptype_probe;
PyAsyncMethods async_methods_probe;

int main(void) {
    return (int)(
        sizeof(pytype_probe) +
        sizeof(heaptype_probe) +
        sizeof(async_methods_probe)
    );
}
