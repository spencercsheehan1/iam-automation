# Reuse the account's default VPC/subnets rather than provisioning a
# custom one — this is a single small service, and a custom VPC (plus a
# NAT gateway, ~$32/mo, to give private subnets internet egress) would
# be the opposite of lightweight. The Fargate task gets a public IP
# directly instead, which is fine for a single-container service that
# isn't handling anything that requires network isolation beyond the
# security group.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "alb" {
  name        = "${var.app_name}-alb"
  description = "Allow inbound HTTP from the internet to the ALB"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP (redirects to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "fargate_service" {
  name        = "${var.app_name}-fargate-service"
  description = "Allow inbound from the ALB only; outbound anywhere (ECR, DynamoDB, Secrets Manager, Snowflake)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "From ALB"
    from_port       = 8501
    to_port         = 8501
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
