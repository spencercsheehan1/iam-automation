"""Headless Judge run, for the daily EventBridge Scheduler job.

Same work as the dashboard's "Run Evaluation" button: evaluate every
policy and append the results to the audit trail. The exit code is the
alert signal — a non-zero exit makes the ECS task stop with a failure,
which an EventBridge rule forwards to the SNS email topic (see
infra/alerts.tf). An uncaught exception also exits non-zero.
"""

from __future__ import annotations

import sys

import storage
from engine.evaluator import DECISION_ERROR, DECISION_FAIL, EvaluationResult, evaluate_policies, load_policies


# Exit codes, shown in the alert email. 1 is left to Python itself: an
# uncaught exception (the run crashed) exits 1.
EXIT_OK = 0
EXIT_ERROR = 2        # at least one ERROR: a data source was broken, pipeline needs fixing
EXIT_FAIL = 3         # at least one FAIL (and no ERROR): someone holds access they shouldn't
EXIT_NO_RESULTS = 4   # nobody evaluated at all: an empty grant list can hide a broken pipeline


def exit_code_for(results: list[EvaluationResult]) -> int:
    """Return the process exit code for a finished run; anything non-zero emails an alert."""
    if not results:
        return EXIT_NO_RESULTS
    decisions = {r.decision for r in results}
    if DECISION_ERROR in decisions:  # ERROR outranks FAIL: a broken check can hide other FAILs
        return EXIT_ERROR
    if DECISION_FAIL in decisions:
        return EXIT_FAIL
    return EXIT_OK


def main() -> int:
    results = evaluate_policies(load_policies())
    storage.save_results(results)

    for r in results:
        print(f"{r.decision:5} {r.role} {r.user}: {r.reason}")
    print(f"Judge daily run: {len(results)} result(s) saved.")
    return exit_code_for(results)


if __name__ == "__main__":
    sys.exit(main())
