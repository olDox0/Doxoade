@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Pre-flight: doctor --check ===
py -3.12 _doctor.py --check
if errorlevel 1 (
    echo.
    echo PRE-FLIGHT FALHOU. Rode: py -3.12 _doctor.py --fix
    echo E sobrescreva manualmente os arquivos indicados.
    exit /b 1
)

echo.
echo === Executando PoCs ===

set PASS=0
set FAIL=0
set FAILED_LIST=

for %%p in (00:00_fizzbuzz 01:01_cycle 02:02_conflict 10:10_ast_to_facts 11:11_ast_function 20:20_unification 21:21_negation_as_failure 30a:30a_if_return_detect) do (
    for /f "tokens=1,2 delims=:" %%a in ("%%p") do (
        set NUM=%%a
        set FOLDER=%%b
        if exist "!FOLDER!\run_!NUM!.bat" (
            echo.
            echo ==== !FOLDER! ====
            call "!FOLDER!\run_!NUM!.bat"
            if errorlevel 1 (
                set /a FAIL+=1
                set FAILED_LIST=!FAILED_LIST! !FOLDER!
            ) else (
                set /a PASS+=1
            )
        ) else (
            echo SKIP: !FOLDER!\run_!NUM!.bat nao existe
        )
    )
)

echo.
echo ================================
echo PASS: !PASS!  ^|  FAIL: !FAIL!
if defined FAILED_LIST echo Failed:!FAILED_LIST!
echo ================================
if !FAIL! gtr 0 exit /b 1
exit /b 0
