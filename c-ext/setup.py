from setuptools import setup, Extension

# For the GIL version
flatten_module = Extension(
    'flatten',
    sources=['flatten.c']
)

# For the no-GIL version
flatten_nogil_module = Extension(
    'flatten_nogil',
    sources=['flatten_nogil.c']
)

setup(
    name='PythonFlattener',
    version='1.0',
    description='A C extension for flattening lists of dictionaries.',
    ext_modules=[
        flatten_module,
        flatten_nogil_module
    ]
)
