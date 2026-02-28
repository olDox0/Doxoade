# -*- coding: utf-8 -*-
# doxoade/commands/experimental.py

#experiments/
#  <experiment_name>/
#    experiment.json        # contrato (obrigatório)
#    main.py                # entrypoint (obrigatório)
#    README.md              # intenção científica
#    runs/                  # execuções
#    artifacts/             # saídas consolidadas
#    probes/                # instrumentos (opcional)
#    __init__.py

"""
Experimental Command Interface
Entry point for managing and running experiments.
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

from doxoade.tools.error_info import DoxoadeError


EXPERIMENTS_DIR = Path(__file__).resolve().parents[1] / "experiments"


def list_experiments() -> None:
    if not EXPERIMENTS_DIR.exists():
        print("[EXPERIMENTAL] No experiments directory found")
        return

    experiments = [
        d.name for d in EXPERIMENTS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]

    if not experiments:
        print("[EXPERIMENTAL] No experiments registered")
        return

    print("[EXPERIMENTAL] Available experiments:")
    for exp in sorted(experiments):
        print(f" - {exp}")


def run_experiment(name: str, argv: list[str]) -> int:
    exp_dir = EXPERIMENTS_DIR / name
    if not exp_dir.exists():
        raise DoxoadeError(f"Experiment '{name}' not found")

    main_file = exp_dir / "main.py"
    if not main_file.exists():
        raise DoxoadeError(f"Experiment '{name}' has no main.py")

    spec = importlib.util.spec_from_file_location(
        f"doxoade.experiments.{name}.main",
        main_file
    )
    if spec is None or spec.loader is None:
        raise DoxoadeError("Failed to load experiment entry point")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "main"):
        raise DoxoadeError("Experiment main.py must expose main(argv)")

    return int(module.main(argv))


def experimental(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print("Usage:")
        print("  doxoade experimental list")
        print("  doxoade experimental run <experiment> [args]")
        return 0

    command = argv[0]

    try:
        if command == "list":
            list_experiments()
            return 0

        if command == "run":
            if len(argv) < 2:
                raise DoxoadeError("Missing experiment name")

            name = argv[1]
            return run_experiment(name, argv[2:])

        raise DoxoadeError(f"Unknown experimental command: {command}")

    except DoxoadeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


# Hook for doxoade command router
def register():
    return {
        "experimental": experimental
    }
    
def init_experiment(name: str) -> int:
    exp_dir = EXPERIMENTS_DIR / name

    if exp_dir.exists():
        raise DoxoadeError(f"Experiment '{name}' already exists")

    exp_dir.mkdir(parents=True)
    (exp_dir / "runs").mkdir()
    (exp_dir / "artifacts").mkdir()
    (exp_dir / "probes").mkdir()

    # __init__.py
    (exp_dir / "__init__.py").write_text("", encoding="utf-8")

    # experiment.json
    (exp_dir / "experiment.json").write_text(
        """{
  "experiment": {
    "name": "%s",
    "status": "incubation"
  },
  "execution_policy": {
    "mode": "non_interactive",
    "deterministic": true
  },
  "constraints": {
    "must_not": [
      "Modify original source files"
    ]
  },
  "safety": {
    "network_access": false
  }
}
""" % name,
        encoding="utf-8"
    )

    # main.py
    (exp_dir / "main.py").write_text(
        '''# -*- coding: utf-8 -*-
"""
Experiment entrypoint.
"""

def main(argv):
    print("[EXPERIMENT] Initialized but not implemented")
    return 0
''',
        encoding="utf-8"
    )

    # README.md
    (exp_dir / "README.md").write_text(
        f"# Experiment: {name}\n\nDescribe the intent of this experiment.\n",
        encoding="utf-8"
    )

    print(f"[EXPERIMENTAL] Experiment '{name}' initialized")
    return 0