#  AWS ACM (Amazon Certificate Manager) TLS certificate for a domain for an Application Load Balancer (ALB).

resource "aws_acm_certificate" "alb_cert" {
  domain_name       = aws_route53_record.alb_record.fqdn #Specifies the domain name for which the certificate is requested.
  validation_method = "DNS"
}

# Creates a DNS record in Route 53 to validate the domain ownership as part of the ACM certificate validation process.
resource "aws_route53_record" "cert_validation" {
  allow_overwrite = true
  name            = tolist(aws_acm_certificate.alb_cert.domain_validation_options)[0].resource_record_name
  records         = [ tolist(aws_acm_certificate.alb_cert.domain_validation_options)[0].resource_record_value ]
  type            = tolist(aws_acm_certificate.alb_cert.domain_validation_options)[0].resource_record_type
  zone_id         = data.aws_route53_zone.hosted_zone_id.zone_id
  ttl             = 60 # Time-to-live for the DNS record.
}

# This resource finalizes the ACM certificate validation process after the DNS validation record has been created.
resource "aws_acm_certificate_validation" "validate_alb_cert" {
  certificate_arn         = aws_acm_certificate.alb_cert.arn # ARN (Amazon Resource Name)
  validation_record_fqdns = [ aws_route53_record.cert_validation.fqdn ] # Specifies the FQDNs of the DNS records that were created for validation.
}