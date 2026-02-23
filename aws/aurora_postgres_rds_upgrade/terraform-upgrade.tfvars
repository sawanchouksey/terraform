# AWS Region Configuration
aws_region = "ap-south-1" # Mumbai region

# RDS Instance Configuration
db_identifier  = "postgres-rds-instance"
engine_version = "14.17"  # Current version
database_name  = "myappdb"

# Master Credentials
master_username = "postgres"
master_password = "Practice$123#Rds"

# Instance Configuration
instance_class        = "db.t3.micro"
allocated_storage     = 20
max_allocated_storage = 100

# Multi-AZ Configuration
multi_az = false

# Network Configuration
vpc_id = "vpc-0cbc028b5d53643ef"
subnet_ids = [
  "subnet-00e8284becb87672b",
  "subnet-03f098afe6a476060",
  "subnet-0bfdaf7ba6397dd30"
]

# Security Configuration
publicly_accessible = true
allowed_cidr_blocks = [
  "",     # Current IP
  "",  # Alternative IP
]

# Backup Configuration
backup_retention_period      = 7  # Increase for upgrade safety
preferred_backup_window      = "03:00-04:00"
preferred_maintenance_window = "sun:04:00-sun:05:00"

# CloudWatch Logs
enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

# Operational Settings
skip_final_snapshot = false
apply_immediately   = false

# Blue/Green Deployment Configuration
enable_blue_green_upgrade = true       # Set to true to create Blue/Green deployment
target_engine_version     = "16.1"     # Target PostgreSQL version
target_instance_class     = null       # null = keep same instance class, or specify new class

# Tags
tags = {
  Environment = "development"
  Project     = "rds-postgres-upgrade"
  ManagedBy   = "terraform"
  CostCenter  = "minimal"
  Purpose     = "blue-green-upgrade-testing"
}
