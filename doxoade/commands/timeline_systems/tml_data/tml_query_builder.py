# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_data/tml_query_builder.py
""" Timeline Nexus - Atena (Query Builder) - Dual Source.
command_history = autoridade (telemetria); events = era pré-telemetria.
GAP GUARD: events só cobre o vácuo ANTERIOR ao marco zero de command_history
(MIN(timestamp)) — sem datas hardcoded, evita double-counting pós-DEZ.
Fuso: ambas as fontes gravam UTC (Z / +00:00) → 'localtime' nas duas. """
from typing import Tuple, List, Optional

SCALE_HOUR, SCALE_DAY, SCALE_MONTH, SCALE_WEEK = 'hour', 'day', 'month', 'week'


_GAP_GUARD = ("timestamp < (SELECT IFNULL(MIN(timestamp), '9999-12-31') "
              "FROM command_history)")

WEEK_EXPR = ("(CAST(strftime('%d', timestamp, 'localtime') AS INTEGER) + "
             "CAST(strftime('%w', timestamp, 'localtime', 'start of month') AS INTEGER) "
             "- 1) / 7")
             
_HOUR_EXPR = "CAST(strftime('%H', timestamp, 'localtime') AS INTEGER)"


def _yx(scale: str) -> Tuple[str, str]:
    """Expressões strftime (y, x) por escala, sempre no fuso local."""
    if scale == SCALE_HOUR:
        return ("CAST(strftime('%w', timestamp, 'localtime') AS INTEGER)",
                "CAST(strftime('%H', timestamp, 'localtime') AS INTEGER)")
    if scale == SCALE_DAY:
        return ("CAST(strftime('%m', timestamp, 'localtime') AS INTEGER) - 1",
                "CAST(strftime('%d', timestamp, 'localtime') AS INTEGER) - 1")
    if scale == SCALE_MONTH:
        return ("CAST(strftime('%Y', timestamp, 'localtime') AS INTEGER)",
                "CAST(strftime('%m', timestamp, 'localtime') AS INTEGER) - 1")
    if scale == SCALE_WEEK:
        return (WEEK_EXPR, _HOUR_EXPR)
    raise ValueError(f"[TML] Escala desconhecida: {scale}")


def build_aggregation_query(scale: str, filters) -> Tuple[str, List, Optional[Tuple[int, int]]]:
    """Query de agregação dual-source com GROUP BY externo (fusão de fontes)."""
    y_e, x_e = _yx(scale)
    ch_where, ch_params = filters.where_clauses()
    ev_where, ev_params = filters.where_clauses(cmd_col='command',
                                                include_search=False)
    sql = f"""
        SELECT y, x, SUM(total) AS total, SUM(errors) AS errors,
               GROUP_CONCAT(DISTINCT cmd) AS cmds
        FROM (
            SELECT {y_e} AS y, {x_e} AS x, command_name AS cmd,
                   COUNT(*) AS total,
                   SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) AS errors
            FROM command_history
            WHERE {ch_where}
            GROUP BY y, x, cmd
            UNION ALL
            SELECT {y_e} AS y, {x_e} AS x, command AS cmd,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END) AS errors
            FROM events
            WHERE {_GAP_GUARD} AND {ev_where}
            GROUP BY y, x, cmd
        )
        GROUP BY y, x
    """
    dims = {'hour': (7, 24), 'day': (12, 31)}.get(scale)
    return sql, ch_params + ev_params, dims

