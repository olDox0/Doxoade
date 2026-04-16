# doxoade/doxoade/tools/memory_pool.py
"""
Doxoade Memory Arena - v1.0.
Pre-allocated object pools para evitar fragmentação de RAM.
Compliance: MPoT-3 (Controlled Allocation).
"""

class FindingArena:
    """Pool de dicionários para resultados do linter (Zero-Allocation Loop)."""

    def __init__(self, size=2000):
        self._pool = [self._create_empty_slot() for _ in range(size)]
        self._ptr = 0
        self._size = size

    def _create_empty_slot(self):
        return {'severity': '', 'category': '', 'message': '', 'file': '', 'line': 0, 'finding_hash': '', 'suggestion_action': None}

    def rent(self, severity, category, message, file, line):
        """Aluga um slot da arena em vez de criar um novo objeto."""
        if self._ptr >= self._size:
            return self._create_empty_slot()
        slot = self._pool[self._ptr]
        slot.update({'severity': severity, 'category': category, 'message': message, 'file': file, 'line': line})
        self._ptr += 1
        return slot

    def flush(self):
        """Reseta o ponteiro para reutilizar a memória no próximo arquivo."""
        self._ptr = 0
finding_arena = FindingArena()