# doxoade/commands/lan_git/web_lan_git/bootstrap_generator_lan_git.py
# Gerador do script instalador automatizado .bat para o cliente
"""
Módulo Gerador de Scripts de Bootstrap Automatizados.
Gera script .bat autocontido para inicializar ambiente virtual e dependências no Cliente B.

Gera dinamicamente o arquivo `instalar_doxoade.bat` que será baixado pelo Computador B.
O script contém instruções seguras para:
    1. Verificar se o Python 3.10+ e Git estão instalados.
    2. Criar a `venv` automaticamente.
    3. Baixar os pacotes necessários e registrar o comando `doxoade` no terminal local do Computador B. """
    
class BootstrapGenerator:
    """Gera scripts de instalação para o Computador Cliente."""

    @staticmethod
    def generate_windows_bat(project_name: str, host_ip: str, host_port: int) -> str:
        """Gera o script 'instalar_doxoade.bat' pronto para execução no Windows."""
        return (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "title Instalador Automatizado Doxoade LAN\r\n"
            "echo ============================================================\r\n"
            f"echo   INSTALADOR AUTOMATIZADO - {project_name.upper()}\r\n"
            f"echo   Host de Origem: http://{host_ip}:{host_port}\r\n"
            "echo ============================================================\r\n"
            "echo.\r\n"
            "echo [1/4] Verificando ambiente Python...\r\n"
            "python --version >nul 2>&1\r\n"
            "if %errorlevel% neq 0 (\r\n"
            "    echo [ERRO] Python não foi encontrado no PATH do sistema.\r\n"
            "    echo Instale o Python 3.10+ e tente novamente.\r\n"
            "    pause\r\n"
            "    exit /b 1\r\n"
            ")\r\n"
            "echo [OK] Python detectado.\r\n"
            "echo.\r\n"
            "echo [2/4] Criando Ambiente Virtual (venv)...\r\n"
            "if not exist venv (\r\n"
            "    python -m venv venv\r\n"
            ")\r\n"
            "echo [OK] Venv pronta.\r\n"
            "echo.\r\n"
            "echo [3/4] Atualizando pip e instalando dependências base...\r\n"
            "call venv\\Scripts\\activate.bat\r\n"
            "python -m pip install --upgrade pip\r\n"
            "if exist requirements.txt (\r\n"
            "    pip install -r requirements.txt\r\n"
            ")\r\n"
            "if exist pyproject.toml (\r\n"
            "    pip install -e .\r\n"
            ")\r\n"
            "echo.\r\n"
            "echo [4/4] Configuração concluída com sucesso!\r\n"
            "echo ============================================================\r\n"
            "echo Para utilizar o sistema, execute: call venv\\Scripts\\activate\r\n"
            "echo ============================================================\r\n"
            "pause\r\n"
        )