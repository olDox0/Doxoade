# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/thirty_days_converter.py
"""
Conversor Canônico para 30 Days of Python (Asabeneh Yetayeh).
Fonte: https://github.com/Asabeneh/30-Days-Of-Python
Conformidade: ProDeNov 2.1 | Categoria 1 (Python Básico).
"""
from __future__ import annotations
import re, sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

_converters_dir = Path(__file__).resolve().parent
if str(_converters_dir) not in sys.path:
    sys.path.insert(0, str(_converters_dir))

try:
    from .base_converter import BaseCanonicalConverter
except (ImportError, ValueError):
    from base_converter import BaseCanonicalConverter

class ThirtyDaysConverter(BaseCanonicalConverter):
    category = "python_basic_30days"
    canonical_filename = "30_days_of_python.jsonl"
    default_source_url = "https://raw.githubusercontent.com/Asabeneh/30-Days-Of-Python/master"

    DAYS_MAP = [
        (1, "01_Day_Introduction", "readme.md", "Introdução ao Python e Setup"),
        (2, "02_Day_Variables_builtin_functions", "02_variables_builtin_functions.md", "Variáveis e Funções Built-in"),
        (3, "03_Day_Operators", "03_operators.md", "Operadores e Expressões"),
        (4, "04_Day_Strings", "04_strings.md", "Strings e Métodos"),
        (5, "05_Day_Lists", "05_lists.md", "Listas e Estruturas Dinâmicas"),
        (6, "06_Day_Tuples", "06_tuples.md", "Tuplas e Imutabilidade"),
        (7, "07_Day_Sets", "07_sets.md", "Conjuntos (Sets) e Álgebra de Conjuntos"),
        (8, "08_Day_Dictionaries", "08_dictionaries.md", "Dicionários e Chaves"),
        (9, "09_Day_Conditionals", "09_conditionals.md", "Condicionais e Fluxo de Decisão"),
        (10, "10_Day_Loops", "10_loops.md", "Loops (while e for)"),
        (11, "11_Day_Functions", "11_functions.md", "Funções, Parâmetros e Retorno"),
        (12, "12_Day_Modules", "12_modules.md", "Módulos, Pacotes e Imports"),
        (13, "13_Day_List_comprehension", "13_list_comprehension.md", "List Comprehensions e Lambdas"),
        (14, "14_Day_Higher_order_functions", "14_higher_order_functions.md", "Funções de Alta Ordem e Closures"),
        (15, "15_Day_Python_type_errors", "15_python_type_errors.md", "Tipos de Erros Comuns e Depuração"),
        (16, "16_Day_Python_date_time", "16_python_datetime.md", "Datas, Horários e Módulo datetime"),
        (17, "17_Day_Exception_handling", "17_exception_handling.md", "Tratamento de Exceções (try/except)"),
        (18, "18_Day_Regular_expressions", "18_regular_expressions.md", "Expressões Regulares (re)"),
        (19, "19_Day_File_handling", "19_file_handling.md", "Manipulação de Arquivos e I/O"),
        (20, "20_Day_Python_package_manager", "20_python_package_manager.md", "PIP e Gestão de Dependências"),
        (21, "21_Day_Classes_and_objects", "21_classes_and_objects.md", "Classes, Objetos e Herança"),
        (22, "22_Day_Web_scraping", "22_web_scraping.md", "Web Scraping com BeautifulSoup"),
        (23, "23_Day_Virtual_environment", "23_virtual_environment.md", "Ambientes Virtuais (venv)"),
        (24, "24_Day_Statistics", "24_statistics.md", "Estatística e NumPy"),
        (25, "25_Day_Pandas", "25_pandas.md", "Análise de Dados com Pandas"),
        (26, "26_Day_Python_web", "26_python_web.md", "Web e APIs com Flask"),
        (27, "27_Day_Python_with_mongodb", "27_python_with_mongodb.md", "Bancos de Dados NoSQL com MongoDB"),
        (28, "28_Day_API", "28_API.md", "Construção de APIs REST"),
        (29, "29_Day_Building_API", "29_building_API.md", "Projeto Completo de API"),
        (30, "30_Day_Conclusions", "30_conclusions.md", "Conclusão e Boas Práticas"),
    ]

    def _clean_markdown(self, raw_text: str, day_num: int, title: str) -> str:
        """Purga badges de redes sociais, botões de doação e limpa a formatação."""
        # Remove blocos HTML de topo com badges e links sociais
        text = re.sub(r'<div align="center">.*?</div>', '', raw_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', '', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'<<\s*Day\s*\d+.*>>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        if day_num == 1:
            m = re.search(r'#+\s*(?:30\s*Days\s*Of\s*Python:?\s*)?Day\s*1\b.*', text, flags=re.DOTALL | re.IGNORECASE)
            if m:
                text = m.group(0)

        header = f"# 📖 30 Days of Python — Dia {day_num:02d}: {title}\n\n"
        return header + text

    def _download_day(self, item: Tuple[int, str, str, str]) -> Tuple[int, str, str, Optional[str]]:
        day_num, folder, filename, title = item
        candidates = [
            f"{self.default_source_url}/{folder}/{filename}",
            f"{self.default_source_url}/{folder}/README.md",
            f"{self.default_source_url}/{folder}/readme.md",
            f"{self.default_source_url}/readme.md" if day_num == 1 else "",
        ]

        for url in candidates:
            if not url:
                continue
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Doxoade-Ingestor/1.0 (30days)'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        raw_bytes = resp.read()
                        raw_text = raw_bytes.decode('utf-8', errors='replace')
                        if len(raw_text) > 200:
                            return day_num, folder, title, raw_text
            except Exception:
                continue

        return day_num, folder, title, None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Iniciando ingestão do 30 Days of Python ({len(self.DAYS_MAP)} dias)...")
        records: List[Dict[str, Any]] = []

        # Download paralelo dos 30 arquivos
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(self._download_day, item) for item in self.DAYS_MAP]
            for future in as_completed(futures):
                day_num, folder, title, raw_text = future.result()
                if raw_text:
                    slug = f"day_{day_num:02d}_{self.slugify(folder.replace(f'{day_num:02d}_Day_', ''))}"
                    uid = f"python/basic/30_days/{slug}"
                    clean_content = self._clean_markdown(raw_text, day_num, title)
                    keywords = self.extract_keywords(f"Dia {day_num} {title}", clean_content, max_words=45)

                    records.append({
                        "uid": uid,
                        "path": uid,
                        "category": self.category,
                        "title": f"30 Days of Python — Dia {day_num:02d}: {title}",
                        "keywords": keywords,
                        "content": clean_content,
                        "_day": day_num
                    })
                    print(f"  ✔ [OK] Dia {day_num:02d}: {title[:35]}... ({len(clean_content)} bytes)")
                else:
                    print(f"  ✖ [FALHA] Não foi possível baixar o Dia {day_num:02d}: {folder}")

        # Ordena cronologicamente do Dia 01 ao Dia 30
        records.sort(key=lambda r: r["_day"])
        for r in records:
            del r["_day"]

        print(f"\n[*] Concluído download de {len(records)}/{len(self.DAYS_MAP)} capítulos integrais.")
        return self.save_canonical(records)


def run_converter():
    converter = ThirtyDaysConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()
