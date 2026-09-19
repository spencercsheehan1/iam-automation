#!/bin/bash
# Populate the real Snowflake private key into Secrets Manager.
#
# Deliberately NOT done via Terraform: passing the key through a
# Terraform resource would write it into the local state file in
# plaintext. This does it directly via the AWS API instead, so the key
# only ever exists in Secrets Manager (encrypted at rest) and your local
# .snowflake/ directory (gitignored, chmod 600).
set -euo pipefail

PROFILE="harvey-admin"
REGION="us-east-1"
KEY_PATH="$(dirname "$0")/../.snowflake/rsa_key.p8"

if [ ! -f "$KEY_PATH" ]; then
  echo "Error: $KEY_PATH not found." >&2
  exit 1
fi

SECRET_ARN=$(terraform -chdir="$(dirname "$0")" output -raw snowflake_private_key_secret_arn)

command aws secretsmanager put-secret-value \
  --profile "$PROFILE" \
  --region "$REGION" \
  --secret-id "$SECRET_ARN" \
  --secret-string "file://${KEY_PATH}"

echo "Done. Secret updated: $SECRET_ARN"
