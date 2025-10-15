from setuptools import setup, find_packages

# Lê o conteúdo do requirements.txt de forma segura
with open('requirements.txt', 'r', encoding='utf-8') as f:
    requirements = f.read().splitlines()

# Lê o conteúdo do README.md de forma segura
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='doxoade',
    version='1.0.0',
    author='olDox222',
    description='olDox222 Advanced Development Environment',
    long_description=long_description,  # Usa a variável que lemos com segurança
    long_description_content_type='text/markdown',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'doxoade = doxoade.doxoade:cli',
            'doxoade-check = doxoade.doxoade:check',
            'doxoade-save = doxoade.doxoade:save',
            'doxoade-init = doxoade.doxoade:init',
            'doxoade-auto = doxoade.doxoade:auto',
            'doxoade-run = doxoade.doxoade:run',
            'doxoade-clean = doxoade.doxoade:clean',
            'doxoade-log = doxoade.doxoade:log',
            'doxoade-tutorial = doxoade.doxoade:tutorial',
            'doxoade-git-clean = doxoade.doxoade:git_clean',
            'doxoade-release = doxoade.doxoade:release',
            'doxoade-sync = doxoade.doxoade:sync',
            'doxoade-kvcheck = doxoade.doxoade:kvcheck',
            'doxoade-encoding = doxoade.doxoade:encoding',
            'doxoade-show-trace = doxoade.doxoade:show_trace',
            'doxoade-optimize = doxoade.doxoade:optimize',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)