def build_hour_monthly_query(filters) -> Tuple[str, List]:
    """Grade 7x24 por mês (comparação mensal), dual-source."""
    y_e = "CAST(strftime('%w', timestamp, 'localtime') AS INTEGER)"
    x_e = "CAST(strftime('%H', timestamp, 'localtime') AS INTEGER)"
    m_e = "CAST(strftime('%m', timestamp, 'localtime') AS INTEGER) - 1"
    ch_where, ch_params = filters.where_clauses()
    ev_where, ev_params = filters.where_clauses(cmd_col='command',
                                                include_search=False)
    sql = f"""
        SELECT m, y, x, SUM(total) AS total, SUM(errors) AS errors,
               GROUP_CONCAT(DISTINCT cmd) AS cmds
        FROM (
            SELECT {m_e} AS m, {y_e} AS y, {x_e} AS x, command_name AS cmd,
                   COUNT(*) AS total,
                   SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) AS errors
            FROM command_history WHERE {ch_where}
            GROUP BY m, y, x, cmd
            UNION ALL
            SELECT {m_e} AS m, {y_e} AS y, {x_e} AS x, command AS cmd,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END) AS errors
            FROM events WHERE {_GAP_GUARD} AND {ev_where}
            GROUP BY m, y, x, cmd
        )
        GROUP BY m, y, x
    """
    return sql, ch_params + ev_params

def build_week_monthly_query(filters) -> Tuple[str, List]:
    """Semanas reais do mês (linhas) × 24h (colunas), por mês, dual-source."""
    m_e = "CAST(strftime('%m', timestamp, 'localtime') AS INTEGER) - 1"
    ch_where, ch_params = filters.where_clauses()
    ev_where, ev_params = filters.where_clauses(cmd_col='command', include_search=False)
    sql = f"""
        SELECT m, w, x, SUM(total) AS total, SUM(errors) AS errors,
               GROUP_CONCAT(DISTINCT cmd) AS cmds
        FROM (
            SELECT {m_e} AS m, {WEEK_EXPR} AS w, {_HOUR_EXPR} AS x,
                   command_name AS cmd, COUNT(*) AS total,
                   SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) AS errors
            FROM command_history WHERE {ch_where}
            GROUP BY m, w, x, cmd
            UNION ALL
            SELECT {m_e} AS m, {WEEK_EXPR} AS w, {_HOUR_EXPR} AS x,
                   command AS cmd, COUNT(*) AS total,
                   SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END) AS errors
            FROM events WHERE {_GAP_GUARD} AND {ev_where}
            GROUP BY m, w, x, cmd
        )
        GROUP BY m, w, x
    """
    return sql, ch_params + ev_params

def build_drill_query(scale: str, y: int, x: int, year_label,
                      limit: int = 10) -> Tuple[str, List]:
    """Drill-down dual-source de uma célula específica."""
    y_e, x_e = _yx(scale)
    if scale == SCALE_MONTH:
        cell = f"{y_e} = ? AND {x_e} = ?"
        params = [int(year_label), x]
    if scale == SCALE_WEEK and month_index is not None:
        cell += " AND CAST(strftime('%m', timestamp, 'localtime') AS INTEGER) = ?"
        params.append(month_index + 1)
    if scale == 'cal':
        cell = ("CAST(strftime('%d', timestamp, 'localtime') AS INTEGER) = ? "
                "AND CAST(strftime('%m', timestamp, 'localtime') AS INTEGER) = ? "
                "AND strftime('%Y', timestamp, 'localtime') = ?")
        params = [day_num, month_index + 1, str(year_label)]
    else:
        cell = (f"{y_e} = ? AND {x_e} = ? "
                f"AND strftime('%Y', timestamp, 'localtime') = ?")
        params = [y, x, str(year_label)]
    sql = f"""
        SELECT cmd AS command, SUM(total) AS total, SUM(errors) AS errors
        FROM (
            SELECT command_name AS cmd, COUNT(*) AS total,
                   SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) AS errors
            FROM command_history WHERE {cell}
            GROUP BY cmd
            UNION ALL
            SELECT command AS cmd, COUNT(*) AS total,
                   SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END) AS errors
            FROM events WHERE {_GAP_GUARD} AND {cell}
            GROUP BY cmd
        )
        GROUP BY cmd ORDER BY total DESC LIMIT ?
    """
    return sql, params + params + [limit]
