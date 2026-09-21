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

import storage
from engine.evaluator import DECISION_ERROR, DECISION_FAIL, DECISION_PASS, PolicyError, evaluate_policies, load_policies
from run_evaluation import EXIT_OK, exit_code_for

ALERT_MEANINGS = {2: "at least one ERROR", 3: "at least one FAIL", 4: "zero users evaluated"}


def _email_alert(results) -> None:
    """Email the judge-alerts SNS topic when a manual run doesn't pass (same rule as the daily run)."""
    topic_arn = os.environ.get("JUDGE_ALERTS_TOPIC_ARN")
    code = exit_code_for(results)
    if not topic_arn or code == EXIT_OK:
        return
    import boto3

    lines = [f"{r.decision} {r.role} {r.user}: {r.reason}" for r in results if r.decision != DECISION_PASS]
    boto3.client("sns", region_name=os.environ.get("AWS_REGION")).publish(
        TopicArn=topic_arn,
        Subject=f"Judge manual evaluation: {ALERT_MEANINGS[code]}",
        Message=f"Manual dashboard run, exit code {code} ({ALERT_MEANINGS[code]}).\n\n"
        + "\n".join(lines)
        + "\n\nDashboard: https://judge.spencer-sheehan.com",
    )

st.set_page_config(page_title="Judge", page_icon="⚖️", layout="wide")

st.title("⚖️ Judge")
st.caption("Continuous access assurance — do all Snowflake users still satisfy our current access policies?")

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
    policies = load_policies()
    st.sidebar.markdown("### Jury (policies)")
    for policy in policies:
        with st.sidebar.expander(f"`{policy.role}` (v{policy.version})"):
            st.json({"allowed_users": list(policy.allowed_users)} if policy.allowed_users else policy.eligibility)
except PolicyError as exc:
    st.error(f"Could not load policy: {exc}")
    st.stop()

if "show_results" not in st.session_state:
    # Hidden by default, even if past runs are sitting in the audit
    # trail — a fresh page load should look like the tool hasn't run
    # yet, so an audience can tell "just started" apart from "just ran".
    st.session_state.show_results = False

run_col, clear_col = st.columns([1, 1])
with run_col:
    run_clicked = st.button("▶ Run Evaluation", type="primary")
with clear_col:
    clear_clicked = st.button("🗑️ Clear")

if run_clicked:
    with st.spinner("Judge is evaluating..."):
        results = evaluate_policies(policies)
        storage.save_results(results)
    try:
        _email_alert(results)
    except Exception as exc:  # an email failure must not hide the results
        st.warning(f"Evaluation saved, but the alert email could not be sent: {exc}")
    st.session_state.show_results = True
    st.success(f"Evaluation complete — {len(results)} user(s) evaluated.")

if clear_clicked:
    st.session_state.show_results = False

st.header("Latest Evaluation")
if not st.session_state.show_results:
    st.info("No evaluation shown. Click **Run Evaluation** to get started.")
else:
    # Group by person: sort by user (then role), case-insensitively. The
    # Bailiff and error lists below are built from this, so they follow suit.
    latest = sorted(storage.load_latest_run(), key=lambda r: (r["user"].lower(), r["role"].lower()))
    df = pd.DataFrame(latest)[["user", "role", "decision", "reason", "evaluated_at"]]
    df.columns = ["User", "Snowflake Role", "Decision", "Reason", "Evaluated"]

    def _highlight(row: pd.Series) -> list[str]:
        color = {
            # Deep tints + explicit white text: readable in light and dark themes.
            DECISION_PASS: "background-color: #2e6b3f; color: #ffffff",
            DECISION_FAIL: "background-color: #8b2e3a; color: #ffffff",
            DECISION_ERROR: "background-color: #7a5c12; color: #ffffff",
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
all_results = storage.load_all_results()
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
    "Judge also runs automatically once a day (EventBridge Scheduler, 11:00 AM "
    "Pacific). Both the daily run and this button email an alert on any FAIL or ERROR."
)
