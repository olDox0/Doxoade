# doxoade/doxoade/rescue_systems/execution_context.py
from __future__ import annotations
import os
import sys
import platform
from enum import Enum
from dataclasses import dataclass

class ExecutionMode(Enum):
    PROD = 'prod'
    TEST = 'test'
    SANDBOX = 'sandbox'
    ANALYSIS = 'analysis'
    CI = 'ci'

class Environment(Enum):
    LOCAL = 'local'
    DOXOADE = 'doxoade'
    CI = 'ci'
    UNKNOWN = 'unknown'

@dataclass(frozen=True)
class ExecutionContext:
    mode: ExecutionMode
    environment: Environment
    python_version: str
    platform: str
    allow_imports: bool
    interactive: bool
    strict: bool

    @staticmethod
    def detect(*, mode: ExecutionMode, allow_imports: bool | None=None, strict: bool | None=None) -> 'ExecutionContext':
        env = _detect_environment()
        if allow_imports is None:
            allow_imports = mode in {ExecutionMode.TEST, ExecutionMode.ANALYSIS}
        if strict is None:
            strict = mode in {ExecutionMode.PROD, ExecutionMode.CI}
        interactive = env in {Environment.LOCAL, Environment.DOXOADE}
        return ExecutionContext(mode=mode, environment=env, python_version=sys.version.split()[0], platform=platform.system().lower(), allow_imports=allow_imports, interactive=interactive, strict=strict)

def _detect_environment() -> Environment:
    if os.getenv('GITHUB_ACTIONS') == 'true':
        return Environment.CI
    if os.getenv('DOXOADE_ACTIVE') == '1':
        return Environment.DOXOADE
    if sys.stdin and sys.stdin.isatty():
        return Environment.LOCAL
    return Environment.UNKNOWN