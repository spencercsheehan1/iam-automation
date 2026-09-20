# Least-privilege permissions per role. Data access is granted per schema:
#   read_schemas   -> USAGE + SELECT
#   write_schemas  -> USAGE + SELECT + INSERT/UPDATE/DELETE/TRUNCATE + CREATE TABLE
# `account_privileges` are account-level and carry no data access.
# Every role in judge/policies/ must appear here (enforced in roles.tf).

locals {
  role_access = {
    PROD_ACCOUNTING_RO_ROLE = {
      read_schemas       = ["FINANCE"]
      write_schemas      = []
      account_privileges = []
    }
    PROD_MARKETING_RO_ROLE = {
      read_schemas       = ["MARKETING"]
      write_schemas      = []
      account_privileges = []
    }
    PROD_TRUST_RO_ROLE = {
      read_schemas       = ["FINANCE", "MARKETING", "ANALYTICS"]
      write_schemas      = []
      account_privileges = []
    }
    PROD_ANALYTICS_ROLE = {
      read_schemas       = []
      write_schemas      = ["ANALYTICS"]
      account_privileges = []
    }
    # Administers identities; deliberately NOT granted MANAGE GRANTS or any data access.
    # (MONITOR USAGE is not listed: only ACCOUNTADMIN can grant it, and
    # SECURITYADMIN — which Terraform runs as — cannot.)
    PROD_ADMIN_ROLE = {
      read_schemas       = []
      write_schemas      = []
      account_privileges = ["CREATE USER", "CREATE ROLE"]
    }
  }

  # Roles that touch data at all (need database + warehouse USAGE).
  data_roles = toset([
    for role, cfg in local.role_access :
    role if length(cfg.read_schemas) + length(cfg.write_schemas) > 0
  ])

  # role|schema pairs, flattened for for_each.
  read_pairs = merge([
    for role, cfg in local.role_access : {
      for s in setunion(cfg.read_schemas, cfg.write_schemas) :
      "${role}|${s}" => { role = role, schema = s }
    }
  ]...)

  write_pairs = merge([
    for role, cfg in local.role_access : {
      for s in cfg.write_schemas :
      "${role}|${s}" => { role = role, schema = s }
    }
  ]...)

  admin_roles = {
    for role, cfg in local.role_access : role => cfg.account_privileges
    if length(cfg.account_privileges) > 0
  }
}

resource "snowflake_grant_privileges_to_account_role" "database_usage" {
  provider = snowflake.securityadmin
  for_each = local.data_roles

  account_role_name = snowflake_account_role.policy[each.key].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.prod.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "warehouse_usage" {
  provider = snowflake.securityadmin
  for_each = local.data_roles

  account_role_name = snowflake_account_role.policy[each.key].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = var.warehouse
  }
}

resource "snowflake_grant_privileges_to_account_role" "schema_usage" {
  provider = snowflake.securityadmin
  for_each = local.read_pairs

  account_role_name = snowflake_account_role.policy[each.value.role].name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = snowflake_schema.this[each.value.schema].fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "select_existing_tables" {
  provider   = snowflake.securityadmin
  for_each   = local.read_pairs
  depends_on = [snowflake_table.this]

  account_role_name = snowflake_account_role.policy[each.value.role].name
  privileges        = ["SELECT"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.this[each.value.schema].fully_qualified_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "select_future_tables" {
  provider = snowflake.securityadmin
  for_each = local.read_pairs

  account_role_name = snowflake_account_role.policy[each.value.role].name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.this[each.value.schema].fully_qualified_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "write_existing_tables" {
  provider   = snowflake.securityadmin
  for_each   = local.write_pairs
  depends_on = [snowflake_table.this]

  account_role_name = snowflake_account_role.policy[each.value.role].name
  privileges        = ["INSERT", "UPDATE", "DELETE", "TRUNCATE"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.this[each.value.schema].fully_qualified_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "write_future_tables" {
  provider = snowflake.securityadmin
  for_each = local.write_pairs

  account_role_name = snowflake_account_role.policy[each.value.role].name
  privileges        = ["INSERT", "UPDATE", "DELETE", "TRUNCATE"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.this[each.value.schema].fully_qualified_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "create_table" {
  provider = snowflake.securityadmin
  for_each = local.write_pairs

  account_role_name = snowflake_account_role.policy[each.value.role].name
  privileges        = ["CREATE TABLE"]
  on_schema {
    schema_name = snowflake_schema.this[each.value.schema].fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "account_level" {
  provider = snowflake.securityadmin
  for_each = local.admin_roles

  account_role_name = snowflake_account_role.policy[each.key].name
  privileges        = each.value
  on_account        = true
}
