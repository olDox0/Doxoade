# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/doxcolors.py
"""
Doxcolors Nexus Edition – High-Performance CLI UI Engine
Versão: 2.0 (Nexus UI)
"""
import os
import sys
import builtins
import time
import random
import string
import math
import threading

# --- CORE ENGINE ---

def _ansi_enabled():
    if os.name != 'nt':
        return sys.stdout.isatty()
    return sys.stdout.isatty() or 'ANSICON' in os.environ or 'WT_SESSION' in os.environ or (os.environ.get('TERM_PROGRAM') == 'vscode')

ANSI_ENABLED = _ansi_enabled()

if os.name == 'nt' and ANSI_ENABLED:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 4)
    except Exception:
        pass

class AnsiCode(str):
    __slots__ = ()
    def __new__(cls, code: str):
        if not ANSI_ENABLED: return str.__new__(cls, '')
        return str.__new__(cls, f'\x1b[{code}m')

class Back: # Adicionado para corrigir o NameError
    BLACK = AnsiCode('40');  RED = AnsiCode('41');   GREEN = AnsiCode('42')
    YELLOW = AnsiCode('43'); BLUE = AnsiCode('44');  MAGENTA = AnsiCode('45')
    CYAN = AnsiCode('46');   WHITE = AnsiCode('47'); RESET = AnsiCode('49')

class Fore:
    BLACK = AnsiCode('30');        RED = AnsiCode('31');         GREEN = AnsiCode('32')
    YELLOW = AnsiCode('33');       BLUE = AnsiCode('34');        MAGENTA = AnsiCode('35')
    CYAN = AnsiCode('36');         WHITE = AnsiCode('37');       RESET = AnsiCode('0')
    LIGHTBLUE_EX = AnsiCode('94'); LIGHTCYAN_EX = AnsiCode('96')
    # Nexus Semantic Colors

    PRIMARY  = AnsiCode('38;2;0;108;255')   # Azul Nexus
    SUCCESS  = AnsiCode('38;2;38;188;95')   # Verde Estável
    ERROR    = AnsiCode('38;2;255;103;0')   # Laranja Erro
    WARNING  = AnsiCode('38;2;232;170;0')   # Amarelo Alerta
    STABLE   = AnsiCode('38;2;176;176;176') # Cinza (Código antigo/estável)
    VOLATILE = AnsiCode('38;2;255;0;255')   # Magenta (Código sendo alterado)

class Style:
    DIM = AnsiCode('2'); NORMAL = AnsiCode('22'); BRIGHT = AnsiCode('1')
    RESET_ALL = AnsiCode('0'); BLINK = AnsiCode('5'); ITALIC = AnsiCode('3')
    HIDDEN = AnsiCode('?25l'); SHOW = AnsiCode('?25h') # Cursor control

# --- UTILS ---

def rgb(r, g, b): return AnsiCode(f'38;2;{r};{g};{b}')
def hex_to_ansi(hex_code: str):
    h = hex_code.lstrip('#')
    return rgb(*(int(h[i:i+2], 16) for i in (0, 2, 4)))

# --- NEXUS UI & ANIMATIONS ---

