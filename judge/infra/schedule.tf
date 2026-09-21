# Daily headless Judge run. EventBridge Scheduler starts a one-off Fargate
# task from the same task definition as the dashboard service, overriding
# the container command to `python run_evaluation.py` (see run_evaluation.py
# and the CMD note in the Dockerfile). The task exits non-zero on a crash or
# any FAIL/ERROR decision, which alerts.tf turns into an email.
resource "aws_scheduler_schedule" "judge_daily" {
  name                         = "${var.app_name}-daily"
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.judge.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      # Unversioned ARN = always the latest ACTIVE revision, so a new
      # `terraform apply` never leaves the schedule on a stale revision.
      task_definition_arn = aws_ecs_task_definition.judge.arn_without_revision
      launch_type         = "FARGATE"
      # alerts.tf matches this group to tell scheduled runs from the service's tasks.
      group = local.scheduled_task_group

      network_configuration {
        subnets          = data.aws_subnets.default.ids
        security_groups  = [aws_security_group.fargate_service.id]
        assign_public_ip = true # no NAT gateway — see vpc.tf
      }
    }

    input = jsonencode({
      containerOverrides = [
        { name = var.app_name, command = ["python", "run_evaluation.py"] }
      ]
    })

    retry_policy {
      maximum_retry_attempts = 0 # a missed day shows up as no new audit rows; don't double-run
    }
  }
}

locals {
  scheduled_task_group = "${var.app_name}-daily"
}

# --- Scheduler role: start the task and hand it the two ECS roles ---
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.app_name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler_permissions" {
  statement {
    sid       = "RunJudgeTask"
    actions   = ["ecs:RunTask"]
    resources = ["${aws_ecs_task_definition.judge.arn_without_revision}:*"]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.judge.arn]
    }
  }

  statement {
    sid       = "PassJudgeTaskRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ecs_execution.arn, aws_iam_role.ecs_task.arn]
  }
}

resource "aws_iam_role_policy" "scheduler_permissions" {
  name   = "${var.app_name}-scheduler-permissions"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_permissions.json
}
