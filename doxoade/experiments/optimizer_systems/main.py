# doxoade/doxoade/experiments/optimizer_systems/main.py
"""
Optimizer Systems Experiment - Main Entry Point
Stage: Infrastructure / Contract Enforcement

This module:
- Loads and validates experiment.json
- Initializes a deterministic experiment run
- Creates isolated run directories
- Records execution context
- Does NOT perform optimization yet
"""
from __future__ import annotations
import json
import uuid
import sys
from pathlib import Path
from datetime import datetime
from doxoade.tools.error_info import show_error
BASE_DIR = Path(__file__).resolve().parent
EXPERIMENT_FILE = BASE_DIR / 'experiment.json'
RUNS_DIR = BASE_DIR / 'runs'

class ExperimentError(RuntimeError):
    pass

def load_experiment_contract() -> dict:
    if not EXPERIMENT_FILE.exists():
        raise ExperimentError('experiment.json not found')
    try:
        with EXPERIMENT_FILE.open('r', encoding='utf-8') as f:
            contract = json.load(f)
    except json.JSONDecodeError as exc:
        raise ExperimentError(f'Invalid JSON contract: {exc}') from exc
    return contract

def validate_contract(contract: dict) -> None:
    required_sections = ['experiment', 'goals', 'constraints', 'inputs', 'outputs', 'metrics', 'execution_policy', 'lifecycle', 'safety']
    for section in required_sections:
        if section not in contract:
            raise ExperimentError(f"Missing contract section: '{section}'")
    if contract['execution_policy'].get('mode') != 'non_interactive':
        raise ExperimentError('Only non_interactive mode is supported')
    if not contract['execution_policy'].get('deterministic', False):
        raise ExperimentError('Experiment must be deterministic')
    if contract['safety'].get('network_access', True):
        raise ExperimentError('Network access must be disabled')
    forbidden = contract['constraints'].get('must_not', [])
    if 'Modify original source files' not in forbidden:
        raise ExperimentError('Contract must explicitly forbid source mutation')

def create_run_environment(contract: dict) -> Path:
    RUNS_DIR.mkdir(exist_ok=True)
    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True)
    (run_dir / 'artifacts').mkdir()
    (run_dir / 'logs').mkdir()
    (run_dir / 'snapshots').mkdir()
    return run_dir

def record_run_metadata(run_dir: Path, contract: dict, argv: list[str]) -> None:
    metadata = {'run_id': run_dir.name, 'timestamp_utc': datetime.utcnow().isoformat() + 'Z', 'argv': argv, 'experiment': contract.get('experiment', {}), 'lifecycle': contract.get('lifecycle', {}), 'status': 'initialized'}
    with (run_dir / 'run.json').open('w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def main(argv: list[str]) -> int:
    try:
        contract = load_experiment_contract()
        validate_contract(contract)
        run_dir = create_run_environment(contract)
        record_run_metadata(run_dir, contract, argv)
        print('[EXPERIMENT] Initialized successfully')
        print(f'[RUN] {run_dir.name}')
        print(f'[PATH] {run_dir}')
        return 0
    except ExperimentError as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        return 2
    except Exception as exc:
        show_error(exc, title='EXPERIMENT ERROR')
        return 2
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
