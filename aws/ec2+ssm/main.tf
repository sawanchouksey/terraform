# VPC and Networking Resources
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = "Main-VPC" })
}

resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = var.availability_zone
  tags              = merge(var.tags, { Name = "Private-Subnet" })
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.tags, { Name = "Main-IGW" })
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.tags, { Name = "Private-Route-Table" })
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}

# IAM Resources
resource "aws_iam_role" "ssm_role" {
  name = "SSMRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "ec2.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ssm_attach" {
  role       = aws_iam_role.ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm_profile" {
  name = "SSMInstanceProfile"
  role = aws_iam_role.ssm_role.name
}

# EC2 Instance
resource "aws_instance" "private" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.private.id
  associate_public_ip_address = false
  key_name                    = var.key_name
  iam_instance_profile        = aws_iam_instance_profile.ssm_profile.name

  tags = merge(var.tags, { Name = "PrivateInstance" })
}

# VPC Endpoints for SSM
locals {
  services = {
    "ec2messages" : {
      "name" : "com.amazonaws.${var.region}.ec2messages"
    },
    "ssm" : {
      "name" : "com.amazonaws.${var.region}.ssm"
    },
    "ssmmessages" : {
      "name" : "com.amazonaws.${var.region}.ssmmessages"
    }
  }
}

resource "aws_security_group" "ssm_https" {
  name        = "allow_ssm"
  description = "Allow SSM traffic"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.private_subnet_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "SSM-Security-Group" })
}

resource "aws_vpc_endpoint" "ssm_endpoint" {
  for_each = local.services

  vpc_id              = aws_vpc.main.id
  service_name        = each.value.name
  vpc_endpoint_type   = "Interface"
  security_group_ids  = [aws_security_group.ssm_https.id]
  private_dns_enabled = true
  ip_address_type     = "ipv4"
  subnet_ids          = [aws_subnet.private.id]

  tags = merge(var.tags, { Name = "VPC-Endpoint-${each.key}" })
}