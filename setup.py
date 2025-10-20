from setuptools import setup, find_packages

with open('requirements.txt', 'r', encoding='utf-8') as f:
    requirements = f.read().splitlines()
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='doxoade',
    version='41.0', # Versão da Arquitetura Explícita
    author='olDox222',
    description='olDox222 Advanced Development Environment',
    long_description=long_description,
    long_description_content_type='text/markdown',
    
    # A Correção Crucial: Dizemos para encontrar APENAS o pacote 'doxoade' e seus sub-pacotes.
    packages=find_packages(include=['doxoade', 'doxoade.*']),
    
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