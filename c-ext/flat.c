#include <Python.h>

static PyObject* flatten_list_nogil(PyObject* self, PyObject* args) {
    PyObject* original_list;
    if (!PyArg_ParseTuple(args, "O", &original_list)) {
        return NULL;
    }

    if (!PyList_Check(original_list)) {
        PyErr_SetString(PyExc_TypeError, "Expected a list.");
        return NULL;
    }

    Py_ssize_t size = PyList_Size(original_list);

    // Release the GIL
    Py_BEGIN_ALLOW_THREADS

    // Note: All Python C API calls from here on must be protected by GIL
    // but the following logic is just C operations. The GIL is released
    // for this loop to not block other threads.
    
    // Create the flattened list. This call acquires the GIL internally, so we need to
    // re-acquire it temporarily if needed. For this simple case, we'll acquire it just
    // for the Python API calls and release it again.
    PyObject* flattened_list = NULL;
    Py_ssize_t i;
    
    Py_BLOCK_THREADS
    flattened_list = PyList_New(size);
    if (!flattened_list) {
        Py_END_ALLOW_THREADS
        return NULL;
    }
    Py_UNBLOCK_THREADS

    for (i = 0; i < size; ++i) {
        PyObject* item = NULL;
        PyObject* namespace_key = NULL;
        PyObject* namespace_value = NULL;
        PyObject* new_dict = NULL;
        PyObject* final_dict = NULL;

        Py_BLOCK_THREADS
        item = PyList_GetItem(original_list, i);
        if (!PyDict_Check(item)) {
            Py_DECREF(flattened_list);
            Py_END_ALLOW_THREADS
            PyErr_SetString(PyExc_TypeError, "List items must be dictionaries.");
            return NULL;
        }

        namespace_key = PyUnicode_FromString("namespace");
        namespace_value = PyDict_GetItemWithError(item, namespace_key);
        Py_DECREF(namespace_key);

        if (!namespace_value) {
            if (PyErr_Occurred()) {
                Py_DECREF(flattened_list);
                Py_END_ALLOW_THREADS
                return NULL;
            }
            Py_DECREF(flattened_list);
            Py_END_ALLOW_THREADS
            PyErr_SetString(PyExc_KeyError, "'namespace' key not found.");
            return NULL;
        }

        new_dict = PyDict_Copy(item);
        if (!new_dict) {
            Py_DECREF(flattened_list);
            Py_END_ALLOW_THREADS
            return NULL;
        }
        PyDict_DelItemString(new_dict, "namespace");

        final_dict = PyDict_New();
        if (!final_dict) {
            Py_DECREF(new_dict);
            Py_DECREF(flattened_list);
            Py_END_ALLOW_THREADS
            return NULL;
        }
        PyDict_SetItem(final_dict, namespace_value, new_dict);

        PyList_SetItem(flattened_list, i, final_dict);
        Py_DECREF(new_dict);
        
        Py_UNBLOCK_THREADS
    }

    // Re-acquire the GIL
    Py_END_ALLOW_THREADS

    return flattened_list;
}

static PyMethodDef methods_nogil[] = {
    {"flatten", flatten_list_nogil, METH_VARARGS, "Flattens a list of dictionaries without holding the GIL."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef flatten_nogil_module = {
    PyModuleDef_HEAD_INIT,
    "flatten_nogil",
    "A module for flattening a list of dictionaries, releasing the GIL.",
    -1,
    methods_nogil
};

PyMODINIT_FUNC PyInit_flatten_nogil(void) {
    return PyModule_Create(&flatten_nogil_module);
}
