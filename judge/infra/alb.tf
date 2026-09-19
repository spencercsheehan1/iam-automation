resource "aws_lb" "judge" {
  name               = var.app_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  # Streamlit holds a long-lived websocket open; ALB's 60s default idle
  # timeout would silently drop it during quiet periods and force
  # reconnects. 300s keeps normal browsing sessions stable.
  idle_timeout = 300
}

resource "aws_lb_target_group" "judge" {
  name        = var.app_name
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip" # required for Fargate

  health_check {
    path                = "/_stcore/health"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
    matcher             = "200"
  }

  # Streamlit's websocket connections are long-lived; keep the target
  # group from cycling a healthy container out from under an open stream.
  deregistration_delay = 30
}

# Plain HTTP just redirects to HTTPS — nothing is ever served over it.
resource "aws_lb_listener" "judge_http" {
  load_balancer_arn = aws_lb.judge.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "judge_https" {
  load_balancer_arn = aws_lb.judge.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.judge.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.judge.arn
  }
}
