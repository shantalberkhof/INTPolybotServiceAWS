# Output values from this module, such as instance IDs, ALB DNS, etc.

# e.g: t2.micro
output "polybot_instance_type" {
  value = data.aws_ec2_instance_types.polybot_instance_types.instance_types[0]
}

# Outputs the Telegram bot token.
output "project_telegram_token_secret_id" {
  value = aws_secretsmanager_secret.tf-botToken.id
}

# domain name of the Application Load Balancer used by Polybot
output "project_telegram_app_url" {
  value = aws_route53_record.alb_record.fqdn
}

# Outputs the port numbers used by the ALB for HTTPS
output "project_telegram_app_url_port_https" {
  value = aws_lb_listener.alb_https.port
}

# Outputs the port numbers used by the ALB for HTTP
output "project_telegram_app_url_port_http" {
  value = aws_lb_listener.alb_http.port
}