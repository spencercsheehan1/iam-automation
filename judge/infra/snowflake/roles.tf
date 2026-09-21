# One Snowflake role per policy file in judge/policies/ — the file's
# `role:` value is the role name, so adding a policy file adds the role.
# Policies for Snowflake's built-in roles (local.builtin_roles) are skipped.

locals {
  policies_dir = "${path.module}/../../policies"

  # Snowflake's system roles already exist and can't be created or owned
  # here. Judge still evaluates their policies; Terraform skips them.
  builtin_roles = toset(["ACCOUNTADMIN", "ORGADMIN", "PUBLIC", "SECURITYADMIN", "SYSADMIN", "USERADMIN"])

  policy_roles = toset([
    for f in fileset(local.policies_dir, "*.yaml") :
    yamldecode(file("${local.policies_dir}/${f}")).role
    if !contains(local.builtin_roles, yamldecode(file("${local.policies_dir}/${f}")).role)
  ])
}

resource "snowflake_account_role" "policy" {
  provider = snowflake.securityadmin
  for_each = local.policy_roles

  name    = each.key
  comment = "Managed by Terraform. Eligibility policy: judge/policies/."

  lifecycle {
    precondition {
      condition     = contains(keys(local.role_access), each.key)
      error_message = "Policy role ${each.key} has no entry in local.role_access (privileges.tf). Add one so the role gets explicit, least-privilege permissions."
    }
  }
}

# PROD_ANALYTICS_ROLE was created by hand before Terraform managed roles.
# Adopt it rather than fail on "already exists". (It also holds the
# ACCOUNTADMIN role today — the bootstrap SQL in README.md revokes that.)
import {
  to = snowflake_account_role.policy["PROD_ANALYTICS_ROLE"]
  id = "\"PROD_ANALYTICS_ROLE\""
}
