terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# DB Subnet Group
resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "${var.db_identifier}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.db_identifier}-subnet-group"
    }
  )
}

# Security Group for RDS
resource "aws_security_group" "rds_sg" {
  name        = "${var.db_identifier}-sg"
  description = "Security group for RDS PostgreSQL instance"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "PostgreSQL access"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.db_identifier}-sg"
    }
  )
}

# RDS Parameter Group
resource "aws_db_parameter_group" "postgres_pg" {
  name        = "${var.db_identifier}-pg"
  family      = "postgres14"
  description = "PostgreSQL 14 parameter group"

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
      Name = "${var.db_identifier}-pg"
    }
  )
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "postgres" {
  identifier     = var.db_identifier
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.master_username
  password = var.master_password

  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  parameter_group_name   = aws_db_parameter_group.postgres_pg.name

  publicly_accessible = var.publicly_accessible
  multi_az            = var.multi_az

  backup_retention_period         = var.backup_retention_period
  backup_window                   = var.preferred_backup_window
  maintenance_window              = var.preferred_maintenance_window
  enabled_cloudwatch_logs_exports = var.enabled_cloudwatch_logs_exports

  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.db_identifier}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  apply_immediately = var.apply_immediately

  # Disable performance insights and enhanced monitoring for cost savings
  performance_insights_enabled = false
  monitoring_interval          = 0

  # Auto minor version upgrade
  auto_minor_version_upgrade = true

  # Deletion protection (set to true for production)
  deletion_protection = false

  tags = merge(
    var.tags,
    {
      Name = var.db_identifier
    }
  )

  lifecycle {
    ignore_changes = [final_snapshot_identifier]
  }
}
