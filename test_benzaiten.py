# test_benzaiten.py
from doxoade.tools.benzaiten_gui.core import BenzaitenWindow
print('Criando janela...')
win = BenzaitenWindow('Teste', 400, 300, mode='web')
print('Janela criada. HWND:', win._hwnd)
print('Modo:', win.mode)
print('DLL carregada?', win._dxlib if hasattr(win, '_dxlib') else 'N/A')
@win.on_ready
def _ready():
    print('✅ on_ready chamado!')
    win.load_html('<h1>Teste</h1>')
print('Chamando run()...')
win.run()
print(' run() retornou! (não deveria)')
