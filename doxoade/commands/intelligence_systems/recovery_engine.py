# doxoade/doxoade/commands/intelligence_systems/recovery_engine.py
import os
import re
import shutil
from datetime import datetime
# [DOX-UNUSED] from pathlib import Path

def run_recovery_mission(project_dir: str, output_dir: str, limit_date: str = None, limit_time: str = None):
    """Resgate Lazarus v3.0: Varredura Total e Aproximação Máxima."""
    
    project_path = os.path.abspath(project_dir)
    
    # 1. Mapeia o inventário (nomes dos arquivos que queremos resgatar)
    project_files = set()
    for root, dirs, files in os.walk(project_path):
        if any(x in root for x in ['.git', 'venv', 'recovery_zone', '__pycache__']):
            dirs[:] = []
            continue
        for f in files:
            project_files.add(f.lower())

    # 2. Prepara a Janela de Tempo
    if limit_date:
        try:
            parts = re.split(r'[.\-]', limit_date)
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            hh, mm = (int(limit_time[:2]), int(limit_time[2:])) if limit_time else (23, 59)
            target_limit = datetime(y, m, d, hh, mm, 0)
        except Exception:
            return (False, 'Formato inválido. Use -d YYYY.MM.DD -t HHMM')
    else:
        target_limit = datetime(2026, 2, 20, 0, 0, 0)

    # 3. Define onde procurar (Recursividade Total)
    search_locations = [project_path] # Procura dentro do projeto inteiro (recursivo)
    
    if os.name == 'nt':
        # Locais padrão do Notepad++ no Windows
        search_locations.append(os.path.expandvars(r'%APPDATA%\Notepad++\backup'))
        # Tenta também a pasta de instalação caso o usuário use backup simples
        npp_custom = r'C:\Program Files\Notepad++\backup'
        if os.path.exists(npp_custom): search_locations.append(npp_custom)

    latest_matches = {}
    
    # Patterns de Backup (Verboso e Simples)
    # 1. file.py.2026-04-29_143935.bak
    # 2. file.py@2026-04-29_143935
    # 3. file.py.bak
    re_timestamp = re.compile(r'(.+?)(?:\.|@)(\d{4}-\d{2}-\d{2}_\d{6})(?:\.bak)?$')

    # 4. A Grande Busca
    for loc in search_locations:
        if not os.path.exists(loc): continue
        
        for root, _, files in os.walk(loc):
            # Evita entrar na zona de recuperação para não criar loops de arquivos
            if 'recovery_zone' in root: continue

            for f in files:
                f_lower = f.lower()
                file_path = os.path.join(root, f)
                file_dt = None
                orig_name = None

                # Tenta extrair data do nome do arquivo (Pattern 1 e 2)
                match = re_timestamp.match(f)
                if match:
                    orig_name = match.group(1)
                    try:
                        file_dt = datetime.strptime(match.group(2), '%Y-%m-%d_%H%M%S')
                    except ValueError: pass
                
                # Se não tem data no nome, mas termina em .bak ou é arquivo do projeto
                if not file_dt and f_lower.endswith('.bak'):
                    orig_name = f[:-4] # remove .bak
                    file_dt = datetime.fromtimestamp(os.path.getmtime(file_path))

                # Validação Final:
                if orig_name:
                    clean_name = os.path.basename(orig_name).lower()
                    
                    # O arquivo pertence ao projeto?
                    if clean_name in project_files:
                        # Está dentro da janela de tempo?
                        if file_dt <= target_limit:
                            # É a versão mais recente para este arquivo até agora?
                            if clean_name not in latest_matches or file_dt > latest_matches[clean_name][0]:
                                latest_matches[clean_name] = (file_dt, file_path)

    if not latest_matches:
        return (False, f'Nenhum backup de arquivos do projeto encontrado antes de {target_limit.strftime("%d/%m %H:%M")}.')

    # 5. Materialização do Resgate
    os.makedirs(output_dir, exist_ok=True)
    for name_lower, (dt, path) in latest_matches.items():
        # Recupera o nome original com o Case correto do inventário (opcional, mas elegante)
        dest = os.path.join(output_dir, os.path.basename(path).split('.')[0] + os.path.splitext(os.path.basename(path).replace('.bak',''))[1])
        # Simplificando: usa o nome base do backup sem o timestamp
        # Se o backup era doxarchives_cli.py.timestamp.bak -> vira doxarchives_cli.py
        
        # Encontra o nome original no inventário para preservar Case
        final_name = "recovered_file"
        for p_file in project_files:
            if p_file == name_lower:
                final_name = p_file
                break
        
        shutil.copy2(path, os.path.join(output_dir, final_name))

    return (True, f'Sucesso! {len(latest_matches)} arquivos resgatados em "{output_dir}".')