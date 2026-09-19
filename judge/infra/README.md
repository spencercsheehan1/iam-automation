# Judge — production infrastructure

Runs Judge as an always-on container on **ECS Fargate behind an ALB**,
backed by **DynamoDB** for the audit trail and **Secrets Manager** for
the Snowflake private key. All resources live in AWS account
`280655609003` (`harvey-admin` profile), region `us-east-1`.

> **Note on App Runner:** this originally ran on AWS App Runner, which
> is simpler to operate. It doesn't work for this app: App Runner
> doesn't support WebSocket connections, and Streamlit requires one for
> live UI updates (the page loads, then hangs indefinitely on
> "Please wait..."). ECS + ALB was the fix — ALB supports WebSockets
> natively. If a future App Runner release adds WebSocket support, this
> could move back for less operational surface; unlikely though, since
> AWS has said App Runner isn't getting new features.

```
Internet ──HTTPS──▶ ALB ──▶ ECS Fargate task (0.25 vCPU / 0.5 GB)
     │  (HTTP redirects to HTTPS)   │  pulls image from
     │                              ▼
     │                           ECR repo "judge"
     │                              │  container calls
     │                              ├──▶ DynamoDB table "judge-evaluations" (audit trail)
     │                              ├──▶ Secrets Manager "judge/snowflake-private-key"
     │                              └──▶ Snowflake (SHOW GRANTS OF ROLE, key-pair auth)
     │
     └── judge.spencer-sheehan.com (Route 53 alias → ALB, ACM cert, DNS validation)
```

Runs in the account's **default VPC**, public subnets, with the Fargate
task getting a public IP directly (no NAT gateway — that's a ~$32/mo
fixed cost this app doesn't need). A security group restricts inbound
traffic to the task to only the ALB; the ALB itself accepts inbound
HTTP (301-redirected to HTTPS) and HTTPS from the internet.

## Cross-account DNS

`spencer-sheehan.com` is registered in a **different** AWS account
(`844670296817`, profile `general`) from where Judge itself runs
(`280655609003`, `harvey-admin`). `versions.tf` declares a second
provider alias (`aws.dns`, using the `general` profile) just for the
Route 53 records — the ACM certificate resource itself must live in
`harvey-admin` (same account+region as the ALB that uses it; ACM certs
can't be used cross-account without AWS Certificate Manager sharing via
RAM, which would be overkill here). `dns.tf` handles both: the cert is
created in `harvey-admin`, its DNS validation CNAME and the final A
record (alias to the ALB) are created via the `aws.dns` provider in the
domain's account.

If the `general` profile's credentials aren't available/valid, only
`dns.tf`'s resources fail — the ALB/ECS/DynamoDB/etc. in `harvey-admin`
apply independently of it.

## First-time setup

```bash
cd judge/infra
cp terraform.tfvars.example terraform.tfvars   # fill in your Snowflake account/warehouse
terraform init
```

**Phase 1 — create just the ECR repo** (the ECS task definition needs an
image to already exist before the service can start):

```bash
terraform apply -target=aws_ecr_repository.judge
```

**Push the first image:**

```bash
../deploy.sh
```

**Phase 2 — everything else** (ECS cluster/service, ALB, DynamoDB, IAM,
Secrets Manager, networking):

```bash
terraform apply
```

**Populate the real Snowflake private key** (this is intentionally a
separate, non-Terraform step — see the comment in `secrets.tf` for why):

```bash
./set_snowflake_key.sh
```

The task definition resolves Secrets Manager values at container
*startup*, not continuously, so force a fresh deployment after setting
the key for the first time:

```bash
command aws ecs update-service --profile harvey-admin --region us-east-1 \
  --cluster judge --service judge --force-new-deployment
```

## Subsequent deploys

Code change → rebuild → push → force a new ECS deployment (`deploy.sh`
does both automatically once the service exists):

```bash
../deploy.sh
```

Watch rollout status:

```bash
command aws ecs describe-services --profile harvey-admin --region us-east-1 \
  --cluster judge --service judge --query 'services[0].deployments'
```

Infra change (new env var, more memory, etc.) → edit the `.tf` files →:

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
- The ECS task definition's `secrets` block injects it as the
  `SNOWFLAKE_PRIVATE_KEY` env var at container start (the execution
  role, not the task role, needs `secretsmanager:GetSecretValue` for
  this — the ECS agent resolves it before the container ever runs, no
  application code calls Secrets Manager directly).
- `terraform.tfstate` is gitignored regardless, as defence in depth.

## Cost (rough, at minimal/idle scale)

- ALB: ~$16–20/mo (fixed hourly charge — this is the main cost driver
  and the main trade-off versus App Runner)
- Fargate: ~$5–10/mo (0.25 vCPU / 0.5 GB, one task)
- DynamoDB: pennies/mo (PAY_PER_REQUEST, this app's volume is tiny)
- ECR: pennies/mo (image storage, lifecycle policy caps at 10 images)
- Secrets Manager: ~$0.40/mo per secret
- NAT gateway: $0 (deliberately avoided — see vpc.tf)
- ACM certificate: $0 (public certs are free)
- Route 53: pennies/mo (a few DNS queries; the hosted zone itself is
  billed to the `general` account regardless of this app)

## Tearing down

```bash
terraform destroy
```

This does **not** delete anything in Snowflake (the `JUDGE_SERVICE`
user, role grants, etc.) — that's managed separately in Snowsight.
