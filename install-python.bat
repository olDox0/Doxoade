::install-python.bat
@echo off
chcp 65001 > nul
mode con: cols=100 lines=40	 > nul
mode con: rate=20 delay=0 > nul
color 0f
setlocal enabledelayedexpansion
echo.
echo.
echo              .§#$$$$$$$$$$$$$$$§# .§#$$$$$$$$§ §$$#$$$$$$$§,`=#§$$$$$$$$$$$$$§, 
echo             .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$§ §$$$$$$$$$$$$$$§,`4$$$$$$$$$$$$§, 
echo            .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$§ §$$$$$$$$$$$$$$$$§,`4$$$$$$$$$$$§, 
echo           .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$$§ §$$$$$$$$$$$$$$$$$§           
echo          .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$$$§ §$$$$$$$$$$$$$$$$$$§`§$$$$$$$$$$$$§, 
echo         .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$$$$§ §$$$$$$$$$$$$$$$$$$§;4$$$$$$$$$$$$$§, 
echo        .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$$$$$§ §$$$$$$$$$$$$$$$$$$§.4$$$$$$$$$$$$$$§, 
echo       .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$$$$$$§ §$$$$$$$$$$$$$$$$$§           
echo      .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$$$$$$$§ §$$$$$$$$$$$$$$$$§`.§$$$$$$$$$$$$$$$$$§, 
echo     .§$$$$$$$$$$$$$$$$$§`.$$$$$$$$$$$$$$$$$$$§ §$$$$$$$$$$$$$$§`.§$$$$$$$$$$$$$$$$$$$$§, 
echo    .§$$$$$$$$$$$$$$$$§#`.$$$$$$$$$$$$$$$$$$#§` `§#$$$$$$$$§`.=#§$$$$$$$$$$$$$$$$$$$$$$$§, 
echo.
echo                       olDox22 Advanced Development Environment
echo                       Uma cortesia de Victor A. Alves de Assis
echo.
echo                        [DOXOADE PYTHON INSTALLER FOR WINDOWS]
echo.
echo     Este comando abrira o seu navegador na pagina de download oficial do Python 3.12.4.
echo.
echo     IMPORTANTE: Durante a instalacao, certifique-se de marcar a caixa:
echo.
echo     +-----------------------------+
echo     ^| [X] Add python.exe to PATH  ^|
echo     +-----------------------------+
echo.
echo.
echo     [Pressione qualquer tecla para continuar]
pause >nul
start "" "https://www.python.org/downloads/release/python-3124/"

endlocal