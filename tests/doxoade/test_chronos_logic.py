# tests/doxoade/test_chronos_logic.py
import pytest
from unittest.mock import MagicMock, patch
from doxoade.chronos import ResourceMonitor

def test_resource_monitor_tree_sum():
    """Testa se o monitor soma corretamente os recursos da árvore de processos."""
    
    # 1. Mock do Processo Pai
    parent = MagicMock()
    parent.cpu_percent.return_value = 10.0
    parent.memory_info.return_value.rss = 100 * 1024 * 1024 # 100 MB
    
    # 2. Mock dos Filhos (Ex: 2 filhos)
    child1 = MagicMock()
    child1.cpu_percent.return_value = 5.0
    child1.memory_info.return_value.rss = 50 * 1024 * 1024 # 50 MB
    
    child2 = MagicMock()
    child2.cpu_percent.return_value = 5.0
    child2.memory_info.return_value.rss = 50 * 1024 * 1024 # 50 MB
    
    # Configura o pai para retornar os filhos
    parent.children.return_value = [child1, child2]
    
    # 3. Instancia o Monitor (sem iniciar a thread para teste unitário)
    monitor = ResourceMonitor(1234)
    
    # 4. Testa a função interna de soma
    cpu_total, mem_mb_total = monitor._get_process_tree_stats(parent)
    
    # Validações
    # CPU: 10 (pai) + 5 (f1) + 5 (f2) = 20
    assert cpu_total == 20.0
    # RAM: 100 + 50 + 50 = 200 MB
    assert mem_mb_total == 200.0

def test_resource_monitor_io_sum():
    """Testa se o monitor soma I/O da árvore."""
    parent = MagicMock()
    parent.io_counters.return_value.read_bytes = 1000
    parent.io_counters.return_value.write_bytes = 500
    
    child = MagicMock()
    child.io_counters.return_value.read_bytes = 1000
    child.io_counters.return_value.write_bytes = 500
    
    parent.children.return_value = [child]
    
    monitor = ResourceMonitor(1234)
    r, w = monitor._get_tree_io(parent)
    
    assert r == 2000
    assert w == 1000

def test_monitor_daemon_property():
    """Garante que a thread é Daemon (não trava o terminal)."""
    monitor = ResourceMonitor(1234)
    assert monitor.daemon is True