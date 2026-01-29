@echo off
set CSC_PATH=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set TARGET_DLL=DoxoadeNPP.dll

echo [PASC-1.3] Compilando DoxoadeNPP Plugin...

%CSC_PATH% /target:library /out:%TARGET_DLL% /reference:System.Web.Extensions.dll Plugin.cs NppInterface.cs

if %errorlevel% neq 0 (
    echo [ERRO] Falha na compilação.
    pause
    exit /b
)

echo [OK] Plugin gerado: %TARGET_DLL%
pause