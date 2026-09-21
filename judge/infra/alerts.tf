# Email alert for the daily run (schedule.tf). No code calls SNS: when the
# scheduled task stops with a non-zero exit (crash, or any FAIL/ERROR
# decision) or fails to start, ECS emits a "Task State Change" event, and
# this rule forwards a short message to an SNS email subscription.
resource "aws_sns_topic" "alerts" {
  name = "${var.app_name}-alerts"
}

# Email subscriptions stay "PendingConfirmation" until the recipient clicks
# the link in the AWS confirmation email; nothing is delivered before that.
resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_event_rule" "daily_run_failed" {
  name        = "${var.app_name}-daily-run-failed"
  description = "Scheduled Judge run stopped with a non-zero exit or failed to start"

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      clusterArn = [aws_ecs_cluster.judge.arn]
      group      = [local.scheduled_task_group]
      lastStatus = ["STOPPED"]
      "$or" = [
        { containers = { exitCode = [{ "anything-but" = 0 }] } },
        { stopCode = ["TaskFailedToStart"] },
      ]
    }
  })
}

resource "aws_cloudwatch_event_target" "daily_run_failed_email" {
  rule = aws_cloudwatch_event_rule.daily_run_failed.name
  arn  = aws_sns_topic.alerts.arn

  input_transformer {
    input_paths = {
      exit_code = "$.detail.containers[0].exitCode"
      reason    = "$.detail.stoppedReason"
      task      = "$.detail.taskArn"
      time      = "$.time"
    }
    input_template = <<-EOT
      "Judge daily evaluation needs attention (<time>). Exit code <exit_code> (1 = run crashed, 2 = at least one ERROR / data source broken, 3 = at least one FAIL / policy violation, 4 = zero users evaluated, empty exit code = task failed to start). Stop reason: <reason>. Task: <task>. Logs: CloudWatch log group ${aws_cloudwatch_log_group.judge.name}. Dashboard: https://${var.domain_name}"
    EOT
  }
}

data "aws_iam_policy_document" "alerts_topic" {
  statement {
    sid       = "AllowEventBridgeRule"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.daily_run_failed.arn]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts_topic.json
}
