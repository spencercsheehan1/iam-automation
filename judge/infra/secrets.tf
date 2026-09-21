# The Snowflake private key is the only genuinely sensitive value this
# app needs. It is deliberately NEVER passed through a Terraform
# variable or resource attribute — that would land it in the local
# state file in plaintext. Instead:
#   1. Terraform creates an empty secret (this resource).
#   2. You populate its real value out-of-band via `set_snowflake_key.sh`
#      (which calls `aws secretsmanager put-secret-value`; see infra/README.md).
#   3. `lifecycle.ignore_changes` tells Terraform to never touch the
#      value again, so `terraform apply` can't accidentally wipe it.
resource "aws_secretsmanager_secret" "snowflake_private_key" {
  name        = "${var.app_name}/snowflake-private-key"
  description = "PEM private key for the Judge Snowflake service account (JUDGE_SERVICE). Value set out-of-band, not via Terraform."
}

resource "aws_secretsmanager_secret_version" "snowflake_private_key_placeholder" {
  secret_id     = aws_secretsmanager_secret.snowflake_private_key.id
  secret_string = "REPLACE_ME_VIA_deploy.sh"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
