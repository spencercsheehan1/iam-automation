output "service_url" {
  description = "Public HTTPS URL for the Judge dashboard."
  value       = "https://${aws_apprunner_service.judge.service_url}"
}

output "service_arn" {
  description = "App Runner service ARN, for manual `aws apprunner start-deployment` calls."
  value       = aws_apprunner_service.judge.arn
}

output "ecr_repository_url" {
  description = "ECR repository to push new images to."
  value       = aws_ecr_repository.judge.repository_url
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.evaluations.name
}

output "snowflake_private_key_secret_arn" {
  description = "Secrets Manager ARN to populate with the real private key (see infra/README.md)."
  value       = aws_secretsmanager_secret.snowflake_private_key.arn
}
