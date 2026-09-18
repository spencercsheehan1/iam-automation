# Judge — MVP Product Requirements Document

## 1. Product Summary

**Judge** is a lightweight continuous access assurance prototype.

It evaluates whether users who currently hold a sensitive Snowflake role still meet the business policy for having that access.

The prototype demonstrates an alternative to traditional quarterly User Access Reviews, where managers manually review and often rubber-stamp access.

Instead of asking:

> “Does this manager approve this access once per quarter?”

Judge asks:

> “Does this user currently satisfy the defined policy for this access?”

The system runs the evaluation automatically and produces an auditable pass/fail result.

---

## 2. Problem

Traditional User Access Reviews are:

- time-consuming
- dependent on human judgment
- frequently rubber-stamped
- point-in-time rather than continuous
- often better at proving a review occurred than proving access is appropriate

The prototype should demonstrate that some access decisions can instead be evaluated continuously against explicit business rules.

---

## 3. MVP Scope

Keep the MVP intentionally narrow.

Judge will evaluate:

**One Snowflake role**  
against  
**One eligibility policy**  
for  
**A small set of sample users**

Example role:

`PROD_ANALYTICS_ROLE`

Example policy:

A user is eligible for `PROD_ANALYTICS_ROLE` only when:

```text
employment_status = active
AND department = Data
```

The exact names can be changed, but there should only be **one role and one policy** in the MVP.

---

## 4. Primary Demo Scenario

Create at least three synthetic users:

### Alice — PASS

```text
Name: Alice
Department: Data
Employment status: Active
Snowflake role: PROD_ANALYTICS_ROLE
```

Expected result:

```text
PASS
Reason: User satisfies all eligibility requirements.
```

### Bob — FAIL

```text
Name: Bob
Department: Marketing
Employment status: Active
Snowflake role: PROD_ANALYTICS_ROLE
```

Expected result:

```text
FAIL
Reason: Department does not satisfy policy.
```

### Charlie — FAIL

```text
Name: Charlie
Department: Data
Employment status: Terminated
Snowflake role: PROD_ANALYTICS_ROLE
```

Expected result:

```text
FAIL
Reason: Employment status does not satisfy policy.
```

---

# 5. System Inputs

Judge needs two types of information.

## A. Employee / organizational data

For the MVP, this can be synthetic data.

Minimum fields:

```text
employee_id
name
email
department
employment_status
```

This represents data that would normally come from an authoritative HR system such as Workday.

Do **not** build a Workday integration.

---

## B. Snowflake role assignments

Judge needs to know:

```text
user
assigned_role
```

Ideally, retrieve the real role assignment from the Snowflake trial environment.

If real Snowflake integration becomes difficult, sample data may be used temporarily, but the preferred demo has at least one real Snowflake query.

---

# 6. Policy

Store the policy in a simple configuration file.

Example:

```yaml
role: PROD_ANALYTICS_ROLE

eligibility:
  employment_status: active
  department: Data
```

Do not build a general-purpose policy engine.

The application only needs to support this one policy for the prototype.

---

# 7. Evaluation Logic

For every user currently holding `PROD_ANALYTICS_ROLE`:

1. Retrieve employee attributes.
2. Retrieve current Snowflake role assignment.
3. Load the eligibility policy.
4. Compare the user's attributes against the policy.
5. Produce either:
   - `PASS`
   - `FAIL`
6. Record why the decision was made.
7. Store the evaluation result.

Example:

```json
{
  "user": "bob@example.com",
  "role": "PROD_ANALYTICS_ROLE",
  "decision": "FAIL",
  "reason": "department_expected=Data, department_actual=Marketing",
  "evaluated_at": "2026-09-17T12:00:00Z"
}
```

The decision must be **deterministic**.

Do not use an LLM to decide whether someone should have access.

---

# 8. Judge / Jury / Bailiff Terminology

The prototype may use the following names in the UI:

### Jury
The eligibility policy.

Example:

> Active employee in the Data department.

### Judge
The evaluation engine.

Judge compares actual user attributes and Snowflake access against the Jury's policy.

### Bailiff
The remediation workflow.

For the MVP, the Bailiff should **not automatically revoke access**.

Instead:

```text
FAIL → flag for remediation
```

The UI may display:

> Recommended action: Review and revoke access.

Automatic revocation is a future enhancement.

---

# 9. Output / Dashboard

Build a simple dashboard showing:

| User | Snowflake Role | Decision | Reason | Evaluated |
|---|---|---|---|---|
| Alice | PROD_ANALYTICS_ROLE | PASS | Policy satisfied | timestamp |
| Bob | PROD_ANALYTICS_ROLE | FAIL | Wrong department | timestamp |
| Charlie | PROD_ANALYTICS_ROLE | FAIL | Employee inactive | timestamp |

