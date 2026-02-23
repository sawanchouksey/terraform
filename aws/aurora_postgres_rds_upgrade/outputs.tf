output "db_instance_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "db_instance_address" {
  description = "RDS instance address (hostname)"
  value       = aws_db_instance.postgres.address
}

output "db_instance_arn" {
  description = "RDS instance ARN"
  value       = aws_db_instance.postgres.arn
}

output "db_instance_id" {
  description = "RDS instance identifier"
  value       = aws_db_instance.postgres.id
}

output "db_port" {
  description = "Database port"
  value       = aws_db_instance.postgres.port
}

output "database_name" {
  description = "Database name"
  value       = aws_db_instance.postgres.db_name
}

output "security_group_id" {
  description = "Security group ID for RDS instance"
  value       = aws_security_group.rds_sg.id
}

output "db_instance_status" {
  description = "RDS instance status"
  value       = aws_db_instance.postgres.status
}

output "db_instance_resource_id" {
  description = "RDS instance resource ID"
  value       = aws_db_instance.postgres.resource_id
}

output "connection_string" {
  description = "PostgreSQL connection string (without password)"
  value       = "postgresql://${var.master_username}:<password>@${aws_db_instance.postgres.endpoint}/${var.database_name}"
  sensitive   = true
}
