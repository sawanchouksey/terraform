# AWS Region Configuration
aws_region = "ap-south-1" # Mumbai region

# RDS Instance Configuration
db_identifier  = "postgres-rds-instance"
engine_version = "14.17"
database_name  = "myappdb"

# Master Credentials (CHANGE THESE!)
master_username = "postgres"
master_password = "Practice$123#Rds" # Use a strong password and consider using AWS Secrets Manager

# Instance Configuration
instance_class        = "db.t3.micro" # Free tier eligible (750 hours/month for 12 months)
allocated_storage     = 20            # Free tier: 20 GB
max_allocated_storage = 100           # Autoscaling up to 100 GB

# Multi-AZ Configuration
multi_az = false # Set to true for high availability (additional cost)

# Network Configuration
vpc_id = "vpc-0cbc028b5d53643ef"
subnet_ids = [
  "subnet-00e8284becb87672b",
  "subnet-03f098afe6a476060",
  "subnet-0bfdaf7ba6397dd30"
]

# Security Configuration - Public Access with IP Whitelisting
publicly_accessible = true
allowed_cidr_blocks = [
  "", # Replace with your public IP address
  # "0.0.0.0/0"        # NEVER use this - allows access from anywhere
]

# Backup Configuration
backup_retention_period      = 1 # Minimum retention for cost savings
preferred_backup_window      = "03:00-04:00"
preferred_maintenance_window = "sun:04:00-sun:05:00"

# CloudWatch Logs
enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

# Operational Settings
skip_final_snapshot = false
apply_immediately   = false

# Tags
tags = {
  Environment = "development"
  Project     = "rds-postgres"
  ManagedBy   = "terraform"
  CostCenter  = "minimal"
}
