# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_data/tml_aggregator.py

""" Timeline Nexus - Hades-lite (Agregador).
Acesso a dados puro: executa a query e devolve linhas cruas.
Não interpreta, não colore — isso é papel do engine. """

from typing import List, Dict, Any


class TimelineAggregator:
    def __init__(self):
        self._conn = None

    def _connect(self):
        if self._conn is None:
            from doxoade.core_database import get_db_connection
            self._conn = get_db_connection()
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def aggregate(self, scale: str, filters) -> List[Dict[str, Any]]:
        """Executa a agregação e retorna lista de dicts {y, x, total, errors, cmds}."""
        from .tml_query_builder import build_aggregation_query
        sql, params, _dims = build_aggregation_query(scale, filters)
        conn = self._connect()
        rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            result.append({
                'y': r['y'], 'x': r['x'],
                'total': r['total'] or 0,
                'errors': r['errors'] or 0,
                'cmds': (r['cmds'] or '').split(',') if r['cmds'] else [],
            })
        return result
        
    def drill_down(self, model, y: int, x: int, limit: int = 10):
        """Top comandos da célula, fundindo as duas fontes."""
        from .tml_query_builder import build_drill_query
        year_label = (model.row_labels[y] if model.scale == 'month'
                      else model.year)
#        sql, params = build_drill_query(model.scale, y, x, year_label, limit)

        day_num = model.meta.get((y, x)) if model.scale == 'cal' else None
        if model.scale == 'cal' and day_num is None:
            return []   # dia vazio/futuro
        sql, params = build_drill_query(model.scale, y, x, year_label, limit,
                                        month_index=model.month_index, day_num=day_num)
                                        
        conn = self._connect()
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
        
    def query(self, sql, params=()):
        """Query livre (para builders especializados)."""
        conn = self._connect()
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
