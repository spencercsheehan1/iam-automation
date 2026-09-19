# ACM cert lives in the app's account/region (required — an ALB can only
# use a cert from the same account+region it's in), but DNS validation
# and the actual A record live in the domain's account (see the "dns"
# provider alias in versions.tf).
resource "aws_acm_certificate" "judge" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  provider = aws.dns

  for_each = {
    for dvo in aws_acm_certificate.judge.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = var.route53_zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "judge" {
  certificate_arn         = aws_acm_certificate.judge.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

resource "aws_route53_record" "judge" {
  provider = aws.dns

  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.judge.dns_name
    zone_id                = aws_lb.judge.zone_id
    evaluate_target_health = true
  }
}
