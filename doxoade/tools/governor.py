# doxoade/doxoade/tools/governor.py
"""
Doxoade Resource Governor - ALB v1.2.
Agora com Sensibilidade de I/O e Latência.
"""
import time
import os
try:
    import psutil
    HAS_PSUTIL = True
except Exception as e:
    import logging as _dox_log
    _dox_log.error(f'[INFRA] unknown: {e}')
    HAS_PSUTIL = False

class ResourceGovernor:

    def __init__(self):
        self.CPU_LIMIT_ECO = 110.0
        self.CPU_LIMIT_CRIT = 180.0
        self.DISK_BUSY_LIMIT = 85.0
        self.RAM_LIMIT_CRIT = 90.0
        self.base_sleep = 0.03
        self.interventions = 0
        self.affected_files = []
        self.enabled = True
        self.last_pace_time = 0
        self._cached_disk = 0
        self._last_disk_check = 0
        self._last_disk_sample = 0
        self._cache = {'cpu': 0.0, 'ram': 0.0, 'disk': 0.0}
        self._last_sample = 0

    def pace(self, targeted=False, force=False, file_path=None):
        if force or not self.enabled:
            return False
        now = time.time()
        if now - self.last_pace_time < 0.5:
            return False
        self.last_pace_time = now
        sleep_time, skip_heavy = self.decide_pace()
        if targeted and (not skip_heavy):
            return False
        if sleep_time > 0:
            time.sleep(sleep_time)
            if skip_heavy:
                self.interventions += 1
                if file_path:
                    self.affected_files.append(file_path)
        return skip_heavy

    def get_savings_estimate(self):
        total_sec = self.interventions * 1.1
        return f'{total_sec:.1f}s' if total_sec < 60 else f'{total_sec / 60:.1f}min'

    def get_system_health(self):
        """Coleta métricas com amostragem estratificada (PASC-6.4)."""
        if not HAS_PSUTIL:
            return (0.0, 0.0, 0.0)
        now = time.time()
        if now - self._last_sample > 1.5:
            self._cache['cpu'] = psutil.cpu_percent(interval=None)
            self._cache['ram'] = psutil.virtual_memory().percent
            self._last_sample = now
        if now - self._last_disk_sample > 10.0:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                disk = psutil.disk_usage(os.getcwd()).percent
                return (cpu, ram, disk)
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f'[INFRA] get_system_health: {e}')
                return (0.0, 0.0, 0.0)
            self._last_disk_sample = now
        return (self._cache['cpu'], self._cache['ram'], self._cache['disk'])

    def decide_pace(self):
        cpu, ram, disk = self.get_system_health()
        if disk > self.DISK_BUSY_LIMIT or ram > self.RAM_LIMIT_CRIT:
            return (self.base_sleep * 15, True)
        if cpu > self.CPU_LIMIT_CRIT:
            return (self.base_sleep * 10, True)
        if cpu > self.CPU_LIMIT_ECO:
            return (self.base_sleep * 2, False)
        return (0.0, False)

    def get_disk_pressure(self):
        """Calcula a pressão de I/O baseada na variação de tempo de atividade."""
        try:
            usage = psutil.disk_usage('/').percent
            return usage
        except Exception as e:
            import logging as _dox_log
            _dox_log.error(f'[INFRA] get_disk_pressure: {e}')
            return 0

    def get_report(self):
        """Retorna o balanço de intervenções para o Logger."""
        return self.interventions
governor = ResourceGovernor()