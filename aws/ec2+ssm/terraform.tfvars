region              = "ap-south-1"
vpc_cidr            = "10.0.0.0/16"
private_subnet_cidr = "10.0.1.0/24"
availability_zone   = "ap-south-1a"
instance_type       = "t2.micro"
ami_id              = "ami-0ddfba243cbee3768"
key_name            = "my-ec2"
tags = {
  Environment = "Development"
  Terraform   = "True"
  Project     = "Infrastructure"
}