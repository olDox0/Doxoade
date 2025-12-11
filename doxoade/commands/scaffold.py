import click
import os
from colorama import Fore

@click.command('scaffold')
@click.argument('component_path')
@click.option('--type', type=click.Choice(['page', 'component']), default='page', help="Tipo de estrutura.")
def scaffold(component_path, type):
    """
    Gera estrutura boilerplate para NiceGUI (Doxrooms).
    Uso: doxoade scaffold LoginScreen (cria em src/ui/login_screen.py)
         doxoade scaffold src/components/MyWidget (cria onde especificado)
    """
    # Normaliza barras para o SO atual
    component_path = os.path.normpath(component_path)
    
    # Extrai o nome do componente (última parte do caminho)
    component_name = os.path.basename(component_path)
    
    # Define o diretório base
    if os.path.dirname(component_path):
        # Se o usuário passou um caminho (ex: src/ui/Tela), usa ele
        base_dir = os.path.dirname(component_path)
    else:
        # Se passou apenas o nome, usa o padrão
        base_dir = "src/ui" if type == 'page' else "src/components"

    # Prepara nomes
    name_snake = component_name.lower().replace(' ', '_')
    class_name = component_name.replace('_', ' ').title().replace(' ', '')
    
    # Cria o diretório se não existir
    os.makedirs(base_dir, exist_ok=True)
    
    file_path = os.path.join(base_dir, f"{name_snake}.py")
    
    if os.path.exists(file_path):
        click.echo(Fore.RED + f"[ERRO] Arquivo '{file_path}' já existe.")
        return

    content = f'''from nicegui import ui

class {class_name}:
    """
    Componente: {class_name}
    Gerado por Doxoade Scaffold
    """
    def __init__(self):
        self.build()

    def build(self):
        with ui.card().classes('w-full p-4'):
            ui.label('{class_name}').classes('text-xl font-bold')
            # TODO: Implementar lógica visual aqui
            ui.button('Ação', on_click=self.on_action)

    def on_action(self):
        ui.notify('{class_name} Action Triggered!')

def create():
    return {class_name}()
'''
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        click.echo(Fore.GREEN + f"[OK] Scaffold criado em: {file_path}")
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO CRÍTICO] Falha ao escrever arquivo: {e}")