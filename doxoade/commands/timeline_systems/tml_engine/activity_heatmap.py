# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_engine/activity_heatmap.py
""" Timeline Nexus - Rá (Orquestrador de Heatmap).
Monta o HeatmapModel pronto para qualquer display (texto, Rich, futuro PNG).
Fluxo: Filters → Aggregator → Células → Triangulação → Modelo. """

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.timeline_systems.tml_data.tml_aggregator import TimelineAggregator
from doxoade.commands.timeline_systems.tml_engine.tml_filters import TimelineFilter
from doxoade.commands.timeline_systems.tml_engine.tml_triangulation import (
    HeatmapCell, assign_intensities,
)

DAY_ABBR = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']
MONTH_ABBR = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN',
              'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']

# Chaves semânticas → estilo de terminal (base; tml_themes assumirá depois)
_STYLE_MAP = {
    'idle':  (Fore.GREY, ''),
    'low':   (Fore.CYAN, ''),
    'mid':   (Fore.LIGHTCYAN_EX, ''),
    'high':  (Fore.GREEN, ''),
    'peak':  (Fore.LIGHTGREEN_EX, Style.BRIGHT),
    'alert': (Fore.RED, Style.BRIGHT),
}


@dataclass
class HeatmapModel:
    """Estrutura render-ready: qualquer display consome isto."""
    scale: str
    year: Optional[int]
    row_labels: List[str]
    col_labels: List[str]
    col_marks: Dict[int, str]                
    cells: List[List[HeatmapCell]]
    stats: Dict = field(default_factory=dict)
    subtitle: str = ''
    month_index: Optional[int] = None
    today_row: Optional[int] = None          
    today_cell: Optional[tuple] = None       
    now_hour: Optional[int] = None           
    meta: Dict = field(default_factory=dict)

    def cell(self, y: int, x: int) -> HeatmapCell:
        return self.cells[y][x]

    def preview(self) -> str:
        """Renderização textual base (█/░) — o Rich virá no tml_display."""
        R = Style.RESET_ALL
        lines = [f"{Fore.CYAN}{Style.BRIGHT}--- [TIMELINE NEXUS] HEATMAP "
                 f"{self.scale.upper()} · {self.year or 'TODOS OS ANOS'} ---{R}"]
        # Header
        lines.append('    ' + ''.join(
            f"{self.col_marks.get(i, '  '):>2}" for i in range(len(self.col_labels))))
        # Linhas
        for y, row_label in enumerate(self.row_labels):
            out = f" {row_label:>3} "
            for x in range(len(self.col_labels)):
                c = self.cells[y][x]
                fg, mod = _STYLE_MAP[c.color_key]
                out += f"{mod}{fg}{c.glyph} {R}"
            lines.append(out)
        # Legenda + stats
        lines.append(f"{Style.DIM}Legenda: ░ 0 · ▒ baixo · ▓ médio · █ alto · "
                     f"█* pico · ■ alerta (>30% erro){R}")
        s = self.stats
        lines.append(f"{Fore.YELLOW}Total: {s.get('total', 0)} cmds · "
                     f"Células ativas: {s.get('active', 0)} · "
                     f"Pico: {s.get('peak_label', '-')} ({s.get('peak_count', 0)}) · "
                     f"Erros: {s.get('error_pct', 0)}%{R}")
        return "\n".join(lines)

    def to_legacy_dict(self) -> Dict:
        matrix = [[c.count for c in row] for row in self.cells]
        details = {f"{c.y}_{c.x}": {'count': c.count, 'errors': c.errors,
                                    'commands': c.commands}
                   for row in self.cells for c in row if c.count > 0}
        return {'scale': self.scale, 'matrix': matrix,
                'dimensions': (len(self.cells), len(self.col_labels)),
                'details': details, 'year': self.year}

@dataclass
class ProjectRecord:
    name: str
    cells: List[HeatmapCell]
    total_cmds: int
    total_errors: int
    last_seen: str
    is_current: bool = False

    @property
    def error_pct(self) -> float:
        return (self.total_errors / self.total_cmds * 100) if self.total_cmds > 0 else 0.0


