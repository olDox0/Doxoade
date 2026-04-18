import os
import tarfile
import click
import zstandard as zstd
import sys
import time
import threading
from doxoade.tools.doxcolors import colors

def get_asset(filename):
    p = os.path.abspath(__file__)
    for _ in range(4):
        p = os.path.dirname(p)
    return os.path.join(p, 'assets', filename)

class NexusTranscodeUI(threading.Thread):
    def __init__(self, total_size, frames):
        super().__init__(daemon=True)
        self.total_size = total_size
        self.frames = frames
        self.current_bytes = 0
        self.running = True
        self.canvas_height = max(len(f.split('\n')) for f in frames) if frames else 0
        # ProgressBar (1) + Respiro (1) + Animation (N)
        self.total_lines = self.canvas_height + 2
        self.up_cmd = f"\x1b[{self.total_lines}A"

    def run(self):
        frame_idx = 0
        sys.stdout.write("\x1b[?25l") # Esconde cursor
        sys.stdout.write("\n" * (self.total_lines + 1)) # Reserva espaço
        
        while self.running:
            t_start = time.perf_counter()
            
            # 1. Dados da Barra
            perc = min(100, int((self.current_bytes / self.total_size) * 100))
            filled = int((45 * self.current_bytes) // self.total_size)
            bar_str = "█" * filled + "░" * (45 - filled)
            color = colors.Fore.SUCCESS if perc == 100 else colors.Fore.PRIMARY
            
            # 2. Construção do Buffer Atômico
            ui = []
            ui.append(self.up_cmd)
            ui.append(f"\r\x1b[K Transcoding: {color}[{bar_str}] {perc}%{colors.Style.RESET_ALL}\n")
            ui.append(f"\x1b[K\n") # Linha de respiro limpa
            
            if self.frames:
                ui.append(self.frames[frame_idx] + "\n")
                frame_idx = (frame_idx + 1) % len(self.frames)

            sys.stdout.write("".join(ui))
            sys.stdout.flush()
            time.sleep(max(0, 0.033 - (time.perf_counter() - t_start)))

        self._cleanup()

    def _cleanup(self):
        """Apaga a animação e deixa apenas a barra de 100%."""
        # Volta ao topo do bloco
        sys.stdout.write(self.up_cmd)
        # 1. Mantém a barra de 100% (Re-imprime ela)
        bar_final = "█" * 45
        sys.stdout.write(f"\r\x1b[K Transcoding: {colors.Fore.SUCCESS}[{bar_final}] 100%{colors.Style.RESET_ALL}\n")
        # 2. Limpa o resto (Respiro + Animação)
        for _ in range(self.canvas_height + 1):
            sys.stdout.write("\x1b[2K\n") # Limpa a linha e desce
        # 3. Posiciona o cursor logo abaixo da barra para o próximo log
        sys.stdout.write(f"\x1b[{self.canvas_height + 1}A")
        sys.stdout.write("\x1b[?25h") # Mostra cursor
        sys.stdout.flush()

def uncompress_zst_to_targz(input_path, output_path):
    anim_path = get_asset('uncompress_loading.nxa')
    total_size = os.path.getsize(input_path)
    frames = colors.UI.load_animation(anim_path) if os.path.exists(anim_path) else []

    ui = NexusTranscodeUI(total_size, frames)
    ui.start()

    try:
        dctx = zstd.ZstdDecompressor()
        with open(input_path, 'rb') as f_raw_in, \
             tarfile.open(output_path, "w:gz", compresslevel=1) as tar_out:
            
            with dctx.stream_reader(f_raw_in) as reader:
                with tarfile.open(fileobj=reader, mode='r|') as tar_in:
                    for member in tar_in:
                        # --- Processamento ---
                        orig = member.name
                        if orig.startswith('root.x86_64/'):
                            member.name = orig.replace('root.x86_64/', '', 1)
                        elif orig == 'root.x86_64': continue
                        if member.name in ["", ".", "./"]: continue

                        if member.isfile():
                            f_mem = tar_in.extractfile(member)
                            if f_mem: tar_out.addfile(member, f_mem)
                        else:
                            tar_out.addfile(member)
                        
                        ui.current_bytes = f_raw_in.tell()

        ui.current_bytes = total_size # Garante 100% no fim
        return True
    except Exception as e:
        sys.stdout.write(f"\n{colors.Fore.ERROR}[FATAL] {e}\n")
        return False
    finally:
        ui.running = False
        ui.join() # Aguarda a limpeza da thread terminar

def _run_transcode_nexus(input_path, output_path, total_size, frames):
    try:
        dctx = zstd.ZstdDecompressor()
        frame_idx = 0
        num_frames = len(frames)
        canvas_height = max(len(f.split('\n')) for f in frames)
        
        # O pulo do gato: Subimos o canvas + a linha da barra de progresso
        up_cmd = f"\x1b[{canvas_height + 1}A" 

        sys.stdout.write("\x1b[?25l") # Esconde cursor
        # Abre o espaço para a animação não sobrescrever comandos anteriores
        sys.stdout.write("\n" * (canvas_height + 2))
        sys.stdout.flush()

        last_update_time = 0
        update_interval = 0.05 # 20 FPS (Atualiza a cada 50ms)

        with open(input_path, 'rb') as f_raw_in, \
             tarfile.open(output_path, "w:gz", compresslevel=1) as tar_out: # Nível 1 para velocidade
            
            with dctx.stream_reader(f_raw_in) as reader:
                with tarfile.open(fileobj=reader, mode='r|') as tar_in:
                    
                    for member in tar_in:
                        # --- Lógica de Transcode ---
                        orig = member.name
                        if orig.startswith('root.x86_64/'):
                            member.name = orig.replace('root.x86_64/', '', 1)
                        elif orig == 'root.x86_64': continue
                        if member.name in ["", ".", "./"]: continue

                        if member.isfile():
                            f_mem = tar_in.extractfile(member)
                            if f_mem: tar_out.addfile(member, f_mem)
                        else:
                            tar_out.addfile(member)

                        # --- THROTTLING DA UI (O Segredo da Estabilidade) ---
                        current_time = time.time()
                        if current_time - last_update_time > update_interval:
                            last_update_time = current_time
                            
                            current_bytes = f_raw_in.tell()
                            perc = min(100, int((current_bytes / total_size) * 100))
                            filled = int((40 * current_bytes) // total_size)
                            bar_str = "█" * filled + "░" * (40 - filled)
                            
                            # Renderização Atômica
                            sys.stdout.write(up_cmd)
                            sys.stdout.write(frames[frame_idx] + "\n")
                            # \r + \x1b[K garante que a linha da barra seja limpa antes de escrever
                            sys.stdout.write(f"\r\x1b[K Transcoding: [{bar_str}] {perc}%\n")
                            sys.stdout.flush()
                            
                            frame_idx = (frame_idx + 1) % num_frames
                            
        # Finalização limpa
        sys.stdout.write(f"\r\x1b[K [OK] Transcoding 100% Completo.\n")
        return True
    except Exception as e:
        click.secho(f"\n[ERRO] {e}", fg='red')
        return False
    finally:
        sys.stdout.write("\x1b[?25h") # Devolve o cursor
        sys.stdout.flush()

def _run_transcode(input_path, output_path, total_size, loader=None):
    try:
        dctx = zstd.ZstdDecompressor()
        
        # Modo 'w:gz' para compressão máxima no arquivo final
        with open(input_path, 'rb') as f_raw_in, \
             tarfile.open(output_path, "w:gz", compresslevel=6) as tar_out:
            
            with click.progressbar(length=total_size, label=' Transcoding RootFS') as bar:
                
                # O stream_reader do zstd é o motor de descompressão
                with dctx.stream_reader(f_raw_in) as reader:
                    # 'r|' indica leitura sequencial de stream (essencial para PASC-8.4)
                    with tarfile.open(fileobj=reader, mode='r|') as tar_in:
                        for member in tar_in:
                            # Atualiza a barra baseado na posição do arquivo comprimido
                            bar.update(f_raw_in.tell() - bar.pos)
                            
                            try:
                                # Normalização de Caminhos (Sanitização)
                                name = member.name
                                if name.startswith('root.x86_64/'):
                                    member.name = name.replace('root.x86_64/', '', 1)
                                elif name == 'root.x86_64':
                                    continue
                                
                                if member.name in ["", ".", "./"]: 
                                    continue

                                # PASC-Security: Filtro de segurança para evitar path traversal
                                if ".." in member.name or member.name.startswith("/"):
                                    continue

                                if member.isfile():
                                    f_member = tar_in.extractfile(member)
                                    if f_member:
                                        tar_out.addfile(member, f_member)
                                else:
                                    # Diretórios, links simbólicos e dispositivos
                                    tar_out.addfile(member)
                                    
                            except Exception as e:
                                if loader: loader.print(f"<{colors.Fore.WARNING}>[SKIP] {member.name}: {e}")
                                continue # Ignora arquivos corrompidos e segue o stream
        return True
    except Exception as e:
        if loader: loader.print(f"<{colors.Fore.ERROR}>[FATAL] {e}")
        else: click.secho(f"\n[FATAL] {e}", fg='red')
        return False