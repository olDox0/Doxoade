# doxoade/doxoade/commands/impact_systems/impact_state.py
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class ImpactState:
    target_module: str
    project_root: str
    search_path: str
    index: Dict[str, Any] = field(default_factory=dict)

    def get_internal_metadata(self) -> Dict[str, Any]:
        """Recupera metadados (linhas e chamadas) do módulo alvo (PASC 8.12)."""
        return self.index.get(self.target_module, {}).get('metadata', {})

    def get_defined_functions(self) -> List[str]:
        """Lista funções exportadas pelo módulo."""
        return self.index.get(self.target_module, {}).get('defines', [])