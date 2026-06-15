# doxoade/doxoade/tools/memory_pool.py
import sys

class FindingArena:
    def __init__(self, size=2000):
        self._pool = [{'severity':None, 'message':None, 'finding_hash':None} for _ in range(size)]
        self._ptr = 0
        self.recycled_count = 0 

    def rent(self, severity, category, message, file, line):
        if self._ptr >= 2000: return {'severity': severity, 'message': message}
        slot = self._pool[self._ptr]
        # [PLATINUM] Detecta reuso real de espaço na RAM
        if slot.get('message') is not None:
            self.recycled_count += 1
        slot.update({'severity': severity, 'category': category, 'message': message, 'file': file, 'line': line})
        self._ptr += 1
        return slot

    def flush(self):
        self._ptr = 0

    def get_stats(self):
        return self.recycled_count

# --- ANCORAGEM GLOBAL ---
if 'doxoade_arena_instance' not in sys.modules:
    sys.modules['doxoade_arena_instance'] = FindingArena()
finding_arena = sys.modules['doxoade_arena_instance']