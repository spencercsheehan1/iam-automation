# --- Access role: lets the App Runner control plane pull the image from ECR ---
data "aws_iam_policy_document" "apprunner_assume_ecr" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_ecr_access" {
  name               = "${var.app_name}-apprunner-ecr-access"
  assume_role_policy = data.aws_iam_policy_document.apprunner_assume_ecr.json
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_access" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# --- Instance role: what the running container is allowed to call ---
data "aws_iam_policy_document" "apprunner_assume_instance" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_instance" {
  name               = "${var.app_name}-apprunner-instance"
  assume_role_policy = data.aws_iam_policy_document.apprunner_assume_instance.json
}

data "aws_iam_policy_document" "apprunner_instance_permissions" {
  statement {
    sid = "DynamoDBAuditTrail"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:BatchWriteItem",
    ]
    resources = [aws_dynamodb_table.evaluations.arn]
  }

  statement {
    sid       = "ReadSnowflakePrivateKey"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.snowflake_private_key.arn]
  }
}

resource "aws_iam_role_policy" "apprunner_instance_permissions" {
  name   = "${var.app_name}-apprunner-instance-permissions"
  role   = aws_iam_role.apprunner_instance.id
  policy = data.aws_iam_policy_document.apprunner_instance_permissions.json
}
