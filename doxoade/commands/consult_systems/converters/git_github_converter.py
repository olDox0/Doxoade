# -*- coding: utf-8 -*-
# doxoade\commands\consult_systems\converters\git_github_converter.py
from __future__ import annotations
import io, re, sys, urllib.request, zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

_converters_dir = Path(__file__).resolve().parent
if str(_converters_dir) not in sys.path:
    sys.path.insert(0, str(_converters_dir))

try:
    from .base_converter import BaseCanonicalConverter
except (ImportError, ValueError):
    from base_converter import BaseCanonicalConverter

try:
    from ..doc_indexer import DocIndexer
except (ImportError, ValueError):
    from doxoade.commands.consult_systems.doc_indexer import DocIndexer


class GitGithubConverter(BaseCanonicalConverter):
    category = "git_github"
    canonical_filename = "git_github.jsonl"
    default_source_url = (
        "https://github.com/Asabeneh/10-days-of-git-and-github/archive/refs/heads/master.zip"
    )

    # Títulos canônicos por dia (fallback se o split falhar)
    DAY_TITLES = {
        1:  "Introdução ao Git e GitHub",
        2:  "Básico do Git: init, add, commit",
        3:  "Branches e Merges",
        4:  "Repositórios Remotos (Push/Pull)",
        5:  "Documentando no GitHub",
        6:  "Colaboração no GitHub",
        7:  "Git Avançado",
        8:  "Submódulos e Monorepos",
        9:  "Git Hooks",
        10: "GitHub com Heroku / CI",
    }

    def _clean_markdown(self, raw: str, day_num: int, title: str) -> str:
        indexer = DocIndexer()
        text = indexer.html_to_markdown(raw, title_fallback=f"Dia {day_num}: {title}")

        # Remove TOC
        text = re.sub(r"^\s*-\s*\[[^\]]+\]\(#[^)]+\)\s*$", "", text, flags=re.MULTILINE)

        # Remove navegação de dia
        text = re.sub(r"(?:<<|>>)\s*Day\s*\d+.*?$", "", text, flags=re.MULTILINE | re.IGNORECASE)

        # Remove imagens quebradas (./images/*.png, ./images/*.jpg)
        text = re.sub(r'!\[[^\]]*\]\(\./images/[^)]+\)', '', text)

        # Remove código vazio
        text = re.sub(r"^\s*-\s*\[\]\s*\(.*?\)\s*$", "", text, flags=re.MULTILINE)

        # Colapsa linhas vazias
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        header = (
            f"# 10 Days of Git — Dia {day_num:02d}: {title}\n\n"
            f"> Fonte: https://github.com/Asabeneh/10-days-of-git-and-github\n\n"
        )
        return header + text

    def _split_readme_by_day(self, readme_text: str) -> Dict[int, str]:
        """Divide o README.md gigante em seções '# Day N'."""
        # Regex captura "# Day 1" até antes do próximo "# Day 2" (ou fim)
        pattern = re.compile(r"^#\s+Day\s+(\d+)\s*$", re.MULTILINE | re.IGNORECASE)
        matches = list(pattern.finditer(readme_text))
        if not matches:
            return {}

        sections: Dict[int, str] = {}
        for i, m in enumerate(matches):
            day_num = int(m.group(1))
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(readme_text)
            body = readme_text[start:end].strip()
            if body:
                sections[day_num] = body
        return sections

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando ZIP do repositório 10 Days of Git...")
        print(f"    {url}")

        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (Git)"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            zip_bytes = resp.read()
        print(f"[*] ZIP recebido ({len(zip_bytes) / (1024*1024):.2f} MB).")

        readme_text: Optional[str] = None
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for member in zf.namelist():
                if member.lower().endswith("readme.md") and "/" in member:
                    # Pega o README.md da raiz do repo (ex: 10-days-of-git-and-github-master/README.md)
                    parts = member.split("/")
                    if len(parts) == 2 and parts[1].lower() == "readme.md":
                        readme_text = zf.read(member).decode("utf-8", errors="replace")
                        print(f"[*] README.md encontrado: {member} ({len(readme_text)} bytes)")
                        break

        if not readme_text:
            print("  ✖ [FALHA] README.md não encontrado no ZIP.")
            return self.save_canonical([])

        sections = self._split_readme_by_day(readme_text)
        if not sections:
            print("  ✖ [FALHA] Nenhuma seção '# Day N' encontrada no README.md.")
            return self.save_canonical([])

        print(f"[*] Seções detectadas: {sorted(sections.keys())}")

        records: List[Dict[str, Any]] = []
        for day_num in sorted(sections.keys()):
            title = self.DAY_TITLES.get(day_num, f"Dia {day_num}")
            body = sections[day_num]
            clean = self._clean_markdown(body, day_num, title)
            uid = f"git/github/day_{day_num:02d}"
            records.append({
                "uid": uid,
                "path": uid,
                "category": self.category,
                "title": f"10 Days of Git — Dia {day_num:02d}: {title}",
                "keywords": self.extract_keywords(f"Dia {day_num} {title}", clean, max_words=45),
                "content": clean,
            })
            print(f"  ✔ [OK] Dia {day_num:02d}: {title[:40]}... ({len(clean)} bytes)")

        print(f"\n[*] Concluído: {len(records)} dias extraídos do README.md.")
        return self.save_canonical(records)


def run_converter():
    converter = GitGithubConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()
