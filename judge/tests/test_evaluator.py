import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from employee_data import Employee, EmployeeDataError
from evaluator import (
    DECISION_ERROR,
    DECISION_FAIL,
    DECISION_PASS,
    Policy,
    evaluate_all,
    evaluate_employee,
    load_policy,
)

POLICY = Policy(
    role="PROD_ANALYTICS_ROLE",
    version="1.0",
    eligibility={"employment_status": "active", "department": "Data"},
)


def make_employee(**overrides) -> Employee:
    defaults = dict(
        employee_id="E001",
        name="Alice",
        email="alice@example.com",
        department="Data",
        employment_status="active",
        snowflake_username="ALICE",
    )
    defaults.update(overrides)
    return Employee(**defaults)


def test_pass_when_all_conditions_met():
    decision, reason = evaluate_employee(make_employee(), POLICY)
    assert decision == DECISION_PASS
    assert "satisfies" in reason.lower()


def test_fail_when_department_wrong():
    decision, reason = evaluate_employee(make_employee(department="Marketing"), POLICY)
    assert decision == DECISION_FAIL
    assert "department" in reason


def test_fail_when_employment_status_wrong():
    decision, reason = evaluate_employee(make_employee(employment_status="terminated"), POLICY)
    assert decision == DECISION_FAIL
    assert "employment_status" in reason


def test_fail_lists_all_mismatches():
    decision, reason = evaluate_employee(
        make_employee(department="Marketing", employment_status="terminated"), POLICY
    )
    assert decision == DECISION_FAIL
    assert "department" in reason
    assert "employment_status" in reason


def test_case_insensitive_matching():
    decision, _ = evaluate_employee(
        make_employee(department="DATA", employment_status="Active"), POLICY
    )
    assert decision == DECISION_PASS


def test_load_policy_from_repo_file():
    policy = load_policy()
    assert policy.role == "PROD_ANALYTICS_ROLE"
    assert policy.eligibility["department"] == "Data"


def test_evaluate_all_end_to_end_sample_data(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "sample")
    policy = load_policy()
    results = evaluate_all(policy)

    by_user = {r.user: r for r in results}
    assert by_user["ALICE"].decision == DECISION_PASS
    assert by_user["BOB"].decision == DECISION_FAIL
    assert by_user["CHARLIE"].decision == DECISION_FAIL


def test_evaluate_all_errors_when_employee_missing(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "sample")

    def fake_get_employee(snowflake_username, path=None):
        return None

    import evaluator

    monkeypatch.setattr(evaluator, "get_employee_by_snowflake_username", fake_get_employee)
    policy = load_policy()
    results = evaluator.evaluate_all(policy)

    assert all(r.decision == DECISION_ERROR for r in results)


def test_evaluate_all_errors_when_snowflake_query_fails(monkeypatch):
    import evaluator
    from snowflake_client import SnowflakeQueryError

    def fake_get_role_assignments(role, mode=None):
        raise SnowflakeQueryError("simulated connection failure")

    monkeypatch.setattr(evaluator, "get_role_assignments", fake_get_role_assignments)
    policy = load_policy()
    results = evaluator.evaluate_all(policy)

    assert len(results) == 1
    assert results[0].decision == DECISION_ERROR
    assert "access state" in results[0].reason.lower()


def test_evaluate_all_errors_when_employee_source_broken(monkeypatch):
    import evaluator

    def fake_get_employee(snowflake_username, path=None):
        raise EmployeeDataError("simulated parse failure")

    monkeypatch.setattr(evaluator, "get_employee_by_snowflake_username", fake_get_employee)
    policy = load_policy()
    results = evaluator.evaluate_all(policy)

    assert all(r.decision == DECISION_ERROR for r in results)
