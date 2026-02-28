# -*- coding: utf-8 -*-
"""
Experiment Contract Validator
Central authority for experiment.json validation.
"""

from __future__ import annotations

from typing import Any, Dict


class ExperimentContractError(ValueError):
    pass


REQUIRED_TOP_LEVEL = {
    "experiment": dict,
    "execution_policy": dict,
    "constraints": dict,
    "safety": dict,
}


REQUIRED_EXECUTION_POLICY = {
    "mode": str,
    "deterministic": bool,
}


REQUIRED_SAFETY = {
    "network_access": bool,
}


def _require_section(contract: dict, name: str, expected_type: type):
    if name not in contract:
        raise ExperimentContractError(f"Missing required section: '{name}'")
    if not isinstance(contract[name], expected_type):
        raise ExperimentContractError(
            f"Section '{name}' must be of type {expected_type.__name__}"
        )


def _require_keys(section: dict, schema: Dict[str, type], section_name: str):
    for key, expected_type in schema.items():
        if key not in section:
            raise ExperimentContractError(
                f"Missing key '{key}' in section '{section_name}'"
            )
        if not isinstance(section[key], expected_type):
            raise ExperimentContractError(
                f"Key '{key}' in section '{section_name}' "
                f"must be {expected_type.__name__}"
            )


def validate_experiment_contract(contract: Dict[str, Any]) -> None:
    """
    Raises ExperimentContractError if invalid.
    Returns None if valid.
    """

    if not isinstance(contract, dict):
        raise ExperimentContractError("Contract root must be a JSON object")

    # --- Top-level sections ---
    for section, expected_type in REQUIRED_TOP_LEVEL.items():
        _require_section(contract, section, expected_type)

    # --- execution_policy ---
    exec_policy = contract["execution_policy"]
    _require_keys(exec_policy, REQUIRED_EXECUTION_POLICY, "execution_policy")

    if exec_policy["mode"] != "non_interactive":
        raise ExperimentContractError(
            "Only 'non_interactive' execution mode is allowed"
        )

    if exec_policy["deterministic"] is not True:
        raise ExperimentContractError(
            "Experiments must declare deterministic execution"
        )

    # --- safety ---
    safety = contract["safety"]
    _require_keys(safety, REQUIRED_SAFETY, "safety")

    if safety["network_access"] is not False:
        raise ExperimentContractError(
            "Network access must be disabled for experiments"
        )

    # --- constraints ---
    constraints = contract["constraints"]
    if not isinstance(constraints.get("must_not", []), list):
        raise ExperimentContractError(
            "constraints.must_not must be a list"
        )

    # Guardrail semantic
    forbidden = constraints.get("must_not", [])
    if "Modify original source files" not in forbidden:
        raise ExperimentContractError(
            "Contract must explicitly forbid source modification"
        )