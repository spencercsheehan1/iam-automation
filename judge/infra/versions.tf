terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state, deliberately. This is a small, solo-owned prototype in
  # its own AWS account (harvey-admin) — no team to coordinate state
  # locking with. terraform.tfstate is gitignored; nothing in this
  # config ever passes a real secret through a Terraform resource (see
  # secrets.tf), so the state file never contains sensitive material
  # even though it lives on local disk.
  #
  # Snowflake roles, grants and permissions are managed separately in
  # ./snowflake/ (its own root module and state).
}

provider "aws" {
  region  = var.aws_region
  profile = "harvey-admin"

  default_tags {
    tags = {
      Project   = "iam-automation"
      App       = "judge"
      ManagedBy = "terraform"
    }
  }
}

# The domain (spencer-sheehan.com) lives in a separate AWS account from
# the app — this alias manages the DNS records (cert validation + the
# judge.spencer-sheehan.com record itself) in that account instead.
provider "aws" {
  alias   = "dns"
  region  = var.aws_region
  profile = "general"
}
