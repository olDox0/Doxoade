@echo off
REM doxoade\research\forward_chaining\poc\\21_negation_as_failure\\run_21.bat
setlocal
cd /d "%~dp0"

py -3.12 engine_p21.py
if errorlevel 1 (
    echo FAIL: run.py exit %errorlevel%
    exit /b %errorlevel%
)

fc /n /c expected.txt output.txt >nul
if errorlevel 1 (
    echo.
    echo DIFF: expected.txt vs output.txt
    fc /n /c expected.txt output.txt
    exit /b 1
)

echo P21 PASS
exit /b 0
