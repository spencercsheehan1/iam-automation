variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Short name used to prefix/tag resources."
  type        = string
  default     = "judge"
}

variable "image_tag" {
  description = "Tag of the ECR image to deploy. Set by deploy.sh after each build/push."
  type        = string
  default     = "latest"
}

variable "fargate_cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU). Must be a valid Fargate cpu/memory pairing."
  type        = string
  default     = "256"
}

variable "fargate_memory" {
  description = "Fargate task memory in MB (512 = 0.5 GB). Must be a valid Fargate cpu/memory pairing."
  type        = string
  default     = "512"
}

variable "snowflake_account" {
  description = "Snowflake account identifier, e.g. orglocator-accountlocator. Not secret."
  type        = string
}

variable "snowflake_user" {
  description = "Snowflake service-account username Judge connects as. Not secret."
  type        = string
  default     = "JUDGE_SERVICE"
}

variable "snowflake_warehouse" {
  description = "Snowflake warehouse to run queries against. Not secret."
  type        = string
}

variable "snowflake_role" {
  description = "Snowflake role Judge assumes when connecting (needs visibility into role grants)."
  type        = string
  default     = "SECURITYADMIN"
}

variable "domain_name" {
  description = "Full hostname the app is served at, e.g. judge.spencer-sheehan.com."
  type        = string
  default     = "judge.spencer-sheehan.com"
}

variable "route53_zone_id" {
  description = "Hosted zone ID for the parent domain, in the account that owns the domain (not harvey-admin)."
  type        = string
  default     = "Z0984600KXJ4CXHKZJO5" # spencer-sheehan.com, account 844670296817 (profile "general")
}

variable "schedule_expression" {
  description = "When the daily headless evaluation runs (EventBridge Scheduler syntax)."
  type        = string
  default     = "cron(0 11 * * ? *)"
}

variable "schedule_timezone" {
  description = "IANA time zone for schedule_expression (handles daylight saving)."
  type        = string
  default     = "America/Los_Angeles"
}

variable "alert_email" {
  description = "Email address subscribed to the alerts SNS topic (must confirm the subscription once)."
  type        = string
  default     = "spencercsheehan@gmail.com"
}
