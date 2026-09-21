import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.employee_data import Employee, EmployeeDataError
from engine.evaluator import (
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

    from engine import evaluator

    monkeypatch.setattr(evaluator, "get_employee_by_snowflake_username", fake_get_employee)
    policy = load_policy()
    results = evaluator.evaluate_all(policy)

    assert all(r.decision == DECISION_ERROR for r in results)


def test_evaluate_all_errors_when_snowflake_query_fails(monkeypatch):
    from engine import evaluator
    from sources.snowflake_client import SnowflakeQueryError

    def fake_get_role_assignments(role, mode=None):
        raise SnowflakeQueryError("simulated connection failure")

    monkeypatch.setattr(evaluator, "get_role_assignments", fake_get_role_assignments)
    policy = load_policy()
    results = evaluator.evaluate_all(policy)

    assert len(results) == 1
    assert results[0].decision == DECISION_ERROR
    assert "access state" in results[0].reason.lower()


def test_evaluate_all_errors_when_employee_source_broken(monkeypatch):
    from engine import evaluator

    def fake_get_employee(snowflake_username, path=None):
        raise EmployeeDataError("simulated parse failure")

    monkeypatch.setattr(evaluator, "get_employee_by_snowflake_username", fake_get_employee)
    policy = load_policy()
    results = evaluator.evaluate_all(policy)

    assert all(r.decision == DECISION_ERROR for r in results)


TRUST_POLICY = Policy(
    role="PROD_TRUST_RO_ROLE",
    version="1.0",
    eligibility={"employment_status": "active", "department": ["TRUST", "GRC"]},
)

ADMIN_POLICY = Policy(
    role="PROD_ADMIN_ROLE",
    version="1.0",
    eligibility={"employment_status": "active", "email": "spencer@example.com"},
)


@pytest.mark.parametrize("dept", ["TRUST", "GRC", "grc"])
def test_list_valued_department_passes_on_any_match(dept):
    decision, _ = evaluate_employee(make_employee(department=dept), TRUST_POLICY)
    assert decision == DECISION_PASS


def test_list_valued_department_fails_when_none_match():
    decision, reason = evaluate_employee(make_employee(department="Data"), TRUST_POLICY)
    assert decision == DECISION_FAIL
    assert "department_expected=TRUST|GRC" in reason


def test_empty_list_never_matches():
    policy = Policy(role="R", version="1.0", eligibility={"department": []})
    decision, _ = evaluate_employee(make_employee(), policy)
    assert decision == DECISION_FAIL


def test_email_condition_matches_case_insensitively():
    decision, _ = evaluate_employee(make_employee(email="Spencer@Example.com"), ADMIN_POLICY)
    assert decision == DECISION_PASS


def test_email_condition_fails_for_other_user():
    decision, reason = evaluate_employee(make_employee(email="winston@example.com"), ADMIN_POLICY)
    assert decision == DECISION_FAIL
    assert "email" in reason


def test_unknown_attribute_fails_closed():
    policy = Policy(role="R", version="1.0", eligibility={"cost_center": "42"})
    decision, _ = evaluate_employee(make_employee(), policy)
    assert decision == DECISION_FAIL


def test_load_policies_loads_all_repo_policies():
    from engine.evaluator import load_policies

    by_role = {p.role: p for p in load_policies()}
    assert set(by_role) == {
        "PROD_ANALYTICS_ROLE",
        "PROD_ACCOUNTING_RO_ROLE",
        "PROD_TRUST_RO_ROLE",
        "PROD_MARKETING_RO_ROLE",
        "PROD_ADMIN_ROLE",
        "ACCOUNTADMIN",
        "SECURITYADMIN",
    }
    assert by_role["PROD_TRUST_RO_ROLE"].eligibility["department"] == ["TRUST", "GRC"]
    assert by_role["PROD_ADMIN_ROLE"].eligibility["email"] == "spencer@example.com"
    assert by_role["ACCOUNTADMIN"].allowed_users == ("spencercsheehan",)
    assert by_role["SECURITYADMIN"].allowed_users == ("JUDGE_SERVICE", "TERRAFORM_SERVICE")


NAMED_POLICY = Policy(role="SECURITYADMIN", version="1.0", eligibility={}, allowed_users=("JUDGE_SERVICE",))


@pytest.mark.parametrize("username", ["JUDGE_SERVICE", "judge_service", " Judge_Service "])
def test_named_holder_passes_listed_user_case_insensitively(username):
    from engine.evaluator import evaluate_named_holder

    decision, _ = evaluate_named_holder(username, NAMED_POLICY)
    assert decision == DECISION_PASS


def test_named_holder_fails_unlisted_user():
    from engine.evaluator import evaluate_named_holder

    decision, reason = evaluate_named_holder("WINSTON", NAMED_POLICY)
    assert decision == DECISION_FAIL
    assert "user_actual=WINSTON" in reason


def test_named_holder_policy_skips_hr_lookup(monkeypatch):
    """Service accounts have no employee record — that must not become ERROR."""
    from engine import evaluator
    from sources.snowflake_client import RoleAssignment

    monkeypatch.setattr(
        evaluator,
        "get_role_assignments",
        lambda role, mode=None: [RoleAssignment("JUDGE_SERVICE", role), RoleAssignment("ROGUE", role)],
    )

    def hr_must_not_be_called(_):
        raise AssertionError("HR lookup called for a named-holder policy")

    monkeypatch.setattr(evaluator, "get_employee_by_snowflake_username", hr_must_not_be_called)

    by_user = {r.user: r.decision for r in evaluate_all(NAMED_POLICY)}
    assert by_user == {"JUDGE_SERVICE": DECISION_PASS, "ROGUE": DECISION_FAIL}


@pytest.mark.parametrize(
    "body",
    [
        "role: R\n",  # neither mode
        "role: R\neligibility: {department: Data}\nallowed_users: [A]\n",  # both modes
        "role: R\nallowed_users: []\n",  # empty allowlist
        "role: R\nallowed_users: A\n",  # not a list
    ],
)
def test_load_policy_rejects_invalid_decision_mode(tmp_path, body):
    from engine.evaluator import PolicyError

    path = tmp_path / "p.yaml"
    path.write_text(body)
    with pytest.raises(PolicyError):
        load_policy(path)


def test_load_policies_errors_on_empty_directory(tmp_path):
    from engine.evaluator import PolicyError, load_policies

    with pytest.raises(PolicyError):
        load_policies(tmp_path)


def test_evaluate_policies_end_to_end_sample_data(monkeypatch):
    from engine.evaluator import evaluate_policies, load_policies

    monkeypatch.setenv("JUDGE_MODE", "sample")
    results = evaluate_policies(load_policies())
    by_key = {(r.user, r.role): r.decision for r in results}

    assert by_key[("ALICE", "PROD_ANALYTICS_ROLE")] == DECISION_PASS
    assert by_key[("BOB", "PROD_ANALYTICS_ROLE")] == DECISION_FAIL
    assert by_key[("ANGELA", "PROD_ACCOUNTING_RO_ROLE")] == DECISION_PASS
    assert by_key[("BOB", "PROD_MARKETING_RO_ROLE")] == DECISION_PASS
    assert by_key[("JOSHUA", "PROD_TRUST_RO_ROLE")] == DECISION_PASS
    assert by_key[("SPENCER", "PROD_TRUST_RO_ROLE")] == DECISION_PASS
    assert by_key[("SPENCER", "PROD_ADMIN_ROLE")] == DECISION_PASS
    assert by_key[("WINSTON", "PROD_ADMIN_ROLE")] == DECISION_FAIL
    assert by_key[("spencercsheehan", "ACCOUNTADMIN")] == DECISION_PASS
    assert by_key[("JUDGE_SERVICE", "SECURITYADMIN")] == DECISION_PASS
    assert by_key[("TERRAFORM_SERVICE", "SECURITYADMIN")] == DECISION_PASS


def test_evaluate_policies_uses_one_timestamp_per_run(monkeypatch):
    from engine import evaluator
    from engine.evaluator import evaluate_policies, load_policies

    monkeypatch.setenv("JUDGE_MODE", "sample")
    stamps = iter(f"2026-01-01T00:00:{i:02d}+00:00" for i in range(60))
    monkeypatch.setattr(evaluator, "_now_iso", lambda: next(stamps))

    results = evaluate_policies(load_policies())

    assert len(results) > 1
    assert len({r.evaluated_at for r in results}) == 1
