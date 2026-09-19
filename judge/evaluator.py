"""Judge: the deterministic evaluation engine.

Compares each user currently holding the policy's Snowflake role (the
Bailiff's concern) against the eligibility policy (the Jury) using only
explicit, deterministic rules. No LLM is involved in the PASS/FAIL/ERROR
decision — see PRD §7 and §17.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from employee_data import Employee, EmployeeDataError, get_employee_by_snowflake_username
from snowflake_client import SnowflakeQueryError, get_role_assignments

POLICIES_DIR = Path(__file__).parent / "policies"
DEFAULT_POLICY_PATH = POLICIES_DIR / "prod_analytics_role.yaml"

DECISION_PASS = "PASS"
DECISION_FAIL = "FAIL"
DECISION_ERROR = "ERROR"


@dataclass(frozen=True)
class Policy:
    role: str
    version: str
    # Each value is a single expected string, or a list of strings meaning
    # "any of these" (e.g. department: [TRUST, GRC]).
    eligibility: dict[str, str | list[str]]


class PolicyError(Exception):
    """Raised when the policy file itself cannot be loaded or is malformed."""


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> Policy:
    if not path.exists():
        raise PolicyError(f"Policy file not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as exc:  # noqa: BLE001
        raise PolicyError(f"Failed to parse policy file: {exc}") from exc

    if not raw or "role" not in raw or "eligibility" not in raw:
        raise PolicyError(f"Policy file missing required keys 'role'/'eligibility': {path}")

    return Policy(
        role=str(raw["role"]),
        version=str(raw.get("version", "unknown")),
        eligibility=dict(raw["eligibility"]),
    )


def load_policies(directory: Path = POLICIES_DIR) -> list[Policy]:
    """Load every ``*.yaml`` policy in ``directory``, sorted by filename.

    Raises PolicyError if any file is malformed or the directory holds no
    policies — an empty set must never look like "nothing to check".
    """
    paths = sorted(directory.glob("*.yaml"))
    if not paths:
        raise PolicyError(f"No policy files found in: {directory}")
    return [load_policy(p) for p in paths]


@dataclass(frozen=True)
class EvaluationResult:
    user: str
    role: str
    decision: str  # PASS | FAIL | ERROR
    reason: str
    policy_version: str
    evaluated_at: str
    employee_attributes_used: dict[str, Any] | None = field(default=None)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def evaluate_employee(employee: Employee, policy: Policy) -> tuple[str, str]:
    """Apply the policy's eligibility rules to one employee.

    Returns (decision, reason). Only ever returns PASS or FAIL — ERROR is
    reserved for missing/unavailable data, handled by the caller.
    """
    mismatches: list[str] = []
    attrs = {
        "employment_status": employee.employment_status,
        "department": employee.department,
        "email": employee.email,
    }

    for field_name, expected in policy.eligibility.items():
        actual = attrs.get(field_name)
        allowed = expected if isinstance(expected, list) else [expected]
        allowed_norm = {str(a).strip().lower() for a in allowed}
        if actual is None or actual.strip().lower() not in allowed_norm:
            shown = "|".join(str(a) for a in allowed)
            mismatches.append(f"{field_name}_expected={shown}, {field_name}_actual={actual}")

    if mismatches:
        return DECISION_FAIL, "; ".join(mismatches)
    return DECISION_PASS, "User satisfies all eligibility requirements."


def evaluate_policies(policies: list[Policy]) -> list[EvaluationResult]:
    """Evaluate every policy and concatenate the results, in policy order."""
    results: list[EvaluationResult] = []
    for policy in policies:
        results.extend(evaluate_all(policy))
    return results


def evaluate_all(policy: Policy | None = None) -> list[EvaluationResult]:
    """Evaluate every user currently holding the policy's role.

    Distinguishes PASS/FAIL (a real decision) from ERROR (Judge could not
    reach a decision because a data source failed) per PRD §12 — missing
    data must never be reported as PASS.
    """
    policy = policy or load_policy()
    results: list[EvaluationResult] = []
    now = _now_iso()

    try:
        assignments = get_role_assignments(policy.role)
    except SnowflakeQueryError as exc:
        results.append(
            EvaluationResult(
                user="unknown",
                role=policy.role,
                decision=DECISION_ERROR,
                reason=f"Unable to retrieve current access state: {exc}",
                policy_version=policy.version,
                evaluated_at=now,
            )
        )
        return results

    for assignment in assignments:
        try:
            employee = get_employee_by_snowflake_username(assignment.user)
        except EmployeeDataError as exc:
            results.append(
                EvaluationResult(
                    user=assignment.user,
                    role=assignment.assigned_role,
                    decision=DECISION_ERROR,
                    reason=f"Unable to evaluate employee attributes: {exc}",
                    policy_version=policy.version,
                    evaluated_at=now,
                )
            )
            continue

        if employee is None:
            results.append(
                EvaluationResult(
                    user=assignment.user,
                    role=assignment.assigned_role,
                    decision=DECISION_ERROR,
                    reason="Unable to evaluate employee attributes: no matching employee record.",
                    policy_version=policy.version,
                    evaluated_at=now,
                )
            )
            continue

        decision, reason = evaluate_employee(employee, policy)
        results.append(
            EvaluationResult(
                user=assignment.user,
                role=assignment.assigned_role,
                decision=decision,
                reason=reason,
                policy_version=policy.version,
                evaluated_at=now,
                employee_attributes_used={
                    "employee_id": employee.employee_id,
                    "name": employee.name,
                    "email": employee.email,
                    "department": employee.department,
                    "employment_status": employee.employment_status,
                },
            )
        )

    return results
