# Judge — Snowflake infrastructure (Terraform)

Manages the Snowflake side of the demo: **roles**, **user → role grants**, and
**least-privilege permissions** on demo data objects. It is a separate root
module from `../` (AWS) with its own local state, so neither needs the other's
credentials.

| Managed here | Not managed here |
|---|---|
| One role per `../../policies/*.yaml` (`role:` = role name) | The Snowflake users themselves (must already exist: `ALICE`, `ANGELA`, `BOB`, `JOSHUA`, `SPENCER`) |
| Demo database `PROD_DATA` with `FINANCE`, `MARKETING`, `ANALYTICS` schemas + one table each | `JUDGE_SERVICE` (the read-only service account the app uses) |
| Least-privilege grants per role (`privileges.tf`) | The warehouse (referenced, only granted `USAGE`) |
| Legitimate user → role grants (`grants.tf`) | "Rogue" demo grants — make those by hand in the Snowflake UI |

Adding a policy file adds the role, but `terraform plan` **fails** until the
role also has an entry in `local.role_access` (`privileges.tf`) — a new role can
never silently get no permissions or too many.

## Permissions

| Role | Privileges |
|---|---|
| `PROD_ACCOUNTING_RO_ROLE` | `USAGE` on database + warehouse; `USAGE` / `SELECT` on `FINANCE` |
| `PROD_MARKETING_RO_ROLE` | `USAGE` on database + warehouse; `USAGE` / `SELECT` on `MARKETING` |
| `PROD_AUDITOR_RO_ROLE` | `USAGE` on database + warehouse; `USAGE` / `SELECT` on all three schemas |
| `PROD_ANALYTICS_ROLE` | `USAGE` on database + warehouse; `SELECT`/`INSERT`/`UPDATE`/`DELETE`/`TRUNCATE` + `CREATE TABLE` on `ANALYTICS` |
| `PROD_ADMIN_ROLE` | Account-level `CREATE USER`, `CREATE ROLE`. No data access, no `MANAGE GRANTS` |

Table grants cover both existing and future tables.

## One-time bootstrap (manual)

Terraform authenticates as a dedicated `TERRAFORM_SERVICE` user so the app's
`JUDGE_SERVICE` identity never needs write access.

1. Generate a key pair (skip if `../../.snowflake/terraform_rsa_key.p8` exists;
   the directory is gitignored):

   ```bash
   cd ../../.snowflake
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out terraform_rsa_key.p8 -nocrypt
   chmod 600 terraform_rsa_key.p8
   openssl rsa -in terraform_rsa_key.p8 -pubout -out terraform_rsa_key.pub
   grep -v '^-----' terraform_rsa_key.pub | tr -d '\n'   # public key body for step 2
   ```

2. In a Snowflake worksheet, as `ACCOUNTADMIN`:

   ```sql
   USE ROLE ACCOUNTADMIN;

   CREATE USER IF NOT EXISTS TERRAFORM_SERVICE
     TYPE = SERVICE
     DEFAULT_ROLE = SECURITYADMIN
     RSA_PUBLIC_KEY = '<public key body from step 1>';
   GRANT ROLE SYSADMIN      TO USER TERRAFORM_SERVICE;  -- creates db/schemas/tables
   GRANT ROLE SECURITYADMIN TO USER TERRAFORM_SERVICE;  -- creates roles, manages grants

   -- PROD_ANALYTICS_ROLE was created by hand and holds ACCOUNTADMIN, which
   -- is unrealistic. Terraform can't revoke a grant it doesn't manage.
   REVOKE ROLE ACCOUNTADMIN FROM ROLE PROD_ANALYTICS_ROLE;
   ```

   (If `TYPE = SERVICE` isn't available on your account, drop that line.)

## Apply

Create any missing users first (Terraform grants roles to users but doesn't create them):

```sql
USE ROLE SECURITYADMIN;
CREATE USER IF NOT EXISTS ANGELA;
CREATE USER IF NOT EXISTS JOSHUA;
CREATE USER IF NOT EXISTS SPENCER;
```

If you have `SNOWFLAKE_*` variables exported for Judge's live mode (especially
`SNOWFLAKE_PASSWORD`), the Terraform provider reads them and fails with
"`password` conflicts with `private_key`". Unset them for the command:

```bash
env -u SNOWFLAKE_PASSWORD -u SNOWFLAKE_ACCOUNT -u SNOWFLAKE_USER \
    -u SNOWFLAKE_WAREHOUSE -u SNOWFLAKE_ROLE -u SNOWFLAKE_PRIVATE_KEY_PATH terraform plan
```

Also, `PROD_ANALYTICS_ROLE` must be owned by `SECURITYADMIN` before the first apply
(it was created by hand as `ACCOUNTADMIN`):

```sql
USE ROLE ACCOUNTADMIN;
GRANT OWNERSHIP ON ROLE PROD_ANALYTICS_ROLE TO ROLE SECURITYADMIN COPY CURRENT GRANTS;
```

```bash
cd judge/infra/snowflake
terraform init
terraform plan      # review: 1 import (PROD_ANALYTICS_ROLE), new roles/objects/grants, 0 destroys
terraform apply
```

This changes the live Snowflake account. On the first apply, granting a role a
user already holds (e.g. `ALICE` → `PROD_ANALYTICS_ROLE`) is a harmless no-op
in Snowflake.

## Verify

```sql
SHOW GRANTS TO ROLE PROD_ANALYTICS_ROLE;        -- no ACCOUNTADMIN
USE ROLE PROD_ACCOUNTING_RO_ROLE;
SELECT * FROM PROD_DATA.FINANCE.INVOICES;       -- allowed
SELECT * FROM PROD_DATA.MARKETING.CAMPAIGNS;    -- denied
```

Then run Judge in live mode: the legitimate grants above `PASS`. Grant a role to
someone who doesn't qualify (e.g. `GRANT ROLE PROD_ADMIN_ROLE TO USER WINSTON;`
in the UI) and it shows `FAIL`.

## What Terraform does *not* prevent

Terraform declares desired state; it does not stop an admin from changing
Snowflake directly. It only re-adds a *managed* grant that someone revoked, and
it neither sees nor reverts grants outside its config. Judge is the detective
control: it reads live grants, so out-of-band changes show up on the next run.
Judge currently evaluates role *membership* only, not the privileges a role holds.
