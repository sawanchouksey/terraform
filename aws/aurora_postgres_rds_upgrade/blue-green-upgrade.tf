# Blue/Green Deployment for RDS PostgreSQL Major Version Upgrade
# This configuration supports upgrading from PostgreSQL 14.17 to 16.x

# Target Parameter Group for PostgreSQL 16
resource "aws_db_parameter_group" "postgres_pg_v16" {
  count       = var.enable_blue_green_upgrade ? 1 : 0
  name        = "${var.db_identifier}-pg-v16"
  family      = "postgres16"
  description = "PostgreSQL 16 parameter group for blue/green upgrade"

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  tags = merge(
    var.tags,
    {
      Name    = "${var.db_identifier}-pg-v16"
      Purpose = "Blue-Green-Upgrade"
    }
  )
}

# Blue/Green Deployment Resource
# Note: This creates a copy of your database and upgrades it
resource "aws_rds_blue_green_deployment" "postgres_upgrade" {
  count = var.enable_blue_green_upgrade ? 1 : 0

  blue_green_deployment_name = "${var.db_identifier}-to-pg16"
  source_arn                 = aws_db_instance.postgres.arn
  target_engine_version      = var.target_engine_version

  # Use the new parameter group for PostgreSQL 16
  target_db_parameter_group_name = aws_db_parameter_group.postgres_pg_v16[0].name

  # Optional: Upgrade DB instance class during migration
  # target_db_instance_class = var.target_instance_class

  tags = merge(
    var.tags,
    {
      Name        = "${var.db_identifier}-blue-green-upgrade"
      Source      = var.engine_version
      Target      = var.target_engine_version
      Environment = "blue-green-deployment"
    }
  )
}

# Output the Blue/Green deployment status
output "blue_green_deployment_id" {
  description = "ID of the Blue/Green deployment"
  value       = var.enable_blue_green_upgrade ? aws_rds_blue_green_deployment.postgres_upgrade[0].id : null
}

output "blue_green_deployment_arn" {
  description = "ARN of the Blue/Green deployment"
  value       = var.enable_blue_green_upgrade ? aws_rds_blue_green_deployment.postgres_upgrade[0].arn : null
}

output "blue_green_deployment_status" {
  description = "Status of the Blue/Green deployment"
  value       = var.enable_blue_green_upgrade ? aws_rds_blue_green_deployment.postgres_upgrade[0].status : null
}

output "green_environment_endpoint" {
  description = "Endpoint of the green (upgraded) environment"
  value       = var.enable_blue_green_upgrade ? try(aws_rds_blue_green_deployment.postgres_upgrade[0].target[0].endpoint, null) : null
}
