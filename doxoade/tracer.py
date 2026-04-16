# doxoade/doxoade/tracer.py
import json
import time
import runpy
import sys
_original_on_press = None

def _traced_on_press(self, *args):
    """Nossa versão substituída do on_press."""
    widget_id = self.id if hasattr(self, 'id') and self.id else self.text
    trace_event = {'ts': time.time(), 'stream': 'gui_event', 'event_type': 'on_press', 'widget_id': widget_id}
    print(json.dumps(trace_event))
    if _original_on_press:
        return _original_on_press(self, *args)

def instrument_kivy():
    """Aplica o monkey-patching na biblioteca Kivy."""
    global _original_on_press
    try:
        from kivy.uix.button import Button
        _original_on_press = Button.on_press
        Button.on_press = _traced_on_press
        print(json.dumps({'ts': time.time(), 'stream': 'tracer', 'data': 'Instrumentação Kivy aplicada com sucesso.'}))
    except ImportError:
        pass
    except Exception:
        print(json.dumps({'ts': time.time(), 'stream': 'tracer', 'data': 'Falha ao aplicar instrumentação Kivy.'}))
if __name__ == '__main__':
    sys.argv.pop(0)
    instrument_kivy()
    script_to_run = sys.argv[0]
    runpy.run_path(script_to_run, run_name='__main__')