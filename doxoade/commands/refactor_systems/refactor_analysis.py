from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .refactor_utils import (
    FunctionHit,
    ReferenceHit,
    find_functions_in_path,
    find_references_in_path,
)


@dataclass
class RefactorSearchResult:
    root: Path
    targets: tuple[str, ...]
    hits: dict[str, list[FunctionHit]] = field(default_factory=dict)

    def missing(self) -> list[str]:
        return [name for name, items in self.hits.items() if not items]

    def ambiguous(self) -> list[str]:
        return [name for name, items in self.hits.items() if len(items) > 1]

    def resolved(self) -> dict[str, FunctionHit]:
        out: dict[str, FunctionHit] = {}
        for name, items in self.hits.items():
            if len(items) == 1:
                out[name] = items[0]
        return out


@dataclass
class RefUsageResult:
    root: Path
    targets: tuple[str, ...]
    refs: dict[str, list[ReferenceHit]] = field(default_factory=dict)

    def missing(self) -> list[str]:
        return [name for name, items in self.refs.items() if not items]


def search_targets(path: Path, targets: list[str]) -> RefactorSearchResult:
    path = path.resolve()
    clean_targets = tuple(dict.fromkeys(t.strip() for t in targets if t.strip()))
    hits = find_functions_in_path(path, clean_targets)
    return RefactorSearchResult(root=path, targets=clean_targets, hits=hits)


def search_references(path: Path, targets: list[str]) -> RefUsageResult:
    path = path.resolve()
    clean_targets = tuple(dict.fromkeys(t.strip() for t in targets if t.strip()))
    refs = find_references_in_path(path, clean_targets)
    return RefUsageResult(root=path, targets=clean_targets, refs=refs)