output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_id" {
  description = "The ID of the private subnet"
  value       = aws_subnet.private.id
}

output "instance_id" {
  description = "The ID of the EC2 instance"
  value       = aws_instance.private.id
}

output "ssm_role_arn" {
  description = "ARN of the IAM role for SSM"
  value       = aws_iam_role.ssm_role.arn
}

output "vpc_endpoints" {
  description = "Map of VPC endpoints created for SSM services"
  value = {
    for k, v in aws_vpc_endpoint.ssm_endpoint : k => v.id
  }
}