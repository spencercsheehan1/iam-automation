# Demo data objects the least-privilege grants in privileges.tf apply to.
# Created as SYSADMIN (the conventional owner of databases/schemas/tables).

locals {
  schemas = toset(["FINANCE", "MARKETING", "ANALYTICS"])

  # One small demo table per schema. No data is loaded.
  tables = {
    "FINANCE.INVOICES" = {
      schema = "FINANCE"
      name   = "INVOICES"
      columns = [
        { name = "INVOICE_ID", type = "NUMBER(38,0)" },
        { name = "CUSTOMER_ID", type = "NUMBER(38,0)" },
        { name = "AMOUNT", type = "NUMBER(12,2)" },
        { name = "INVOICED_AT", type = "TIMESTAMP_NTZ(9)" },
      ]
    }
    "MARKETING.CAMPAIGNS" = {
      schema = "MARKETING"
      name   = "CAMPAIGNS"
      columns = [
        { name = "CAMPAIGN_ID", type = "NUMBER(38,0)" },
        { name = "NAME", type = "VARCHAR" },
        { name = "CHANNEL", type = "VARCHAR" },
        { name = "SPEND", type = "NUMBER(12,2)" },
      ]
    }
    "ANALYTICS.EVENTS" = {
      schema = "ANALYTICS"
      name   = "EVENTS"
      columns = [
        { name = "EVENT_ID", type = "NUMBER(38,0)" },
        { name = "USER_ID", type = "VARCHAR" },
        { name = "EVENT_TYPE", type = "VARCHAR" },
        { name = "OCCURRED_AT", type = "TIMESTAMP_NTZ(9)" },
      ]
    }
  }
}

resource "snowflake_database" "prod" {
  provider = snowflake.sysadmin

  name    = var.database_name
  comment = "Demo data for Judge role privileges. Managed by Terraform."
}

resource "snowflake_schema" "this" {
  provider = snowflake.sysadmin
  for_each = local.schemas

  database = snowflake_database.prod.name
  name     = each.key
}

resource "snowflake_table" "this" {
  provider = snowflake.sysadmin
  for_each = local.tables

  database = snowflake_database.prod.name
  schema   = snowflake_schema.this[each.value.schema].name
  name     = each.value.name

  dynamic "column" {
    for_each = each.value.columns
    content {
      name = column.value.name
      type = column.value.type
    }
  }
}
