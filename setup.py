from setuptools import setup, find_packages

# Lê o conteúdo do requirements.txt para as dependências
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='doxoade',
    version='1.0.0',
    author='olDox222',
    description='olDox222 Advanced Development Environment - Ferramenta de análise de projetos Python',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'doxoade = doxoade.doxoade:cli',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)