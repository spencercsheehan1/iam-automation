# Audit-trail table. Single logical partition (pk="EVAL") since evaluation
# volume for this MVP is tiny (a handful of users, run on-demand or daily) —
# see db_dynamo.py for the access-pattern rationale.
resource "aws_dynamodb_table" "evaluations" {
  name         = "${var.app_name}-evaluations"
  billing_mode = "PAY_PER_REQUEST" # no capacity planning for near-zero traffic
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true # cheap insurance for an audit trail
  }
}
