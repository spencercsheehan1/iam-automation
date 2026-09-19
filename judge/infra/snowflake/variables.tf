variable "snowflake_organization_name" {
  description = "Snowflake organization name (the part before the dash in the account identifier). Not secret."
  type        = string
  default     = "yiooglh"
}

variable "snowflake_account_name" {
  description = "Snowflake account name (the part after the dash in the account identifier). Not secret."
  type        = string
  default     = "ox90063"
}

variable "snowflake_user" {
  description = "Snowflake user Terraform authenticates as. Created once by the bootstrap SQL in README.md."
  type        = string
  default     = "TERRAFORM_SERVICE"
}

variable "private_key_path" {
  description = "Path to TERRAFORM_SERVICE's PKCS8 PEM private key (local, gitignored)."
  type        = string
  default     = "../../.snowflake/terraform_rsa_key.p8"
}

variable "warehouse" {
  description = "Existing warehouse the roles are granted USAGE on so they can run queries. Referenced, not managed."
  type        = string
  default     = "SNOWFLAKE_LEARNING_WH"
}

variable "database_name" {
  description = "Demo database Terraform creates to hang the least-privilege grants on."
  type        = string
  default     = "PROD_DATA"
}
