"""Judge — continuous access assurance prototype.

Streamlit dashboard: manual "Run Evaluation" trigger, results table,
compliance metrics, and audit history. See judge-prd.md for the full
spec and terminology (Jury = policy, Judge = evaluation engine,
Bailiff = remediation workflow).
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

import db
from evaluator import DECISION_ERROR, DECISION_FAIL, DECISION_PASS, PolicyError, evaluate_all, load_policy

st.set_page_config(page_title="Judge", page_icon="⚖️", layout="wide")

st.title("⚖️ Judge")
st.caption("Continuous access assurance — does this user still satisfy the policy for this access?")

mode = os.environ.get("JUDGE_MODE", "sample")
st.sidebar.markdown("### Configuration")
st.sidebar.write(f"**Snowflake mode:** `{mode}`")
if mode == "sample":
    st.sidebar.info(
        "Running against synthetic sample data (no Snowflake account "
        "connected yet). Set `JUDGE_MODE=live` with Snowflake credentials "
        "to query a real trial account."
    )

try:
    policy = load_policy()
    st.sidebar.markdown("### Jury (policy)")
    st.sidebar.write(f"**Role:** `{policy.role}`")
    st.sidebar.write(f"**Policy version:** `{policy.version}`")
    st.sidebar.json(policy.eligibility)
except PolicyError as exc:
    st.error(f"Could not load policy: {exc}")
    st.stop()

if st.button("▶ Run Evaluation", type="primary"):
    with st.spinner("Judge is evaluating..."):
        results = evaluate_all(policy)
        db.save_results(results)
    st.success(f"Evaluation complete — {len(results)} user(s) evaluated.")

latest = db.load_latest_run()

st.header("Latest Evaluation")
if not latest:
    st.info("No evaluations yet. Click **Run Evaluation** to get started.")
else:
    df = pd.DataFrame(latest)[["user", "role", "decision", "reason", "evaluated_at"]]
    df.columns = ["User", "Snowflake Role", "Decision", "Reason", "Evaluated"]

    def _highlight(row: pd.Series) -> list[str]:
        color = {
            DECISION_PASS: "background-color: #d4edda",
            DECISION_FAIL: "background-color: #f8d7da",
            DECISION_ERROR: "background-color: #fff3cd",
        }.get(row["Decision"], "")
        return [color] * len(row)

    st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True, hide_index=True)

    total = len(latest)
    passed = sum(1 for r in latest if r["decision"] == DECISION_PASS)
    failed = sum(1 for r in latest if r["decision"] == DECISION_FAIL)
    errored = sum(1 for r in latest if r["decision"] == DECISION_ERROR)
    compliance_rate = f"{(passed / total * 100):.0f}%" if total else "N/A"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Users evaluated", total)
    c2.metric("Passed", passed)
    c3.metric("Failed", failed)
    c4.metric("Errors", errored)
    c5.metric("Compliance rate", compliance_rate)

    failing = [r for r in latest if r["decision"] == DECISION_FAIL]
    if failing:
        st.subheader("🛎️ Bailiff — Recommended Actions")
        for r in failing:
            st.warning(
                f"**{r['user']}** — Recommended action: Review and revoke `{r['role']}`. "
                f"Reason: {r['reason']}"
            )

    erroring = [r for r in latest if r["decision"] == DECISION_ERROR]
    if erroring:
        st.subheader("⚠️ Data Source Errors")
        for r in erroring:
            st.error(f"**{r['user']}** — {r['reason']}")

st.header("Audit History")
all_results = db.load_all_results()
if all_results:
    hist_df = pd.DataFrame(all_results)[
        ["evaluation_id", "user", "role", "decision", "reason", "policy_version", "evaluated_at"]
    ]
    hist_df.columns = ["Evaluation ID", "User", "Role", "Decision", "Reason", "Policy Version", "Evaluated"]
    st.dataframe(hist_df, use_container_width=True, hide_index=True)
else:
    st.caption("No history yet.")

st.divider()
st.caption(
    "Architecture note: this manual trigger stands in for a scheduled job "
    "(e.g. GitHub Actions, Airflow, or Azure Functions) that would run "
    "Judge automatically, such as daily."
)
