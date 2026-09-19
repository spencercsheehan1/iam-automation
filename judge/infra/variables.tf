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

variable "apprunner_cpu" {
  description = "App Runner vCPU allocation (e.g. \"0.25 vCPU\")."
  type        = string
  default     = "0.25 vCPU"
}

variable "apprunner_memory" {
  description = "App Runner memory allocation (e.g. \"0.5 GB\")."
  type        = string
  default     = "0.5 GB"
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
