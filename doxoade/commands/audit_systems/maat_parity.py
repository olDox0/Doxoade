# doxoade/doxoade/commands/audit_systems/maat_parity.py
"""
ParityGuard v1.2 - O Dinamômetro de Ma'at.
Garante paridade lógica e ganho de performance real (PASC 6.4).
"""
import time
import random
import string
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.vulcan.bridge import vulcan_bridge

class ParityGuard:

    def __init__(self, root):
        self.root = root

    def audit(self, files: list):
        findings = []
        for f in files:
            if not vulcan_bridge.is_binary_stale(f):
                v_mod = vulcan_bridge.get_optimized_module(f)
                if v_mod:
                    findings.extend(self._audit_module_parity(f, v_mod))
        return findings

    def _run_simd_shadow_test(self, file_path, v_mod):
        """Shadow Test: confronta a lógica Python vs Silício (Ares vs Apolo)."""
        findings = []
        data_size = 100 * 1024
        raw_text = ''.join(random.choices(string.ascii_letters + string.digits, k=data_size))
        needle = 'DOXOADE_SIMD_TEST_TOKEN'
        pos_to_insert = random.randint(0, data_size - 100)
        test_content = raw_text[:pos_to_insert] + needle + raw_text[pos_to_insert:]
        if hasattr(v_mod, 'scan_buffer_with_lines'):
            try:
                t0 = time.perf_counter()
                expected_hits = test_content.count(needle)
                py_time = time.perf_counter() - t0
                t1 = time.perf_counter()
                native_hits_list = v_mod.scan_buffer_with_lines(test_content.encode('utf-8'), needle.encode('utf-8'))
                native_hits = len(native_hits_list) if native_hits_list else 0
                v_time = time.perf_counter() - t1
                if expected_hits != native_hits:
                    findings.append({'severity': 'CRITICAL', 'category': 'SHOP-FLOOR', 'message': f'Divergência SIMD em {v_mod.__name__}: PY={expected_hits} vs NATIVE={native_hits}', 'file': file_path, 'line': 0})
                speedup = py_time / v_time if v_time > 0 else 0
                if speedup < 1.1:
                    findings.append({'severity': 'WARNING', 'category': 'VULCAN-EFFICIENCY', 'message': f'Otimização negligenciável em {v_mod.__name__} ({speedup:.2f}x). Considere reverter.', 'file': file_path, 'line': 0})
                else:
                    print(f'   {Fore.GREEN}⚡ [VULCAN-POWER] {v_mod.__name__} validado: {speedup:.1f}x mais rápido.{Style.RESET_ALL}')
            except Exception as e:
                findings.append({'severity': 'CRITICAL', 'category': 'SHOP-FLOOR', 'message': f'Crash durante Shadow Test em {v_mod.__name__}: {str(e)}', 'file': file_path, 'line': 0})
        return findings

    def _perform_shadow_battle(self, func_name, v_func):
        """Realiza o Shadow Test com inputs de estresse (Ares)."""
        test_input = ''.join(random.choices(string.ascii_letters + string.digits, k=10000))
        target_char = random.choice(string.ascii_letters).encode('utf-8')
        try:
            t_native = time.perf_counter()
            res_nat = v_func(test_input.encode('utf-8'), target_char)
            duration_nat = time.perf_counter() - t_native
            if res_nat is None:
                return (False, 'Kernel retornou Void/Null inesperado.')
            return (True, f'Speed: {duration_nat:.6f}s')
        except Exception as e:
            return (False, f'Crash no Silício: {str(e)}')