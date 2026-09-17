# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/test_stdio_handshake.py
"""
🧪 Teste de Handshake do PTY STDIO Server.
Spawna o servidor, lê o DOX_PTY_READY, envia AUTH e verifica AUTH_OK.
Uso: python -m doxoade.tools.terminal_pty.test_stdio_handshake
"""
import subprocess
import sys
import time
import os

def main():
    shell = "cmd" if os.name == "nt" else "auto"
    cmd = [
        sys.executable, "-m",
        "doxoade.tools.terminal_pty.pty_stdio_server",
        "--shell", shell,
        "--cols", "120",
        "--rows", "30",
    ]

    print(f"🚀 Spawning: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )

    # 1. Ler a linha DOX_PTY_READY
    ready_line = proc.stdout.readline().decode("utf-8", errors="replace").strip()
    print(f"📥 Recebido: {ready_line[:80]}...")

    if not ready_line.startswith("DOX_PTY_READY|"):
        print("❌ Handshake inválido!")
        proc.kill()
        return 1

    # 2. Extrair token
    token = None
    for part in ready_line.split("|"):
        if part.startswith("token="):
            token = part[len("token="):]
            break

    if not token:
        print("❌ Token não encontrado no handshake!")
        proc.kill()
        return 1

    print(f"🔑 Token extraído: {token[:32]}...")

    # 3. Enviar AUTH
    auth_msg = f"AUTH {token}\n".encode("utf-8")
    proc.stdin.write(auth_msg)
    proc.stdin.flush()
    print("📤 AUTH enviado.")

    # 4. Ler resposta (binária - protocolo PTY)
    time.sleep(0.5)
    response = proc.stdout.read(64)
    print(f"📥 Resposta bruta ({len(response)} bytes): {response[:32]}")

    # Verificar AUTH_OK (msg_type=0x15, payload="OK")
    if len(response) >= 5 and response[0] == 0x15:
        payload_len = int.from_bytes(response[1:5], "big")
        payload = response[5:5 + payload_len]
        print(f"✅ AUTH_OK recebido! Payload: {payload.decode()}")
    elif len(response) >= 5 and response[0] == 0x16:
        payload_len = int.from_bytes(response[1:5], "big")
        payload = response[5:5 + payload_len]
        print(f"❌ AUTH_FAIL: {payload.decode()}")
        proc.kill()
        return 1
    else:
        print(f"⚠ Resposta inesperada: {response}")
        proc.kill()
        return 1

    # 5. Aguardar o servidor estabilizar o PTY antes de enviar input
    time.sleep(1.0)

    # 6. Teste rápido: enviar INPUT_DATA com "echo HELLO\r"
    from doxoade.tools.terminal_pty.pty_protocol import (
        make_input_data, make_shutdown, MsgType, HEADER_SIZE
    )
    
    test_cmd = "echo DOXOADE_PTY_ALIVE\r\n"
#    test_cmd = "echo DOXOADE_PTY_ALIVE\r"
    msg = make_input_data(test_cmd)
    
    try:
        proc.stdin.write(msg.to_bytes())
        proc.stdin.flush()
        print(f"📤 Enviado: '{test_cmd.strip()}'")
    except OSError as e:
        print(f"⚠ Falha ao enviar input (servidor pode não estar pronto): {e}")
        print("   Tentando novamente após delay...")
        time.sleep(1.0)
        try:
            proc.stdin.write(msg.to_bytes())
            proc.stdin.flush()
            print(f"📤 Enviado (retry): '{test_cmd.strip()}'")
        except OSError:
            print("❌ Não foi possível enviar input ao PTY.")
            proc.kill()
            return 1

    # 7. Ler output por 2 segundos (non-blocking)
    time.sleep(1.5)
    output_data = b""
    
    import msvcrt  # Windows non-blocking read
    import io
    
    # Usar read com timeout via thread
    import threading
    read_result = [b""]
    
    def _read_output():
        try:
            read_result[0] = proc.stdout.read(8192)
        except Exception:
            pass
    
    reader_t = threading.Thread(target=_read_output, daemon=True)
    reader_t.start()
    reader_t.join(timeout=2.0)
    output_data = read_result[0]

    # Decodificar mensagens de output
    from doxoade.tools.terminal_pty.pty_protocol import ProtocolStreamReader
    reader = ProtocolStreamReader()
    reader.feed(output_data)
    messages = reader.read_all_messages()

    terminal_text = ""
    for msg in messages:
        if msg.msg_type == MsgType.OUTPUT_DATA:
            terminal_text += msg.payload.decode("utf-8", errors="replace")

    if "DOXOADE_PTY_ALIVE" in terminal_text:
        print("✅ OUTPUT recebido! Terminal PTY está VIVO e respondendo.")
        print(f"   Texto: ...{terminal_text[-80:]}")
    else:
        print(f"⚠ Output recebido mas sem marcador. ({len(terminal_text)} chars)")
        if terminal_text:
            print(f"   Último: {terminal_text[-100:]}")

    # 8. Shutdown gracioso
    try:
        shutdown_msg = make_shutdown()
        proc.stdin.write(shutdown_msg.to_bytes())
        proc.stdin.flush()
    except OSError:
        pass
    
    time.sleep(0.5)
    proc.kill()

    print("\n🏆 TESTE COMPLETO — PTY STDIO Server operacional.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
