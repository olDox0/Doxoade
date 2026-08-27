# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_engine/tml_filters.py
""" Timeline Nexus - Ártemis (Filtros).
Modelo de recorte temporal/semântico sobre command_history. """

from dataclasses import dataclass
from typing import Optional, List, Tuple

@dataclass
class TimelineFilter:
    """Filtros aplicáveis às agregações. Base primeiro: comando, ano, período e busca."""
    command: Optional[str] = None
    year: Optional[int] = None
    date_start: Optional[str] = None   # 'YYYY-MM-DD'
    date_end: Optional[str] = None     # 'YYYY-MM-DD'
    search: Optional[str] = None       # busca em full_command_line

    def where_clauses(self, cmd_col: str = 'command_name',
                      include_search: bool = True):
        """Retorna (fragmento_sql, params). cmd_col varia por fonte
        (command_name vs command); search só existe em command_history."""
        clauses, params = [], []
        if self.year is not None:
            clauses.append("strftime('%Y', timestamp, 'localtime') = ?")
            params.append(str(self.year))
        if self.command:
            clauses.append(f"{cmd_col} = ?")
            params.append(self.command)
        if self.date_start:
            clauses.append("timestamp >= ?")
            params.append(f"{self.date_start}T00:00:00")
        if self.date_end:
            clauses.append("timestamp <= ?")
            params.append(f"{self.date_end}T23:59:59")
        if self.search and include_search:
            clauses.append("full_command_line LIKE ?")
            params.append(f"%{self.search}%")
        return (" AND ".join(clauses) if clauses else "1=1"), params

    def cache_key(self) -> str:
        """Chave estável para o futuro cache (Hermes)."""
        return "|".join(map(str, [self.command, self.year, self.date_start,
                                  self.date_end, self.search]))