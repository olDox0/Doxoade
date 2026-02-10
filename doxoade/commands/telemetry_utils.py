# -*- coding: utf-8 -*-
"""
Telemetry Utils v3.6 - Córtex Analítico de Recursos.
Focado em precisão de I/O e análise de vazão.
"""
import json
# [DOX-UNUSED] import os

def parse_json_safe(data):
    if not data: return {}
    try: return json.loads(data)
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: parse_json_safe\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return {}

def format_bytes(size_mb):
    """Converte MB para a unidade mais legível (PASC-6.4)."""
    bytes_val = size_mb * 1024 * 1024
    if bytes_val < 1024: return f"{bytes_val:.0f} B"
    if bytes_val < 1024 * 1024: return f"{bytes_val/1024:.1f} KB"
    return f"{size_mb:.1f} MB"

def get_resource_status(cpu, ram, io_total):
    status = {"cpu": "Ocioso", "ram": "Leve", "io": "Baixo"}
    if cpu > 80: status["cpu"] = "Crítico"
    elif cpu > 50: status["cpu"] = "Alto"
    if ram > 400: status["ram"] = "Pesado"
    elif ram > 150: status["ram"] = "Moderado"
    if io_total > 50: status["io"] = "Intenso"
    elif io_total > 1: status["io"] = "Ativo" # Detecta I/O a partir de 1MB total
    elif io_total > 0.01: status["io"] = "Mínimo" # Detecta I/O de KBs
    return status
    
def aggregate_command_stats(rows):
    stats = {}
    for row in rows:
        cmd = row['command_name'] or "unknown"
        if cmd not in stats:
            stats[cmd] = {'dur': [], 'cpu': [], 'ram': [], 'io_r': [], 'io_w': []}
        
        if row['duration_ms']: stats[cmd]['dur'].append(row['duration_ms'])
        if row['cpu_percent']: stats[cmd]['cpu'].append(row['cpu_percent'])
        if row['peak_memory_mb']: stats[cmd]['ram'].append(row['peak_memory_mb'])
        stats[cmd]['io_r'].append(row['io_read_mb'] or 0)
        stats[cmd]['io_w'].append(row['io_write_mb'] or 0)
    return stats