Also show basic metrics:

```text
Users evaluated: 3
Passed: 1
Failed: 2
Compliance rate: 33%
```

The UI should prioritize clarity over appearance.

A simple Streamlit application is sufficient.

---

# 10. Audit Evidence

Each evaluation should preserve enough information to explain the decision later.

Store:

```text
evaluation_id
user
role
decision
reason
policy_version
evaluated_at
```

Optional:

```text
employee_attributes_used
```

The important principle is:

> An auditor should be able to understand what policy was tested, what data was evaluated, and why Judge reached its conclusion.

---

# 11. Continuous Operation

For the prototype, include a manual **Run Evaluation** button.

Architecture should assume the evaluation would eventually run automatically, such as:

```text
daily scheduled job
```

Do not build a full scheduler unless trivial.

The demo should explain that production could run through GitHub Actions, Airflow, Azure Functions, or another scheduler.

---

# 12. Failure Handling

The system must distinguish:

```text
PASS
FAIL
ERROR
```

Do not treat missing data as PASS.

Examples:

Employee record unavailable:

```text
ERROR
Unable to evaluate employee attributes.
```

Snowflake query fails:

```text
ERROR
Unable to retrieve current access state.
```

This is important because a broken monitoring pipeline must not appear as a healthy control.

---

# 13. Suggested Technical Stack

Prefer simplicity.

```text
Python
Snowflake
YAML policy file
SQLite or simple local persistence
Streamlit
```

Optional:

```text
GitHub Actions
```

Do not add infrastructure unless required for the demo.

---

# 14. Suggested Repository Structure

```text
judge/
│
├── app.py
├── evaluator.py
├── snowflake_client.py
├── employee_data.py
│
├── policies/
│   └── prod_analytics_role.yaml
│
├── data/
│   └── employees.csv
│
├── tests/
│   └── test_evaluator.py
│
├── requirements.txt
└── README.md
```

Keep modules small.

---

# 15. Acceptance Criteria

The MVP is complete when all of the following are true:

1. A Snowflake role exists for the demo.
2. Multiple sample users exist.
3. Employee attributes exist for those users.
4. One eligibility policy exists.
5. Judge evaluates each user deterministically.
6. Eligible users return `PASS`.
7. Ineligible users return `FAIL`.
8. Missing or broken source data returns `ERROR`, not `PASS`.
9. The reason for every decision is visible.
10. Results are displayed in a simple dashboard.
11. Previous evaluation results can be inspected.
12. At least basic unit tests validate the policy evaluation logic.

---

# 16. Explicit Non-Goals

Do **not** implement any of the following in the MVP:

- full User Access Review workflow
- manager certifications
- access request UI
- full Snowflake role inheritance resolution
- arbitrary policy creation
- Terraform parsing
- Workday integration
- ConductorOne integration
- Slack integration
- automatic access revocation
- multiple systems
- multiple control frameworks
- advanced RBAC modeling
- machine-learning access recommendations
- production authentication
- enterprise-scale deployment

These may be discussed as future enhancements.

---

# 17. Optional AI Enhancement

Only implement this if the core MVP is finished.

An LLM may convert structured Judge results into a human-readable explanation.

Input:

```json
{
  "user": "Bob",
  "role": "PROD_ANALYTICS_ROLE",
  "decision": "FAIL",
  "expected_department": "Data",
  "actual_department": "Marketing"
}
```

Output:

> Bob currently holds PROD_ANALYTICS_ROLE but is assigned to the Marketing organization. The policy restricts this role to active members of the Data organization. Review whether this access should be revoked.

The LLM must **not make the PASS/FAIL decision**.

The deterministic rules engine remains authoritative.

---

# 18. Future Direction

If another week of development were available:

1. ingest real HR data
2. support more Snowflake roles
3. support richer eligibility policies
4. integrate with Terraform / IAM systems as policy sources
5. send remediation alerts to Slack
6. add approval-based remediation
7. optionally auto-revoke high-confidence violations
8. track policy and access drift over time
9. map policies to SOC 2 / ISO 27001 controls
10. add monitoring for whether Judge itself is functioning correctly

---

## One-sentence product thesis

> **Judge continuously tests whether sensitive access still matches business policy, turning access assurance from a quarterly human review into an ongoing control.**

---

> **Build only the MVP described here. Prefer the simplest working implementation. Do not implement anything listed under Non-Goals unless explicitly asked. Before writing code, propose a short implementation plan and identify any assumptions that materially affect the architecture.**
