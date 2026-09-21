"""Judge: the deterministic evaluation engine.

Compares each user currently holding the policy's Snowflake role (the
Bailiff's concern) against the eligibility policy (the Jury) using only
explicit, deterministic rules. No LLM is involved in the PASS/FAIL/ERROR
decision — see PRD §7 and §17.
"""

# Store type hints as strings instead of evaluating them. This lets the file
# use `X | None`, `list[...]` etc. and refer to classes defined further down.
from __future__ import annotations

import datetime as dt                        # dates/times (used for the timestamp)
from dataclasses import dataclass, field     # auto-generate boilerplate for data-holder classes
from pathlib import Path                     # filesystem paths as objects
from typing import Any                       # "any type" hint

import yaml                                  # third-party: parses .yaml policy files

# Project-local modules: the two data sources the evaluator compares.
from sources.employee_data import Employee, EmployeeDataError, get_employee_by_snowflake_username
from sources.snowflake_client import SnowflakeQueryError, get_role_assignments

# Build a path to the `policies/` folder relative to THIS file, so it works
# no matter where the program is launched from:
#   __file__  -> judge/engine/evaluator.py
#   .resolve()-> make it absolute
#   .parent   -> judge/engine/      .parent again -> judge/
#   / "policies" -> judge/policies/
POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"
DEFAULT_POLICY_PATH = POLICIES_DIR / "prod_analytics_role.yaml"

# Constants for the three possible outcomes. Using named constants instead of
# retyping the strings avoids typos.
DECISION_PASS = "PASS"
DECISION_FAIL = "FAIL"
DECISION_ERROR = "ERROR"


# frozen=True -> instances are immutable after creation (can't reassign fields).
@dataclass(frozen=True)
class Policy:
    role: str        # the Snowflake role this policy governs
    version: str     # policy version, recorded on every result for auditing
    # Each value is a single expected string, or a list of strings meaning
    # "any of these" (e.g. department: [TRUST, GRC]).
    eligibility: dict[str, str | list[str]]
    # Named-holder policies (e.g. ACCOUNTADMIN): the only Snowflake users
    # allowed to hold the role. Decided by name, with no HR lookup, so it
    # works for service accounts that have no employee record.
    allowed_users: tuple[str, ...] = ()   # default: empty tuple (= "not a named-holder policy")


# A custom exception type, so callers can catch policy-file problems specifically.
class PolicyError(Exception):
    """Raised when the policy file itself cannot be loaded or is malformed."""


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> Policy:
    # Fail early with a clear message if the file isn't there.
    if not path.exists():
        raise PolicyError(f"Policy file not found: {path}")
    try:
        # Open the file and parse the YAML into plain Python dicts/lists.
        # safe_load (not load) refuses to construct arbitrary Python objects.
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as exc:  # noqa: BLE001
        # Wrap any parse error in PolicyError; `from exc` keeps the original
        # error attached for debugging.
        raise PolicyError(f"Failed to parse policy file: {exc}") from exc

    # Validation: the file must be non-empty and contain a `role` key.
    if not raw or "role" not in raw:
        raise PolicyError(f"Policy file missing required key 'role': {path}")
    # Exactly one decision mode: attribute rules or a named allowlist.
    # `(A in raw) == (B in raw)` is True when BOTH or NEITHER key is present,
    # which are both invalid — we need exactly one.
    if ("eligibility" in raw) == ("allowed_users" in raw):
        raise PolicyError(f"Policy file must set exactly one of 'eligibility'/'allowed_users': {path}")

    # `.get` returns None if the key is missing (no KeyError).
    allowed_users = raw.get("allowed_users")
    # If the key IS present, it must be a non-empty list.
    if allowed_users is not None and (not isinstance(allowed_users, list) or not allowed_users):
        raise PolicyError(f"'allowed_users' must be a non-empty list: {path}")

    # Convert the raw YAML data into a validated, immutable Policy object.
    return Policy(
        role=str(raw["role"]),
        version=str(raw.get("version", "unknown")),         # fall back to "unknown" if absent
        eligibility=dict(raw.get("eligibility") or {}),     # `or {}` handles a missing/None value
        allowed_users=tuple(str(u) for u in allowed_users or ()),  # list -> tuple of strings
    )


def load_policies(directory: Path = POLICIES_DIR) -> list[Policy]:
    """Load every ``*.yaml`` policy in ``directory``, sorted by filename.

    Raises PolicyError if any file is malformed or the directory holds no
    policies — an empty set must never look like "nothing to check".
    """
    # glob finds files matching the pattern; sorted() makes the order
    # deterministic (glob order is arbitrary).
    paths = sorted(directory.glob("*.yaml"))
    # Zero policies is treated as an error, not as "everything passes".
    if not paths:
        raise PolicyError(f"No policy files found in: {directory}")
    # List comprehension: load each file into a Policy.
    return [load_policy(p) for p in paths]


@dataclass(frozen=True)
class EvaluationResult:
    # One row of output: the verdict for a single (user, role) pair.
    user: str
    role: str
    decision: str  # PASS | FAIL | ERROR
    reason: str                  # human-readable explanation of the decision
    policy_version: str          # which policy version produced this result
    evaluated_at: str            # ISO timestamp of when the evaluation ran
    # Snapshot of the HR data used for the decision; None when not applicable
    # (named-holder policies and ERROR results have no employee lookup).
    employee_attributes_used: dict[str, Any] | None = field(default=None)


