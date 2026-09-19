# Two aliased providers, one identity (TERRAFORM_SERVICE), two Snowflake
# roles — following Snowflake's separation of duties:
#   sysadmin       creates databases / schemas / tables
#   securityadmin  creates roles and manages every grant
# SECURITYADMIN holds MANAGE GRANTS, so it can grant privileges on the
# SYSADMIN-owned objects below. See README.md for the one-time bootstrap
# that creates TERRAFORM_SERVICE and grants it both roles.

provider "snowflake" {
  alias = "sysadmin"

  organization_name = var.snowflake_organization_name
  account_name      = var.snowflake_account_name
  user              = var.snowflake_user
  authenticator     = "SNOWFLAKE_JWT"
  private_key       = file(var.private_key_path)
  role              = "SYSADMIN"

  # snowflake_table is still a preview resource in the provider.
  preview_features_enabled = ["snowflake_table_resource"]
}

provider "snowflake" {
  alias = "securityadmin"

  organization_name = var.snowflake_organization_name
  account_name      = var.snowflake_account_name
  user              = var.snowflake_user
  authenticator     = "SNOWFLAKE_JWT"
  private_key       = file(var.private_key_path)
  role              = "SECURITYADMIN"

  preview_features_enabled = ["snowflake_table_resource"]
}
