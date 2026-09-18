"""One-off CLI check for JUDGE_MODE=live.

Run this after exporting SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE, and
JUDGE_MODE=live in your shell. Prints results to stdout; does not touch
judge.db (use the Streamlit app for the persisted/audited run).
"""

from evaluator import evaluate_all, load_policy

if __name__ == "__main__":
    policy = load_policy()
    results = evaluate_all(policy)
    print(f"{'USER':15s} {'DECISION':8s} REASON")
    print("-" * 70)
    for r in results:
        print(f"{r.user:15s} {r.decision:8s} {r.reason}")
