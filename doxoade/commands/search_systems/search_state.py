# doxoade/doxoade/commands/search_systems/search_state.py
"""SearchState - Contrato de Interface Nexus (PASC 8.7)."""
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class SearchState:
    root: str
    query: str
    matches: List[Dict[str, Any]] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    db_results: Dict[str, List] = field(default_factory=lambda: {'incidents': [], 'solutions': []})
    git_results: List[Dict[str, Any]] = field(default_factory=list)
    limit: int = 20
    is_full_mode: bool = False