def _now_iso() -> str:
    # Current time in UTC (timezone-aware), formatted like "2026-09-20T14:03:07+00:00".
    # timespec="seconds" drops microseconds. The leading _ marks it as module-private.
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def evaluate_employee(employee: Employee, policy: Policy) -> tuple[str, str]:
    """Apply the policy's eligibility rules to one employee.

    Returns (decision, reason). Only ever returns PASS or FAIL — ERROR is
    reserved for missing/unavailable data, handled by the caller.
    """
    mismatches: list[str] = []   # collects a description of every rule that failed
    # Map the field names a policy can mention to this employee's actual values.
    attrs = {
        "employment_status": employee.employment_status,
        "department": employee.department,
        "email": employee.email,
    }

    # Check every rule in the policy, e.g. ("department", ["TRUST", "GRC"]).
    for field_name, expected in policy.eligibility.items():
        actual = attrs.get(field_name)   # employee's value (None if the field name is unknown)
        # Normalize: a single string becomes a one-item list, so both forms
        # are handled the same way below.
        allowed = expected if isinstance(expected, list) else [expected]
        # Set of allowed values, trimmed and lowercased -> comparison is
        # case- and whitespace-insensitive.
        allowed_norm = {str(a).strip().lower() for a in allowed}
        # Fail this rule if the value is missing OR not in the allowed set.
        if actual is None or actual.strip().lower() not in allowed_norm:
            shown = "|".join(str(a) for a in allowed)   # e.g. "TRUST|GRC"
            mismatches.append(f"{field_name}_expected={shown}, {field_name}_actual={actual}")

    # Any mismatch means FAIL; report ALL of them, not just the first.
    if mismatches:
        return DECISION_FAIL, "; ".join(mismatches)
    return DECISION_PASS, "User satisfies all eligibility requirements."


def evaluate_named_holder(username: str, policy: Policy) -> tuple[str, str]:
    """Apply an ``allowed_users`` policy: PASS only for a listed user.

    Case-insensitive — Snowflake returns quoted user names (e.g. an
    account's signup user) in their original lowercase.
    """
    # Normalized set of approved usernames for fast, case-insensitive lookup.
    allowed = {u.strip().lower() for u in policy.allowed_users}
    if username.strip().lower() in allowed:
        return DECISION_PASS, "User is an approved holder of this role."
    return DECISION_FAIL, f"user_expected={'|'.join(policy.allowed_users)}, user_actual={username}"


def evaluate_policies(policies: list[Policy]) -> list[EvaluationResult]:
    """Evaluate every policy and concatenate the results, in policy order.

    All results share one ``evaluated_at`` — the dashboard treats rows with
    the same timestamp as a single run ("Latest Evaluation").
    """
    now = _now_iso()   # take ONE timestamp up front so every row in this run matches
    results: list[EvaluationResult] = []
    for policy in policies:
        # extend() appends each item of the returned list (vs. append(), which adds the list itself).
        results.extend(evaluate_all(policy, evaluated_at=now))
    return results


def evaluate_all(policy: Policy | None = None, evaluated_at: str | None = None) -> list[EvaluationResult]:
    """Evaluate every user currently holding the policy's role.

    Distinguishes PASS/FAIL (a real decision) from ERROR (Judge could not
    reach a decision because a data source failed) per PRD §12 — missing
    data must never be reported as PASS.
    """
    policy = policy or load_policy()   # no policy passed in -> load the default one
    results: list[EvaluationResult] = []
    now = evaluated_at or _now_iso()   # use the caller's timestamp if given, else make one

    # Step 1: ask Snowflake who currently holds this role.
    try:
        assignments = get_role_assignments(policy.role)
    except SnowflakeQueryError as exc:
        # Snowflake unreachable -> we can't know who has access. Report a
        # single ERROR row rather than pretending everything is fine.
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
        return results   # nothing more can be evaluated, so stop here

    # Step 2: judge each user who holds the role.
    for assignment in assignments:
        # Branch A: named-holder policy -> decide purely by username, no HR lookup.
        if policy.allowed_users:
            decision, reason = evaluate_named_holder(assignment.user, policy)
            results.append(
                EvaluationResult(
                    user=assignment.user,
                    role=assignment.assigned_role,
                    decision=decision,
                    reason=reason,
                    policy_version=policy.version,
                    evaluated_at=now,
                )
            )
            continue   # skip to the next user; the HR-based logic below doesn't apply

        # Branch B: attribute-based policy -> look the user up in the HR data.
        try:
            employee = get_employee_by_snowflake_username(assignment.user)
        except EmployeeDataError as exc:
            # HR data source failed -> ERROR, never a silent PASS.
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

        # The lookup worked but found nobody: also ERROR (an unknown person
        # holding the role is something a human needs to look at).
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

        # We have the employee -> apply the eligibility rules (PASS or FAIL).
        decision, reason = evaluate_employee(employee, policy)
        results.append(
            EvaluationResult(
                user=assignment.user,
                role=assignment.assigned_role,
                decision=decision,
                reason=reason,
                policy_version=policy.version,
                evaluated_at=now,
                # Record exactly which HR data the decision was based on (audit trail).
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
