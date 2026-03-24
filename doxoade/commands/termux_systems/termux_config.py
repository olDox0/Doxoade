#!/usr/bin/env python3
# doxoade\commands\termux_systems\termux_config.py
import os

HOME = os.path.expanduser("~")
# Arquivo de registro para garantir que o script rode apenas uma vez
FLAG_FILE = os.path.join(HOME, ".doxoade_termux_configured")

def ensure_file(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8"):
            pass

def main():
    # Verifica se já foi executado anteriormente
    if os.path.exists(FLAG_FILE):
        print("✔️  O ambiente Termux já foi configurado anteriormente. Ignorando...")
        return

    print("⚙️  Iniciando a configuração inteligente do Termux...")

    # ==========================================
    # 1. Configurando o NANO
    # ==========================================
    nanorc_path = os.path.join(HOME, ".nanorc")
    ensure_file(nanorc_path)

    with open(nanorc_path, "r+", encoding="utf-8") as f:
        content = f.read()
        if "set linenumbers" not in content:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("set linenumbers\n")
            print("✔️  Números de linha ativados no Nano.")
        else:
            print("✔️  Nano já estava configurado.")

    # ==========================================
    # 2. Configurando Cores do TERMUX
    # ==========================================
    termux_dir = os.path.join(HOME, ".termux")
    colors_path = os.path.join(termux_dir, "colors.properties")

    os.makedirs(termux_dir, exist_ok=True)
    ensure_file(colors_path)

    with open(colors_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Remove qualquer linha antiga de background e adiciona a nova
    lines = [line for line in lines if not line.startswith("background=")]
    lines.append("background=#197b3f\n")

    with open(colors_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Aplica as cores imediatamente via Python
    #from subprocess import run as subprorun
    import shutil
    from doxoade.tools.exec_safe import run_safe

    cmd = shutil.which("termux-reload-settings")

    if cmd:
        run_safe("termux-reload-settings") #subprorun([cmd], check=True)
    else:
        print("⚠️ termux-reload-settings não encontrado.")

    # ==========================================
    # 3. Configurando o MICRO (Cores e Indentação inteligente)
    # ==========================================
    micro_colors_dir = os.path.join(HOME, ".config/micro/colorschemes")
    micro_settings_dir = os.path.join(HOME, ".config/micro")

    os.makedirs(micro_colors_dir, exist_ok=True)
    os.makedirs(micro_settings_dir, exist_ok=True)

    # Cria o Tema
    theme_path = os.path.join(micro_colors_dir, "meutema.micro")
    with open(theme_path, "w", encoding="utf-8") as f:
        f.write('color-link cursor-line ",#e05a00"\n')

    # Configuração via JSON para não quebrar configurações existentes
    import json
    settings_path = os.path.join(micro_settings_dir, "settings.json")
    settings = {}
    
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            # Se o arquivo existir mas estiver corrompido, começamos do zero
            pass

    # Atualiza apenas os valores necessários
    settings.update({
        "colorscheme": "meutema",
        "cursorline": True,
        "truecolor": True,
        "autoindent": False,
        "smartpaste": False
    })

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

    print("✔️  Micro configurado (Linha do cursor laranja + Correção de colar código).")

    # ==========================================
    # 4. Finalização e Registro
    # ==========================================
    # Cria o arquivo de flag para registrar que a configuração já foi feita
    with open(FLAG_FILE, "w", encoding="utf-8") as f:
        f.write("Configuração executada com sucesso.\n")

    print("🚀 Tudo pronto! Configuração finalizada com sucesso e registrada.")

if __name__ == "__main__":
    main()