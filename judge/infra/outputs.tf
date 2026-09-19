output "service_url" {
  description = "Public HTTPS URL for the Judge dashboard."
  value       = "https://${var.domain_name}"
}

output "alb_dns_name" {
  description = "Raw ALB DNS name (redirects to service_url over HTTPS)."
  value       = aws_lb.judge.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.judge.name
}

output "ecs_service_name" {
  value = aws_ecs_service.judge.name
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
