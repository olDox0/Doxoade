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
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)