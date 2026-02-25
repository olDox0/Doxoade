# doxoade/probes/web_probe.py
"""
Capsula de analise do commands/webcheck.py.
varedura da composição web, audição visual, overload,
Tailwind e chart.js
"""
import os
import re
try:
    import requests
except ImportError:
    requests = None 
class WebAuditProbe:
    def __init__(self, project_path):
        self.path = project_path
        self.dox_palette = ['#26bc5f', '#FF6700', '#E8AA00', '#C81576', '#006CFF', '#EDF1F5', '#19171a', '#4C4552']
    def audit_visuals(self):
        """Valida se as cores hexadecimais batem com a paleta Dox."""
        findings = []
        hex_pattern = r'#(?:[0-9a-fA-F]{3}){1,2}\b'
        for root, _, files in os.walk(self.path):
            for f in files:
                if f.endswith(('.html', '.css', '.py')):
                    with open(os.path.join(root, f), 'r', errors='ignore') as file:
                        content = file.read()
                        found_colors = re.findall(hex_pattern, content)
                        for color in found_colors:
                            if color.lower() not in [c.lower() for c in self.dox_palette]:
                                findings.append({'type': 'warning', 'msg': f"Visual: Cor fora do padrão: {color}", 'file': f})
        return findings
    def check_cdn_health(self):
        """Verifica CDNs com Importação Tardia (Hybrid Venv Strategy)."""
        try:
            import requests # Import local para não quebrar o CLI
        except ImportError:
            return [{'type': 'warning', 'msg': "Sonda CDN desativada: 'requests' não encontrado no ambiente."}]
        
        findings = []
        urls = ["https://cdn.tailwindcss.com", "https://cdn.jsdelivr.net/npm/chart.js"]
        for url in urls:
            try:
                res = requests.head(url, timeout=3)
                if res.status_code != 200:
                    findings.append({'type': 'error', 'msg': f"Asset Health: CDN instável {url}"})
            except Exception:
                findings.append({'type': 'error', 'msg': f"Asset Health: Timeout em {url}"})
        return findings
    def audit_payloads(self):
        """Monitora o peso do projeto (MPoT-16)."""
        findings = []
        for root, _, files in os.walk(self.path):
            for f in files:
                if f.endswith(('.db', '.git', 'venv')): continue
                f_path = os.path.join(root, f)
                size_mb = os.path.getsize(f_path) / (1024 * 1024)
                if size_mb > 2:
                    findings.append({'type': 'error', 'msg': f"Payload Alerta: {f} ({size_mb:.2f}MB)", 'file': f})
        return findings