terraform {
  required_version = ">= 1.5"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.21"
    }
  }

  # Local state, deliberately — same reasoning as ../versions.tf (small,
  # solo-owned prototype; terraform.tfstate is gitignored). Kept separate
  # from the AWS root module so an AWS apply never needs Snowflake
  # credentials and vice versa. The provider's private key is read from
  # disk by the provider block and is never written to state.
}
