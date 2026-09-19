#!/bin/bash
# Build, push, and deploy Judge to ECS Fargate.
#
# First-time setup: see infra/README.md for the two-phase apply and the
# manual Secrets Manager step (populating the real Snowflake private key).
#
# Subsequent runs: build a new image, push it, then force a new ECS
# deployment (unlike App Runner, ECS doesn't auto-redeploy on a new
# image push to the same tag).
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

echo "==> Done pushing. If this is the first deploy, run 'terraform apply' in infra/ now."

# Only force a redeploy if the ECS service already exists (skip on first-ever deploy,
# before `terraform apply` has created it).
if command aws ecs describe-services --profile "$PROFILE" --region "$REGION" \
     --cluster "$APP_NAME" --services "$APP_NAME" \
     --query 'services[0].status' --output text 2>/dev/null | grep -q ACTIVE; then
  echo "==> Forcing new ECS deployment"
  command aws ecs update-service --profile "$PROFILE" --region "$REGION" \
    --cluster "$APP_NAME" --service "$APP_NAME" --force-new-deployment >/dev/null
  echo "==> Deployment triggered. Watch with:"
  echo "    command aws ecs describe-services --profile $PROFILE --region $REGION --cluster $APP_NAME --services $APP_NAME --query 'services[0].deployments'"
fi