@dataclass
class ProjectTimelineModel:
    year: int
    projects: List[ProjectRecord]
    current_project: str
    total_cmds_global: int
    active_projects_count: int

# Orquestrador Rá (Classe de Execução)
class ActivityHeatmap:
    """Orquestrador: única porta de entrada para construir modelos."""

    def __init__(self):
        self.aggregator = TimelineAggregator()

    def build_projects_model(self, year: Optional[int] = None,
                             limit: int = 20) -> ProjectTimelineModel:
        """
        Agrega o uso do Doxoade distribuído por projetos hospedeiros e meses.
        """
        from doxoade.commands.timeline_systems.tml_data.project_resolver import (
            resolve_project_name, get_current_project_name
        )

        year = year or datetime.now().year
        year_str = str(year)
        curr_proj = get_current_project_name()

        # Query direta para extrair working_dir, timestamp e erros
        sql = """
            SELECT working_dir, timestamp,
                   (CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) AS is_error
            FROM command_history
            WHERE strftime('%Y', timestamp, 'localtime') = ?
            UNION ALL
            SELECT project_path AS working_dir, timestamp,
                   (CASE WHEN status != 'completed' THEN 1 ELSE 0 END) AS is_error
            FROM events
            WHERE timestamp < (SELECT IFNULL(MIN(timestamp), '9999-12-31') FROM command_history)
              AND strftime('%Y', timestamp, 'localtime') = ?
        """

        conn = self.aggregator._connect()
        rows = conn.execute(sql, (year_str, year_str)).fetchall()

        # Agrupamento em memória: { project_name: { 'cells': [12 cells], 'total': int, 'errors': int, 'last_seen': str } }
        data = {}
        for r in rows:
            p_name = resolve_project_name(r['working_dir'])
            ts = r['timestamp'] or ''
            is_err = r['is_error'] or 0

            try:
                m_idx = int(ts[5:7]) - 1 if len(ts) >= 7 else 0
            except ValueError:
                m_idx = 0

            if p_name not in data:
                data[p_name] = {
                    'cells': [HeatmapCell(y=0, x=m) for m in range(12)],
                    'total': 0,
                    'errors': 0,
                    'last_seen': ts[:10]
                }

            proj = data[p_name]
            if 0 <= m_idx < 12:
                proj['cells'][m_idx].count += 1
                if is_err:
                    proj['cells'][m_idx].errors += 1
            if is_err:
                proj['errors'] += 1
            proj['total'] += 1

            if ts[:10] > proj['last_seen']:
                proj['last_seen'] = ts[:10]

        # Normaliza intensidades globais entre todos os projetos
        all_cells = [c for p in data.values() for c in p['cells']]
        assign_intensities(all_cells)

        # Monta lista de ProjectRecord ordenada pelos mais ativos
        records = []
        for name, p_data in sorted(data.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]:
            records.append(ProjectRecord(
                name=name,
                cells=p_data['cells'],
                total_cmds=p_data['total'],
                total_errors=p_data['errors'],
                last_seen=p_data['last_seen'],
                is_current=(name.lower() == curr_proj.lower())
            ))

        total_global = sum(p['total'] for p in data.values())

        return ProjectTimelineModel(
            year=year,
            projects=records,
            current_project=curr_proj,
            total_cmds_global=total_global,
            active_projects_count=len(data)
        )

    def build_calendar(self, year=None, month=None, command=None, search=None):
        """Todos os dias do mês no calendário real (semanas × dias da semana)."""
        import calendar as _cal
        from doxoade.commands.timeline_systems.tml_data.tml_query_builder import (
            build_aggregation_query)
        year = year or datetime.now().year
        month = month if month is not None else datetime.now().month - 1
        filters = TimelineFilter(command=command, search=search, year=year)
        filters.date_start = f"{year}-{month + 1:02d}-01"
        filters.date_end = f"{year}-{month + 1:02d}-31"
        try:
            sql, params, _dims = build_aggregation_query('day', filters)
            rows = self.aggregator.query(sql, params)
        finally:
            self.aggregator.close()

        first, days = _cal.monthrange(year, month + 1)   
        offset = (first + 1) % 7                          
        ranges = self._month_week_ranges(year, month)
        cells = [[HeatmapCell(y, x) for x in range(7)] for y in range(len(ranges))]
        meta = {}
        for r in rows:
            d = r['x'] + 1
            if 1 <= d <= days:
                w = (d + offset - 1) // 7
                col = (((first + d - 1) % 7) + 1) % 7     # weekday Mon=0 → col Sun=0
                c = cells[w][col]
                c.count, c.errors, c.commands = r['total'], r['errors'], r['cmds']
                meta[(w, col)] = d
        assign_intensities([c for row in cells for c in row])

        labels = [f"S{i + 1} {s:02d}-{e:02d}" for i, (s, e) in enumerate(ranges)]
        model = HeatmapModel(scale='cal', year=year, subtitle=MONTH_ABBR[month],
                             month_index=month, row_labels=labels,
                             col_labels=DAY_ABBR, col_marks=dict(enumerate(DAY_ABBR)),
                             cells=cells, stats=self._compute_stats(cells, labels, DAY_ABBR))
        model.meta = meta
        self._mark_today(model)
        return model
        
    def build(self, scale='hour', year=None, command=None, search=None, month=None):
        year = year or datetime.now().year
        filters = TimelineFilter(command=command, search=search)
        if scale in ('hour', 'day'):
            filters.year = year
        else:
            filters.year = None  # visão multi-anos

        if scale == 'day':
            if month is not None:
                return self.build_calendar(year=year, month=month, command=command, search=search)
            return self.build_day_matrix(year=year, command=command, search=search)

        if scale == 'day' and month is not None:
            return self.build_calendar(year=year, month=month, command=command, search=search)

        if scale == 'week':
            month = month if month is not None else datetime.now().month - 1
            stack = self.build_week_stack(year=year, command=command,
                                          search=search, month=month)
            return stack[0]

        if month is not None and scale == 'hour':
            filters.date_start = f"{year}-{month + 1:02d}-01"
            filters.date_end = f"{year}-{month + 1:02d}-31"

        try:
            rows = self.aggregator.aggregate(scale, filters)
        finally:
            self.aggregator.close()

        # Dimensões e rótulos por escala
        if scale == 'month':
            years = sorted({r['y'] for r in rows}) or [year]
            y_map = {yr: i for i, yr in enumerate(years)}
            n_rows, n_cols = len(years), 12
            row_labels, col_labels = [str(y) for y in years], MONTH_ABBR
            col_marks = {i: m[0] for i, m in enumerate(MONTH_ABBR)}
        elif scale == 'day':
            y_map, n_rows, n_cols = None, 12, 31
            row_labels, col_labels = MONTH_ABBR, [f"{d:02d}" for d in range(1, 32)]
            col_marks = {i: col_labels[i] for i in (0, 7, 14, 21, 28, 30)}
        else:  # hour
            y_map, n_rows, n_cols = None, 7, 24
            row_labels, col_labels = DAY_ABBR, [f"{h:02d}" for h in range(24)]
            col_marks = {0: '0', 6: '6', 12: '12', 18: '18', 23: '23'}

        cells = [[HeatmapCell(y, x) for x in range(n_cols)] for y in range(n_rows)]
        for r in rows:
            y = y_map[r['y']] if y_map else r['y']
            if 0 <= y < n_rows and 0 <= r['x'] < n_cols:
                c = cells[y][r['x']]
                c.count, c.errors, c.commands = r['total'], r['errors'], r['cmds']

        assign_intensities([c for row in cells for c in row])

        return HeatmapModel(scale=scale, year=year if scale != 'month' else None,
                            row_labels=row_labels, col_labels=col_labels,
                            col_marks=col_marks, cells=cells,
                            stats=self._compute_stats(cells, row_labels, col_labels))

    def build_hour_stack(self, year=None, command=None, search=None, month=None):
        """Uma grade 7x24 por mês ativo. Intensidade normalizada no ANO
        inteiro para que as cores sejam comparáveis entre meses."""
        from doxoade.commands.timeline_systems.tml_data.tml_query_builder import (
            build_hour_monthly_query)
        year = year or datetime.now().year
        filters = TimelineFilter(command=command, search=search, year=year)
        try:
            rows = self.aggregator.query(*build_hour_monthly_query(filters))
        finally:
            self.aggregator.close()

        by_month = {}
        for r in rows:
            by_month.setdefault(r['m'], []).append(r)
        months = [m for m in sorted(by_month) if month is None or m == month]

        grids, all_cells = {}, []
        for m in months:
            cells = [[HeatmapCell(y, x) for x in range(24)] for y in range(7)]
            for r in by_month[m]:
                c = cells[r['y']][r['x']]
                c.count, c.errors, c.commands = r['total'], r['errors'], r['cmds']
            grids[m] = cells
            all_cells.extend(c for row in cells for c in row)
        assign_intensities(all_cells)  # escala global = comparação justa

        cols = [f"{h:02d}" for h in range(24)]
        marks = {0: '0', 3: '3', 6: '6', 9: '9', 12: '12', 15: '15', 18: '18', 23: '23'}
        return [HeatmapModel(scale='hour', year=year, subtitle=MONTH_ABBR[m],
                             row_labels=DAY_ABBR, col_labels=cols, col_marks=marks,
                             cells=grids[m],
                             stats=self._compute_stats(grids[m], DAY_ABBR, cols))
                for m in months]

    @staticmethod
    def _month_week_ranges(year, month_idx):
        """Semanas reais do mês: [(start, end)] por linha de calendário."""
        import calendar
        first, days = calendar.monthrange(year, month_idx + 1)  # (1º dia Mon=0, nº de dias)
        offset = (first + 1) % 7                                # converte p/ Sun=0
        ranges, start = [], 1
        while start <= days:
            w = (start + offset - 1) // 7
            end = min(days, (w + 1) * 7 - offset)
            ranges.append((start, end))
            start = end + 1
        return ranges

    def build_week_stack(self, year=None, command=None, search=None, month=None):
        """Um grid semanas×24h por mês. Semanas = linhas reais do calendário."""
        from doxoade.commands.timeline_systems.tml_data.tml_query_builder import (
            build_week_monthly_query)
        year = year or datetime.now().year
        filters = TimelineFilter(command=command, search=search, year=year)
        try:
            rows = self.aggregator.query(*build_week_monthly_query(filters))
        finally:
            self.aggregator.close()

        by_month = {}
        for r in rows:
            by_month.setdefault(r['m'], []).append(r)
        months = ([month] if month is not None else sorted(by_month))

        grids, all_cells = {}, []
        for m in months:
            ranges = self._month_week_ranges(year, m)
            cells = [[HeatmapCell(y, x) for x in range(24)] for y in range(len(ranges))]
            for r in by_month.get(m, []):
                if r['w'] < len(ranges):
                    c = cells[r['w']][r['x']]
                    c.count, c.errors, c.commands = r['total'], r['errors'], r['cmds']
            grids[m] = (ranges, cells)
            all_cells.extend(c for row in cells for c in row)
        assign_intensities(all_cells)  # normalização global p/ comparar semanas

        cols = [f"{h:02d}" for h in range(24)]
        marks = {0: '0', 3: '3', 6: '6', 9: '9', 12: '12', 15: '15', 18: '18', 23: '23'}
        models = []
        for m in months:
            ranges, cells = grids[m]
            labels = [f"S{i + 1} {s:02d}-{e:02d}" for i, (s, e) in enumerate(ranges)]
            models.append(HeatmapModel(
                scale='week', year=year, subtitle=MONTH_ABBR[m], month_index=m,
                row_labels=labels, col_labels=cols, col_marks=marks, cells=cells,
                stats=self._compute_stats(cells, labels, cols)))
        return models

    @staticmethod
    def _compute_stats(cells, row_labels, col_labels) -> Dict:
        total = 0
        errors = 0
        active = 0
        peak = None
        for item in cells:
            row = item if isinstance(item, (list, tuple)) else [item]
            for c in row:
                if c.count > 0:
                    total += c.count
                    errors += c.errors
                    active += 1
                    if peak is None or c.count > peak.count:
                        peak = c
        return {
            'total': total,
            'active': active,
            'error_pct': round(100 * errors / total, 1) if total else 0.0,
            'peak_label': (f"{row_labels[peak.y]} {col_labels[peak.x]}"
                           if peak and peak.count else '-'),
            'peak_count': peak.count if peak else 0,
        }

    @staticmethod
    def _mark_today(model):
        """Destaca o dia atual (anil/laranja) conforme a escala."""
        import calendar
        now = datetime.now()
        if model.scale != 'month' and model.year != now.year:
            return
        if model.scale == 'hour':
            model.today_row = (now.weekday() + 1) % 7  # Sun=0
            model.now_hour = now.hour
        elif model.scale == 'week':
            if model.month_index == now.month - 1:
                first, _d = calendar.monthrange(now.year, now.month)
                offset = (first + 1) % 7
                model.today_row = (now.day + offset - 1) // 7
                model.now_hour = now.hour
        elif model.scale == 'day':
            model.today_cell = (now.month - 1, now.day - 1)
        elif model.scale == 'month':
            if str(now.year) in model.row_labels:
                model.today_cell = (model.row_labels.index(str(now.year)), now.month - 1)
        elif model.scale == 'cal':
            if model.month_index == now.month - 1:
                first, _d = calendar.monthrange(now.year, now.month)
                offset = (first + 1) % 7
                model.today_row = (now.day + offset - 1) // 7
                model.today_cell = (model.today_row,
                                    (((first + now.day - 1) % 7) + 1) % 7)

    def build_day_matrix(self, year: Optional[int] = None, command: Optional[str] = None,
                         search: Optional[str] = None) -> HeatmapModel:
        """
        Gera a matriz anual de dias (12 meses x 31 dias).
        Valida dias reais por mês para evitar dias fictícios (ex: 30 de Fev).
        """
        import calendar
        from doxoade.commands.timeline_systems.tml_data.tml_query_builder import (
            build_aggregation_query,
        )

        year = year or datetime.now().year
        filters = TimelineFilter(command=command, search=search, year=year)

        # 1. Executa a query de agregação dual-source para a escala 'day'
        try:
            sql, params, _dims = build_aggregation_query('day', filters)
            rows = self.aggregator.query(sql, params)
        finally:
            self.aggregator.close()

        # 2. Inicializa a grade 12x31
        cells = [[HeatmapCell(y, x) for x in range(31)] for y in range(12)]
        valid_cells = []
        meta = {}

        # 3. Mapeia dias válidos de cada mês do ano
        for m_idx in range(12):
            _, days_in_month = calendar.monthrange(year, m_idx + 1)
            meta[m_idx] = {'days_in_month': days_in_month}
            for d_idx in range(days_in_month):
                valid_cells.append(cells[m_idx][d_idx])

        # 4. Preenche os dados vindos do banco
        for r in rows:
            m = r['y']  # 0 a 11 (Mês)
            d = r['x']  # 0 a 30 (Dia - 1)
            if 0 <= m < 12 and 0 <= d < meta[m]['days_in_month']:
                c = cells[m][d]
                c.count = r['total']
                c.errors = r['errors']
                c.commands = r['cmds']

        # 5. Triangulação de intensidades (apenas para células válidas)
        assign_intensities(valid_cells)

        # 6. Rótulos e Metadados
        col_labels = [f"{d:02d}" for d in range(1, 32)]
        # Rótulos de cabeçalho espaçados para legibilidade (1, 5, 10, 15, 20, 25, 30)
        col_marks = {i: f"{i + 1}" for i in range(31) if (i + 1) in (1, 5, 10, 15, 20, 25, 30)}

        model = HeatmapModel(
            scale='day',
            year=year,
            row_labels=MONTH_ABBR,
            col_labels=col_labels,
            col_marks=col_marks,
            cells=cells,
            stats=self._compute_stats(cells, MONTH_ABBR, col_labels),  # 👈 Corrigido: 'cells' em vez de 'valid_cells'
            meta=meta
        )

        self._mark_today(model)
        return model