class NexusUI:
    """Motor de Interface Visual do Doxoade."""
    
    @staticmethod
    def gradient_text(text, start_hex="#006CFF", end_hex="#26BC5F"):
        """Gera um texto com gradiente linear."""
        if not ANSI_ENABLED: return text
        h1, h2 = start_hex.lstrip('#'), end_hex.lstrip('#')
        r1, g1, b1 = (int(h1[i:i+2], 16) for i in (0, 2, 4))
        r2, g2, b2 = (int(h2[i:i+2], 16) for i in (0, 2, 4))
        
        result = ""
        steps = len(text)
        for i, char in enumerate(text):
            r = int(r1 + (r2 - r1) * (i / max(1, steps-1)))
            g = int(g1 + (g2 - g1) * (i / max(1, steps-1)))
            b = int(b1 + (b2 - b1) * (i / max(1, steps-1)))
            result += f"\x1b[38;2;{r};{g};{b}m{char}"
        return result + "\x1b[0m"

    @staticmethod
    def decode_effect(target_text, duration=1.0):
        """Efeito de decodificação 'Matrix' para revelar texto."""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        start_time = time.time()
        while time.time() - start_time < duration:
            current = "".join(random.choice(chars) for _ in range(len(target_text)))
            sys.stdout.write(f"\r{Fore.PRIMARY}{current}{Style.RESET_ALL}")
            sys.stdout.flush()
            time.sleep(0.05)
        sys.stdout.write(f"\r{NexusUI.gradient_text(target_text)}\n")

    @staticmethod
    def pulse(text, hex_color="#FF00FF", speed=1.0):
        """Efeito de pulsar (fade in/out) - Requer terminal com suporte a TrueColor."""
        # Simulado via alternância de brilho se não houver suporte total
        pass 

    @staticmethod
    def play_animation(frames, interval=0.1, loops=2):
        """
        Animação multi-linha ultra-estável por contagem de linhas.
        """
        if not ANSI_ENABLED: return
        
        sys.stdout.write("\x1b[?25l") # Esconde cursor
        
        try:
            for loop in range(loops):
                for frame in frames:
                    # Limpa espaços e divide linhas
                    lines = frame.strip('\n').split('\n')
                    num_lines = len(lines)
                    
                    # Desenha o frame linha por linha
                    for line in lines:
                        # \r volta pro início da linha, \x1b[2K apaga o que tinha antes
                        sys.stdout.write("\r\x1b[2K" + line + "\n")
                    
                    sys.stdout.flush()
                    time.sleep(interval)
                    
                    # SOBE O CURSOR exatamente o número de linhas que imprimimos
                    # para desenhar o próximo frame por cima
                    sys.stdout.write(f"\x1b[{num_lines}A")
            
            # Ao terminar, move o cursor para baixo da animação
            sys.stdout.write(f"\x1b[{num_lines}B\n")
            
        finally:
            sys.stdout.write("\x1b[?25h") # Mostra cursor
            sys.stdout.flush()

    @staticmethod
    def apply_tags(text):
        """
        Traduz tags humanas para códigos ANSI.
        Ex: "<BLUE>Texto" -> "\x1b[34mTexto"
        """
        # Mapeamento automático de Fore, Back e Style
        import re
        
        # Procura por padrões <NOME>
        tags = re.findall(r'<(.*?)>', text)
        
        for tag in tags:
            tag_upper = tag.upper()
            replacement = ""
            
            # 1. Tenta buscar em Fore (Cores de fonte)
            if hasattr(Fore, tag_upper):
                replacement = getattr(Fore, tag_upper)
            # 2. Tenta buscar em Style (Reset, Bold, etc)
            elif hasattr(Style, tag_upper):
                replacement = getattr(Style, tag_upper)
            # 3. Tenta buscar em Back (Fundo)
            elif hasattr(Back, tag_upper):
                replacement = getattr(Back, tag_upper)
            
            # Se encontrou uma correspondência, substitui no texto
            if replacement:
                text = text.replace(f"<{tag}>", replacement)
        
        # Garante que <RESET> seja sempre o padrão caso o usuário esqueça
        return text.replace("<RESET>", Style.RESET_ALL)

    @staticmethod
    def load_animation(file_path, separator="===FRAME==="):
        """Carrega e TRADUZ as tags do arquivo automaticamente."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Aplica a tradução de tags em todo o conteúdo do arquivo
            content = NexusUI.apply_tags(content)
            
            frames = [frame.strip('\n') for frame in content.split(separator) if frame.strip()]
            return frames
        except Exception as e:
            print(f"Erro ao carregar animação: {e}")
            return []

    @staticmethod
    def loader(file_path, interval=0.1):
        """Retorna um objeto AsyncAnimation carregado de um arquivo."""
        frames = NexusUI.load_animation(file_path)
        return AsyncAnimation(frames, interval)



class Spinner:
    """Braille Loading Spinner."""
    frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    def __init__(self, message="Processando"):
        self.message = message
        self.idx = 0

    def step(self):
        frame = self.frames[self.idx % len(self.frames)]
        sys.stdout.write(f"\r{Fore.CYAN}{frame}{Fore.RESET} {self.message}...")
        sys.stdout.flush()
        self.idx += 1

    def finish(self, success=True):
        symbol = f"{Fore.SUCCESS}✔" if success else f"{Fore.ERROR}✘"
        sys.stdout.write(f"\r{symbol}{Fore.RESET} {self.message} Finalizado.\n")

class ProgressBar:
    """Barra de progresso semântica."""
    def __init__(self, total, label="Progresso", width=30):
        self.total = total
        self.label = label
        self.width = width

    def update(self, current):
        perc = min(100, int((current / self.total) * 100))
        filled = int((self.width * current) // self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        color = Fore.SUCCESS if perc == 100 else Fore.PRIMARY
        sys.stdout.write(f"\r{self.label} {color}[{bar}] {perc}%{Fore.RESET}")
        sys.stdout.flush()

class AsyncAnimation:
    def __init__(self, frames, interval=0.1):
        self.frames = frames
        self.interval = interval
        self.running = False
        self._thread = None
        self.lock = threading.Lock()
        self.current_height = 0 # Rastreia a altura real do frame atual

    def _animate(self):
        sys.stdout.write("\x1b[?25l") # Esconde cursor
        try:
            while self.running:
                for frame in self.frames:
                    if not self.running: break
                    
                    with self.lock:
                        # 1. Limpa o que foi desenhado no frame anterior
                        if self.current_height > 0:
                            sys.stdout.write(f"\x1b[{self.current_height}A")
                        
                        # 2. Desenha o novo frame
                        lines = frame.strip('\n').split('\n')
                        for line in lines:
                            sys.stdout.write("\r\x1b[2K" + line + "\n")
                        
                        self.current_height = len(lines)
                        sys.stdout.flush()
                    
                    time.sleep(self.interval)
        finally:
            with self.lock:
                # 3. FAXINA DE SAÍDA: Apaga a animação e deixa o cursor pronto para o próximo texto
                if self.current_height > 0:
                    sys.stdout.write(f"\x1b[{self.current_height}A")
                    for _ in range(self.current_height):
                        sys.stdout.write("\x1b[2K\x1b[B")
                    sys.stdout.write(f"\x1b[{self.current_height}A")
                
                sys.stdout.write("\x1b[?25h") # Mostra cursor
                sys.stdout.flush()

    def print(self, text):
        """Imprime logs coloridos empurrando a animação para baixo."""
        from .doxcolors import colors
        formatted = colors.UI.apply_tags(text)
        
        with self.lock:
            # 1. Se a animação está na tela, sobe e apaga ela temporariamente
            if self.current_height > 0:
                sys.stdout.write(f"\x1b[{self.current_height}A")
                for _ in range(self.current_height):
                    sys.stdout.write("\x1b[2K\x1b[B")
                sys.stdout.write(f"\x1b[{self.current_height}A")
            
            # 2. Imprime o log de verdade
            sys.stdout.write(f"\r{formatted}\n")
            sys.stdout.flush()
            
            # 3. Reseta o height para 0 para que o loop de animação 
            # saiba que deve redesenhar do ponto atual
            self.current_height = 0

    def start(self):
        if not self.frames: return
        self.running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

# --- OVERRIDES ---

_original_print = builtins.print
def safe_print(*args, **kwargs):
    _original_print(*args, **kwargs)
    if ANSI_ENABLED: _original_print('\x1b[0m', end='')
builtins.print = safe_print

# --- EXPORTS ---
class DoxColors:
    Fore = Fore; Back = Back; Style = Style; UI = NexusUI
    rgb = staticmethod(rgb); hex = staticmethod(hex_to_ansi)
colors = DoxColors