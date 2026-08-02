# doxoade/tools/source_profile.py
# -*- coding: utf-8 -*-
"""
Source Profile — "o que é fonte, não o que é artefato" (BPC0).
================================================================
Um único perfil de extensões compartilhável (backup, e futuramente
intelligence/audit). Filosofia de Ma'at, DIFERENTE da lista do intelligence:

  • INCLUI  código + markup + config + texto + scripts + build-meta editável.
  • EXCLUI  binário compilado (.pyd/.so/.dll/.o/.exe) → regenerável e pesado.
  • EXCLUI  compactado/mídia/imagens-raster/db/zim   → regenerável ou não-fonte.

POR QUE NÃO COPIAR A LISTA DO intelligence?
  O intelligence quer .pyd/.so para montar o grafo de dependências nativas.
  O backup NÃO os quer: são o peso morto que infla o delta (forense: o delta
  de 3 arquivos / ~37 MB crus que motivou este módulo era dessa classe).
  A lista do backup = fonte não-regenerável; a do intelligence = analisável.

SEGREDOS: .env fica DE FORA por padrão (costuma carregar credenciais).
  Se o seu .env não tem segredo e você quer versioná-lo, adicione-o abaixo.

AJUSTE: este é o ÚNICO lugar a mexer para mudar o escopo de fonte.
"""
from pathlib import Path

# ── código ────────────────────────────────────────────────────────────────
_CODE = (
    ".py", ".pyw", ".pyi", ".pyx", ".pxd",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inl",
    ".cs", ".java", ".go", ".rs", ".rb", ".php", ".lua", ".r", ".m", ".mm",
    ".swift", ".kt", ".kts", ".scala", ".pl", ".pm", ".t", ".ex", ".exs",
    ".erl", ".hs", ".clj", ".elm", ".dart", ".vb", ".fs", ".fsx",
)
# ── scripts / shell / assembly ────────────────────────────────────────────
_SCRIPT = (
    ".sh", ".bash", ".zsh", ".fish", ".ksh", ".csh",
    ".bat", ".cmd", ".ps1", ".psm1", ".psd1",
    ".asm", ".s", ".S", ".nasm",
)
# ── web / markup ──────────────────────────────────────────────────────────
_WEB = (
    ".html", ".htm", ".xhtml",
    ".css", ".scss", ".sass", ".less",
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".astro",
    ".xml", ".xsl", ".xslt", ".svg",
    ".json", ".jsonc", ".json5",
)
# ── config (sem .env: pode conter segredo) ────────────────────────────────
_CONF = (
    ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".properties",
    ".editorconfig", ".gitattributes", ".gitignore", ".dockerfile",
    ".makefile", ".mk", ".cmake", ".gradle", ".bazel",
)
# ── docs / texto ──────────────────────────────────────────────────────────
_DOC = (
    ".md", ".markdown", ".rst", ".txt", ".text",
    ".tex", ".bib", ".csv", ".tsv", ".rtf", ".adoc", ".org",
)

SOURCE_EXTS = frozenset(_CODE + _SCRIPT + _WEB + _CONF + _DOC)

# Arquivos SEM extensão que, ainda assim, são fonte editável à mão.
SOURCE_BASENAMES = frozenset({
    "Makefile", "GNUmakefile", "makefile",
    "Dockerfile", "Containerfile", "Vagrantfile", "Procfile", "Justfile",
    "LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS",
    "README", "CHANGELOG", "CHANGES", "HISTORY",
    "CMakeLists.txt",  # (tem .txt, mas deixa explícito)
})


def ext_of(name: str) -> str:
    """Extensão normalizada (lower, com ponto); '' se não houver."""
    return Path(name).suffix.lower()


def is_source_path(name: str) -> bool:
    """True se o path é fonte não-regenerável (por extensão ou por nome-base)."""
    p = Path(name)
    if p.name in SOURCE_BASENAMES:
        return True
    return p.suffix.lower() in SOURCE_EXTS