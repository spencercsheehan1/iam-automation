# Judge — production infrastructure

Runs Judge as an always-on container on **AWS App Runner**, backed by
**DynamoDB** for the audit trail and **Secrets Manager** for the
Snowflake private key. All resources live in AWS account `280655609003`
(`harvey-admin` profile), region `us-east-1`.

```
Internet ──HTTPS──▶ App Runner (0.25 vCPU / 0.5 GB, auto-scaling)
                        │  pulls image from
                        ▼
                     ECR repo "judge"
                        │  container calls
                        ├──▶ DynamoDB table "judge-evaluations" (audit trail)
                        ├──▶ Secrets Manager "judge/snowflake-private-key"
                        └──▶ Snowflake (SHOW GRANTS OF ROLE, key-pair auth)
```

## First-time setup

```bash
cd judge/infra
cp terraform.tfvars.example terraform.tfvars   # fill in your Snowflake account/warehouse
terraform init
```

**Phase 1 — create just the ECR repo** (App Runner needs an image to
already exist before it can be created):

```bash
terraform apply -target=aws_ecr_repository.judge
```

**Push the first image:**

```bash
../deploy.sh
```

**Phase 2 — everything else** (App Runner, DynamoDB, IAM, Secrets
Manager):

```bash
terraform apply
```

**Populate the real Snowflake private key** (this is intentionally a
separate, non-Terraform step — see the comment in `secrets.tf` for why):

```bash
./set_snowflake_key.sh
```

To pick up a changed secret value without pushing a new image, force a
redeploy:

```bash
command aws apprunner start-deployment \
  --profile harvey-admin --region us-east-1 \
  --service-arn "$(terraform output -raw service_arn)"
```

## Subsequent deploys

Code change → rebuild → push → App Runner auto-deploys (~1–2 min):

```bash
../deploy.sh
```

Infra change (new env var, more memory, etc.) → edit the `.tf` files → :

```bash
terraform plan
terraform apply
```

## Secrets handling

- The Snowflake private key is **never** referenced by a Terraform
  variable or resource value — only an empty placeholder secret is
  created by Terraform (`secrets.tf`), with `lifecycle.ignore_changes`
  so `apply` can never overwrite the real value.
- The real value is set via `set_snowflake_key.sh`, which calls
  `aws secretsmanager put-secret-value` directly — the key touches AWS
  and your local `.snowflake/` directory only, never Terraform state.
- App Runner injects it as the `SNOWFLAKE_PRIVATE_KEY` env var at
  container start via `runtime_environment_secrets` (native Secrets
  Manager integration — no code in the app itself calls Secrets
  Manager).
- `terraform.tfstate` is gitignored regardless, as defence in depth.

## Cost (rough, at minimal/idle scale)

- App Runner: ~$5–15/mo (0.25 vCPU / 0.5 GB, pay for provisioned +
  active compute time)
- DynamoDB: pennies/mo (PAY_PER_REQUEST, this app's volume is tiny)
- ECR: pennies/mo (image storage, lifecycle policy caps at 10 images)
- Secrets Manager: ~$0.40/mo per secret

## Tearing down

```bash
terraform destroy
```

This does **not** delete anything in Snowflake (the `JUDGE_SERVICE`
user, role grants, etc.) — that's managed separately in Snowsight.
