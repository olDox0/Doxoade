@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: DOXOADE VULCAN BUILD SYSTEM - Performance Engine
:: Padrão Chief-Gold | Compliance: MPoT-10, PASC-6.4
:: ============================================================================

echo.
echo   [96m[VULCAN-FORGE] [0m Iniciando Forja de Binarios Nativa...
echo  ------------------------------------------------------------

:: 1. LOCALIZAÇÃO DO COMPILADOR MSVC (Microsoft Visual C++)
set "MSVC_FOUND=0"
set "VS_PATH_22=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
set "VS_PATH_19=C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
set "VS_BT_22=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

if exist "%VS_PATH_22%" ( set "VC_VARS=%VS_PATH_22%" ) else (
    if exist "%VS_BT_22%" ( set "VC_VARS=%VS_BT_22%" ) else (
        if exist "%VS_PATH_19%" ( set "VC_VARS=%VS_PATH_19%" )
    )
)

if defined VC_VARS (
    echo   [92m[OK] [0m Compilador MSVC detectado.
    call "%VC_VARS%" >nul
    set "MSVC_FOUND=1"
) else (
    echo   [91m[ERRO] [0m MSVC nao encontrado. Instale o 'Build Tools for Visual Studio'.
    exit /b 1
)

:: 2. VERIFICAÇÃO DE AMBIENTE VIRTUAL
if not defined VIRTUAL_ENV (
    echo   [93m[AVISO] [0m VENV nao ativo. Tentando localizar...
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
    ) else (
        echo   [91m[ERRO] [0m Ambiente Python invalido para compilação.
        exit /b 1
    )
)

:: 3. EXECUÇÃO DA FORJA
echo   [94m[INFO] [0m Sincronizando Cython e NumPy...
python -m pip install -q cython numpy

if "%1"=="" (
    echo   [93m[!] [0m Alvo omitido. Compilando extensões core...
    :: Se você tiver um setup.py na raiz para o Vulcan
    python setup.py build_ext --inplace
) else (
    echo   [96m[FORGE] [0m Processando alvo:  [93m%1 [0m
    :: O comando 'vulcan ignite' coloca o setup_tmp.py na foundry
    if exist ".doxoade\vulcan\foundry\setup_tmp.py" (
        python .doxoade\vulcan\foundry\setup_tmp.py build_ext --inplace
    ) else (
        echo   [91m[ERRO] [0m Setup temporario nao encontrado em .doxoade/vulcan/foundry/
        exit /b 1
    )
)

if %errorlevel% neq 0 (
    echo.
    echo   [91m[FALHA] [0m A Forja falhou. Verifique erros de sintaxe no código C.
    exit /b %errorlevel%
)

echo.
echo   [92m[SUCESSO] [0m Binario Vulcano forjado com sucesso.
echo  ------------------------------------------------------------
endlocal