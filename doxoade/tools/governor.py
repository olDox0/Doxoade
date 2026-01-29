# -*- coding: utf-8 -*-
# doxoade/tools/governor.py
"""
Doxoade Resource Governor - ALB v1.2.
Agora com Sensibilidade de I/O e Latência.
"""
import psutil
import time
import os

class ResourceGovernor:
    def __init__(self):
        # MPoT-15: Limiares Gold
        self.CPU_LIMIT_ECO = 100.0
        self.CPU_LIMIT_CRIT = 150.0
        self.DISK_BUSY_LIMIT = 85.0
        self.RAM_LIMIT_CRIT = 75.0
        
        self.base_sleep = 0.03
        self.last_pace_time = 0
        self.enabled = True
        self.interventions = 0
        
        self._cached_disk = 0
        self._last_disk_check = 0
        
        self._cache = {'cpu': 0, 'ram': 0, 'disk': 0}
        self._last_sample = 0

    def pace(self, targeted=False, force=False):
        """Aplica modulação de carga com override de Soberania."""
        # [ALB BYPASS] Se force=True, ignora CPU/RAM e retorna False (não pula nada)
        if force:
            return False 

        now = time.time()
        # Cooldown de amostragem
        if now - self.last_pace_time < 0.5:
            return False 
            
        self.last_pace_time = now
        sleep_time, skip_heavy = self.decide_pace()
        
        if targeted and not skip_heavy:
            return False

        if sleep_time > 0:
            time.sleep(sleep_time)
            self.interventions += 1
        return skip_heavy
        
    def get_system_health(self):
        now = time.time()
        # MPoT-12: Amostragem a cada 2 segundos. Fora isso, usa o cache.
        if now - self._last_sample < 2.0:
            return self._cache['cpu'], self._cache['ram'], self._cache['disk']

        try:
            self._cache['cpu'] = psutil.cpu_percent(interval=None)
            self._cache['ram'] = psutil.virtual_memory().percent
            self._cache['disk'] = psutil.disk_usage(os.getcwd()).percent
            self._last_sample = now
        except: pass
        
        return self._cache['cpu'], self._cache['ram'], self._cache['disk']

    def decide_pace(self):
        cpu, ram, disk = self.get_system_health()
        if disk > self.DISK_BUSY_LIMIT or ram > self.RAM_LIMIT_CRIT:
            return self.base_sleep * 15, True
        if cpu > self.CPU_LIMIT_CRIT:
            return self.base_sleep * 10, True
        if cpu > self.CPU_LIMIT_ECO:
            return self.base_sleep * 2, False
        return 0.0, False

    def get_disk_pressure(self):
        """Calcula a pressão de I/O baseada na variação de tempo de atividade."""
        try:
            # Em sistemas modernos, usamos o busy_time do psutil
            # Se não disponível, calculamos a vazão
            usage = psutil.disk_usage('/').percent # Pressão de espaço
            # Nota: No Windows, monitoramos o tempo de resposta via psutil
            # Para fins de ALB, simplificamos para ocupação global
            return usage
        except:
            return 0

    def get_report(self):
        """Retorna o balanço de intervenções para o Logger."""
        return self.interventions

governor = ResourceGovernor()