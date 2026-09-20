# Legitimate user -> role grants. Users must already exist in Snowflake
# (they are not managed here).
#
# Deliberately NOT listed: the "rogue" grants used to demo Judge (e.g.
# WINSTON -> PROD_ADMIN_ROLE). Make those by hand in the Snowflake UI —
# Terraform doesn't track or revert grants it doesn't manage, and Judge
# reads live grants, so it flags them on the next run.

locals {
  user_role_grants = {
    ALICE   = ["PROD_ANALYTICS_ROLE"]
    ANGELA  = ["PROD_ACCOUNTING_RO_ROLE"]
    BOB     = ["PROD_MARKETING_RO_ROLE"]
    JOSHUA  = ["PROD_TRUST_RO_ROLE"]
    SPENCER = ["PROD_TRUST_RO_ROLE", "PROD_ADMIN_ROLE"]
  }

  user_role_pairs = merge([
    for user, roles in local.user_role_grants : {
      for role in roles : "${user}|${role}" => { user = user, role = role }
    }
  ]...)
}

resource "snowflake_grant_account_role" "user" {
  provider = snowflake.securityadmin
  for_each = local.user_role_pairs

  role_name = snowflake_account_role.policy[each.value.role].name
  user_name = each.value.user
}
