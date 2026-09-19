# NOTE on deploy order: this resource references an image tag in the ECR
# repo above. The repo must exist AND already have that tag pushed before
# this resource can be created. deploy.sh handles the sequencing:
#   1. terraform apply -target=aws_ecr_repository.judge   (repo only)
#   2. build & push the image
#   3. terraform apply                                    (everything else)
resource "aws_apprunner_service" "judge" {
  service_name = var.app_name

  source_configuration {
    auto_deployments_enabled = true # new push to `image_tag` redeploys automatically

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.judge.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8501"

        runtime_environment_variables = {
          JUDGE_MODE           = "live"
          JUDGE_DB_BACKEND     = "dynamodb"
          JUDGE_DYNAMODB_TABLE = aws_dynamodb_table.evaluations.name
          SNOWFLAKE_ACCOUNT    = var.snowflake_account
          SNOWFLAKE_USER       = var.snowflake_user
          SNOWFLAKE_WAREHOUSE  = var.snowflake_warehouse
          SNOWFLAKE_ROLE       = var.snowflake_role
        }

        runtime_environment_secrets = {
          SNOWFLAKE_PRIVATE_KEY = aws_secretsmanager_secret.snowflake_private_key.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.apprunner_cpu
    memory            = var.apprunner_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/_stcore/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 3
  }

  depends_on = [
    aws_iam_role_policy_attachment.apprunner_ecr_access,
    aws_iam_role_policy.apprunner_instance_permissions,
    aws_secretsmanager_secret_version.snowflake_private_key_placeholder,
  ]
}
