# Judge

A lightweight continuous access assurance prototype. Judge continuously
tests whether a sensitive Snowflake role still matches business policy,
instead of relying on quarterly, manually rubber-stamped access reviews.

See [`../judge-prd.md`](../judge-prd.md) for the full product spec.

## How it works

- **Jury** — the eligibility policy (`policies/prod_analytics_role.yaml`).
- **Judge** — the deterministic evaluation engine (`evaluator.py`) that
  compares each user's actual attributes and Snowflake access against
  the Jury's policy.
- **Bailiff** — the remediation surface. On `FAIL`, the dashboard flags
  the user with a recommended action ("Review and revoke access"). The
  MVP never auto-revokes.

Every evaluation produces one of three outcomes:

| Decision | Meaning |
|---|---|
| `PASS` | User satisfies the policy. |
| `FAIL` | User holds the role but does not satisfy the policy. |
| `ERROR` | Judge could not reach a decision — a data source (employee or Snowflake) was unavailable or broken. **Never reported as PASS.** |

Results are persisted to a local SQLite database (`judge.db`) as an
append-only audit trail: `evaluation_id`, `user`, `role`, `decision`,
`reason`, `policy_version`, `evaluated_at`.

## Setup

```bash
cd judge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run the dashboard

```bash
streamlit run app.py
```

Click **Run Evaluation**. With the bundled synthetic data you should see:

| User | Decision | Reason |
|---|---|---|
| alice@example.com | PASS | Satisfies policy (Data, active) |
| bob@example.com | FAIL | Wrong department (Marketing) |
| charlie@example.com | FAIL | Employee inactive (terminated) |

## Run the tests

```bash
pytest tests/
```

## Snowflake modes

Judge defaults to **sample mode** — no Snowflake account required. It
reads synthetic role-grant data from
`data/snowflake_roles_sample.csv`.

To point Judge at a real Snowflake trial account instead:

```bash
pip install snowflake-connector-python
export JUDGE_MODE=live
export SNOWFLAKE_ACCOUNT=...
export SNOWFLAKE_USER=...
export SNOWFLAKE_PASSWORD=...
export SNOWFLAKE_WAREHOUSE=...
export SNOWFLAKE_ROLE=...   # optional
streamlit run app.py
```

In live mode, Judge runs `SHOW GRANTS OF ROLE PROD_ANALYTICS_ROLE`
against the real account. Any connection or query failure surfaces as
`ERROR`, never silently falls back to sample data — a broken pipeline
must not look like a healthy control.

## Non-goals (MVP)

See `judge-prd.md` §16. Notably: no automatic revocation, no manager
certification workflow, no general-purpose policy engine, no Workday /
ConductorOne / Slack integrations, no LLM-driven access decisions.
