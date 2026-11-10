@echo off
REM doxoade\research\forward_chaining\poc\30a_if_return_detect\run_30a.bat
setlocal
cd /d "%~dp0"

py -3.12 engine_p30a.py
if errorlevel 1 (
    echo FAIL: engine_p30a.py exit %errorlevel%
    exit /b %errorlevel%
)

fc /n /c expected.txt output.txt >nul
if errorlevel 1 (
    echo.
    echo DIFF: expected.txt vs output.txt
    fc /n /c expected.txt output.txt
    exit /b 1
)

echo P30a PASS
exit /b 0
