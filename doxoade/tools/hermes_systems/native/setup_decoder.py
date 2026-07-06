# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/native/setup_decoder.py
"""
Build do Hermes Native Decoder via setuptools.
Usa o compilador correto (MSVC no Windows) automaticamente.
Uso:
cd doxoade/tools/hermes_systems/native
python setup_decoder.py build_ext --inplace
"""
import os
import sysconfig
from setuptools import setup, Extension

# Detecta paths do Python automaticamente (Correção do bug de ordem)
python_include = sysconfig.get_path('include')
python_lib_dir = sysconfig.get_config_var('LIBDIR') or ''

# Define a extensão
hermes_decoder = Extension(
    'hermes_decoder',
    sources=['hermes_decoder.c'],
    include_dirs=[python_include],
    libraries=['lzma'],
    library_dirs=[python_lib_dir] if python_lib_dir else [],
    extra_compile_args=['/O2'] if os.name == 'nt' else ['-O3', '-fPIC'],
)

setup(
    name='hermes_decoder',
    version='1.0.0',
    description='Hermes Native Decoder - C extension for fast HBC3 decoding',
    ext_modules=[hermes_decoder],
)