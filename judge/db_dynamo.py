"""DynamoDB persistence for evaluation results (the audit trail).

The audit-trail backend — a container's local disk doesn't survive
restarts/redeploys and isn't shared across instances, so results live in a
managed table. db.py re-exports these functions for app.py.

Table layout (single logical partition — evaluation volume here is tiny,
so a GSI/sharding scheme would be over-engineering for this MVP):

    pk = "EVAL"                              (constant partition key)
    sk = "<evaluated_at>#<evaluation_id>"    (sort key)

Sorting by sk gives chronological order for free (ISO 8601 timestamps
sort lexicographically), so "all results, most recent first" and "just
the latest run" are both plain Query calls with ScanIndexForward=False —
no application-side sorting needed.
"""

from __future__ import annotations

import json
import os
import uuid

from evaluator import EvaluationResult

PARTITION_KEY_VALUE = "EVAL"


def _table_name() -> str:
    return os.environ.get("JUDGE_DYNAMODB_TABLE", "judge-evaluations")


def _get_table():
    import boto3

    resource = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION"))
    return resource.Table(_table_name())


def save_results(results: list[EvaluationResult]) -> None:
    table = _get_table()
    with table.batch_writer() as batch:
        for r in results:
            evaluation_id = str(uuid.uuid4())
            batch.put_item(
                Item={
                    "pk": PARTITION_KEY_VALUE,
                    "sk": f"{r.evaluated_at}#{evaluation_id}",
                    "evaluation_id": evaluation_id,
                    "user": r.user,
                    "role": r.role,
                    "decision": r.decision,
                    "reason": r.reason,
                    "policy_version": r.policy_version,
                    "evaluated_at": r.evaluated_at,
                    "employee_attributes_used": (
                        json.dumps(r.employee_attributes_used) if r.employee_attributes_used else None
                    ),
                }
            )


def _item_to_dict(item: dict) -> dict:
    return {
        "evaluation_id": item.get("evaluation_id"),
        "user": item.get("user"),
        "role": item.get("role"),
        "decision": item.get("decision"),
        "reason": item.get("reason"),
        "policy_version": item.get("policy_version"),
        "evaluated_at": item.get("evaluated_at"),
        "employee_attributes_used": item.get("employee_attributes_used"),
    }


def load_all_results() -> list[dict]:
    """Return every stored evaluation, most recent first."""
    table = _get_table()
    items: list[dict] = []
    query_kwargs = {
        "KeyConditionExpression": "pk = :pk",
        "ExpressionAttributeValues": {":pk": PARTITION_KEY_VALUE},
        "ScanIndexForward": False,  # descending by sk => most recent evaluated_at first
    }
    while True:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    return [_item_to_dict(item) for item in items]


def load_latest_run() -> list[dict]:
    """Return only the rows from the most recent evaluation timestamp."""
    table = _get_table()
    response = table.query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": PARTITION_KEY_VALUE},
        ScanIndexForward=False,
        Limit=1,
    )
    latest_items = response.get("Items", [])
    if not latest_items:
        return []

    latest_ts = latest_items[0]["evaluated_at"]
    response = table.query(
        KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
        ExpressionAttributeValues={":pk": PARTITION_KEY_VALUE, ":prefix": f"{latest_ts}#"},
        ScanIndexForward=False,
    )
    return [_item_to_dict(item) for item in response.get("Items", [])]
