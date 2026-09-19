#!/bin/bash
# Build, push, and deploy Judge to App Runner.
#
# First-time setup: see infra/README.md for the two-phase apply and the
# manual Secrets Manager step (populating the real Snowflake private key).
#
# Subsequent runs of this script just build a new image, push it, and
# App Runner's auto_deployments picks it up automatically.
set -euo pipefail

cd "$(dirname "$0")/.."  # repo-relative: judge/

PROFILE="harvey-admin"
REGION="us-east-1"
APP_NAME="judge"

ACCOUNT_ID=$(command aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)
ECR_URL="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

echo "==> Logging in to ECR ($ECR_URL)"
command aws ecr get-login-password --profile "$PROFILE" --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "==> Building image"
docker build --platform linux/amd64 -t "${APP_NAME}:latest" .

echo "==> Tagging and pushing"
docker tag "${APP_NAME}:latest" "${ECR_URL}:latest"
docker push "${ECR_URL}:latest"

echo "==> Done. If this is the first deploy, run 'terraform apply' in infra/ now."
echo "    Otherwise, App Runner's auto_deployments will pick this up within ~a minute."
