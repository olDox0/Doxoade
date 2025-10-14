#atualizado em 2025/10/02-Versão 27.0. Módulo de instrumentação para monkey-patching.
import json
import time
import runpy
import sys

# Armazena a função original para não entrarmos em um loop infinito
_original_on_press = None

def _traced_on_press(self, *args):
    """Nossa versão substituída do on_press."""
    # Tenta obter um id ou, como fallback, o texto do botão
    widget_id = self.id if hasattr(self, 'id') and self.id else self.text
    
    # Imprime um JSON formatado para o stdout, que o doxoade run irá capturar
    trace_event = {
        'ts': time.time(),
        'stream': 'gui_event',
        'event_type': 'on_press',
        'widget_id': widget_id
    }
    print(json.dumps(trace_event))
    
    # Chama a função on_press original que salvamos
    if _original_on_press:
        return _original_on_press(self, *args)

def instrument_kivy():
    """Aplica o monkey-patching na biblioteca Kivy."""
    global _original_on_press
    try:
        from kivy.uix.button import Button
        # Salva a função original e a substitui pela nossa
        _original_on_press = Button.on_press
        Button.on_press = _traced_on_press
        print(json.dumps({'ts': time.time(), 'stream': 'tracer', 'data': 'Instrumentação Kivy aplicada com sucesso.'}))
    except ImportError:
        # Kivy não está instalado, não fazemos nada
        pass
    except Exception:
        # Falha no patching, registramos o erro
        print(json.dumps({'ts': time.time(), 'stream': 'tracer', 'data': 'Falha ao aplicar instrumentação Kivy.'}))

if __name__ == '__main__':
    # O tracer é o novo ponto de entrada
    
    # Remove o nome do tracer dos argumentos para que o script alvo não o veja
    sys.argv.pop(0)
    
    # Aplica a instrumentação antes de qualquer coisa
    instrument_kivy()
    
    # O primeiro argumento restante é o script que o usuário realmente quer rodar
    script_to_run = sys.argv[0]
    
    # Usa runpy para executar o script alvo, que agora rodará em um ambiente "patchado"
    runpy.run_path(script_to_run, run_name='__main__')