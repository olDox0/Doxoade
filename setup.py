# doxoade/setup.py
from setuptools import setup, find_packages

setup(
    name="doxoade",
    version="75.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "doxoade = doxoade.__main__:main",
            "dox = doxoade.__main__:main",
        ],
    },
)