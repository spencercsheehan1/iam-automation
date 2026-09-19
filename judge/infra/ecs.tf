resource "aws_ecs_cluster" "judge" {
  name = var.app_name
}

resource "aws_cloudwatch_log_group" "judge" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = 14
}

resource "aws_ecs_task_definition" "judge" {
  family                   = var.app_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.fargate_cpu
  memory                   = var.fargate_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = var.app_name
      image     = "${aws_ecr_repository.judge.repository_url}:${var.image_tag}"
      essential = true

      portMappings = [
        { containerPort = 8501, protocol = "tcp" }
      ]

      environment = [
        { name = "JUDGE_MODE", value = "live" },
        { name = "JUDGE_DB_BACKEND", value = "dynamodb" },
        { name = "JUDGE_DYNAMODB_TABLE", value = aws_dynamodb_table.evaluations.name },
        { name = "SNOWFLAKE_ACCOUNT", value = var.snowflake_account },
        { name = "SNOWFLAKE_USER", value = var.snowflake_user },
        { name = "SNOWFLAKE_WAREHOUSE", value = var.snowflake_warehouse },
        { name = "SNOWFLAKE_ROLE", value = var.snowflake_role },
        { name = "AWS_REGION", value = var.aws_region },
      ]

      # Secrets Manager values injected as env vars at container start —
      # the execution role (not the task role) needs GetSecretValue for
      # this, since the ECS agent itself resolves it before launch.
      secrets = [
        { name = "SNOWFLAKE_PRIVATE_KEY", valueFrom = aws_secretsmanager_secret.snowflake_private_key.arn }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.judge.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "judge"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "judge" {
  name            = var.app_name
  cluster         = aws_ecs_cluster.judge.id
  task_definition = aws_ecs_task_definition.judge.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.fargate_service.id]
    assign_public_ip = true # no NAT gateway — see vpc.tf
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.judge.arn
    container_name   = var.app_name
    container_port   = 8501
  }

  depends_on = [aws_lb_listener.judge_http]
}
