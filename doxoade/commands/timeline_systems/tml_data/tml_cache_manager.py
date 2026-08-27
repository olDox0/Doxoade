# doxoade/commands/timeline_systems/tml_data/tml_cache_manager.py

class TimelineCache:
    """
    Cache multi-nível:
    - L1: RAM (LRU, 1000 entradas)
    - L2: Disco (SQLite, 10000 entradas)
    """
    
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self.l1_cache = LRUCache(maxsize=1000)
        self.l2_db = self._init_l2_db()
        
    def get(self, key: str) -> Optional[np.ndarray]:
        # Tenta L1
        if data := self.l1_cache.get(key):
            return data
            
        # Tenta L2
        if data := self._load_from_disk(key):
            self.l1_cache.set(key, data)  # Promove para L1
            return data
        return None
        
    def set(self, key: str, data: np.ndarray):
        self.l1_cache.set(key, data)
        self._save_to_disk(key, data)