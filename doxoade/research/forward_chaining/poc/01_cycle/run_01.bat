@echo off
REM doxoade\research\forward_chaining\poc\10_ast_to_facts\run.bat
setlocal
cd /d "%~dp0"

py -3.12 engine_p01.py
if errorlevel 1 (
    echo FAIL: engine_p01.py exit %errorlevel%
    exit /b %errorlevel%
)

fc /n /c expected.txt output.txt >nul
if errorlevel 1 (
    echo.
    echo DIFF: expected.txt vs output.txt
    fc /n /c expected.txt output.txt
    exit /b 1
)

echo P01 PASS
exit /b 0
