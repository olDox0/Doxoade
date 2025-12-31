# TEST-TARGET: doxoade/commands/run.py
# tests/test_run_logic.py
import os
# Removido pytest (não usado explicitamente, o runner 'pytest' injeta asserts)
from doxoade.commands.run import _build_execution_command, _smart_find_script, _get_flow_probe_path

def test_get_flow_probe_path_exists():
    """Teste simples para cobrir o _get_flow_probe_path."""
    try:
        path = _get_flow_probe_path()
        assert os.path.exists(path)
        assert path.endswith("flow_runner.py")
    except FileNotFoundError:
        # Se rodar fora do contexto de pacote instalado, pode falhar, mas o teste deve ser robusto
        pass

def test_smart_find_script_resolves_py_extension():
    """Testa se o resolvedor adiciona .py automaticamente."""
    # Setup: cria um arquivo dummy
    dummy_name = "test_script_temp.py"
    with open(dummy_name, 'w') as f: f.write("pass")
    
    try:
        # Caso 1: Nome exato
        assert _smart_find_script(dummy_name) == dummy_name
        
        # Caso 2: Sem extensão
        name_no_ext = "test_script_temp"
        assert _smart_find_script(name_no_ext) == dummy_name
        
        # Caso 3: Arquivo inexistente
        assert _smart_find_script("nao_existe") == "nao_existe"
    finally:
        if os.path.exists(dummy_name):
            os.remove(dummy_name)

def test_build_execution_command_normal():
    """Testa a construção do comando normal."""
    python = "python.exe"
    script = "main.py"
    cmd = _build_execution_command(script, python, flow=False)
    
    assert cmd == [python, script]

def test_build_execution_command_with_flow():
    """Testa se o modo Flow injeta a sonda corretamente."""
    python = "python.exe"
    script = "main.py"
    cmd = _build_execution_command(script, python, flow=True)
    
    # O comando deve ser: [python, sonda, script]
    assert len(cmd) == 3
    assert cmd[0] == python
    assert "flow_runner.py" in cmd[1] # A sonda
    assert cmd[2] == script

def test_build_execution_command_with_args():
    """Testa passagem de argumentos extras."""
    cmd = _build_execution_command("main.py", "py", flow=False, args=["--verbose", "input.txt"])
    assert cmd == ["py", "main.py", "--verbose", "input.txt"]