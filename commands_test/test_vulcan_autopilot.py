import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.autopilot import VulcanAutopilot


class _AdvisorStub:
    def __init__(self, compiled: set[str]):
        self.compiled = compiled

    def _is_already_compiled(self, file_path: str) -> bool:
        return file_path in self.compiled


def test_filter_candidates_skips_already_compiled_when_not_forced(monkeypatch):
    ap = object.__new__(VulcanAutopilot)
    ap.advisor = _AdvisorStub({"b.py"})

    monkeypatch.setattr(
        "doxoade.tools.vulcan.forge.assess_file_for_vulcan",
        lambda file_path: (True, None),
    )

    result = ap._filter_candidates(
        [{"file": "a.py"}, {"file": "b.py"}],
        force_recompile=False,
    )

    assert [c["file"] for c in result] == ["a.py"]


def test_filter_candidates_keeps_compiled_when_forced(monkeypatch):
    ap = object.__new__(VulcanAutopilot)
    ap.advisor = _AdvisorStub({"b.py"})

    monkeypatch.setattr(
        "doxoade.tools.vulcan.forge.assess_file_for_vulcan",
        lambda file_path: (True, None),
    )

    result = ap._filter_candidates(
        [{"file": "a.py"}, {"file": "b.py"}],
        force_recompile=True,
    )

    assert [c["file"] for c in result] == ["a.py", "b.py"]
