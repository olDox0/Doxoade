@echo off
pushd "%~dp0"

:: 1. Detecta versão do Python (ex: 312) e caminhos
for /f "delims=" %%i in ('python -c "import sys; print(sys.base_prefix)"') do set PY_BASE=%%i
for /f "delims=" %%i in ('python -c "import sys; print(f'python{sys.version_info.major}{sys.version_info.minor}')"') do set PY_LIB_NAME=%%i

set PY_INCLUDE="%PY_BASE%\include"
set PY_LIBS="%PY_BASE%\libs"
set GCC_PATH=%CD%\..\..\..\..\thirdparty\w64devkit\bin\gcc.exe

if not exist "%GCC_PATH%" (
    echo [ERRO] GCC nao encontrado em %GCC_PATH%
    pause
    exit /b
)

echo [VULCAN:BUILD] Usando Python: %PY_LIB_NAME%
echo [VULCAN:BUILD] Forjando motor ASM...
"%GCC_PATH%" -c fast_search.s -o fast_search.o
if %ERRORLEVEL% NEQ 0 goto error

echo [VULCAN:BUILD] Fundindo API Python...
:: Mudamos -lpython3 para -l%PY_LIB_NAME% para resolver o erro de Linker
"%GCC_PATH%" -shared -O3 -msse2 accelerator.c fast_search.o -o vulcan_accelerator.pyd -I %PY_INCLUDE% -L %PY_LIBS% -l%PY_LIB_NAME%
if %ERRORLEVEL% NEQ 0 goto error

echo.
if exist "..\vulcan_accelerator.pyd" del "..\vulcan_accelerator.pyd"
move /Y vulcan_accelerator.pyd ..\
echo [OK] vulcan_accelerator.pyd gerado com sucesso em tools/vulcan/

goto end

:error
echo.
echo [ERRO] Falha na fundicao.
pause

:end
if exist fast_search.o del fast_search.o
popd