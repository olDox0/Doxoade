@echo off
set TARGET_PATH=%1
if "%TARGET_PATH%"=="" (
    echo ERRO: Especifique o caminho do arquivo C.
    exit /b 1
)

:: Converte caminhos para o padrão Windows absoluto
set ABS_TARGET=%~f1
set BASE_NAME=%~n1

echo ---------------------------------------------------------
echo 🔮 [SOTÉRIA FORGE] Metalurgia: %BASE_NAME%
echo ---------------------------------------------------------

:: 1. Vacinação (Garante UTF-8 e caminhos limpos)
python -c "from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe; s=SoteriaScribe(); p=r'%ABS_TARGET%'; content=open(p, 'r', encoding='utf-8').read(); open(p.replace('.c', '_vacinado.c'), 'w', encoding='utf-8').write(s.instrument_code(content, p))"

:: 2. Compilação Modular
gcc -O0 "%ABS_TARGET:.c=_vacinado.c%" doxoade\tools\vulcan\diagnostic\soteria\src\soteria_trace.c doxoade\tools\vulcan\diagnostic\soteria\src\soteria_mem.c doxoade\tools\vulcan\diagnostic\soteria\src\soteria_core.c -I doxoade\tools\vulcan\diagnostic\soteria\include -ldbghelp -lpsapi -o "%~dp1%BASE_NAME%.exe"

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Falha na Metalurgia.
    exit /b 1
)
echo ✅ %BASE_NAME%.exe pronto.