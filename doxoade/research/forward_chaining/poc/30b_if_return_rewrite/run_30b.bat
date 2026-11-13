@echo off
REM doxoade\research\forward_chaining\poc\30b_if_return_rewrite\run_30b.bat
setlocal
cd /d "%~dp0"

py -3.12 engine_p30b.py
if errorlevel 1 (
    echo FAIL: engine_p30b.py exit %errorlevel%
    exit /b %errorlevel%
)

fc /n /c expected.txt output.txt >nul
if errorlevel 1 (
    echo.
    echo DIFF: expected.txt vs output.txt
    fc /n /c expected.txt output.txt
    exit /b 1
)

echo P30b PASS
exit /b 0
