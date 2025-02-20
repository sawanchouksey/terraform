# AWS Private Instance with SSM Configuration

This Terraform project sets up a private EC2 instance in AWS with Systems Manager (SSM) access capability, allowing secure management without requiring a bastion host or direct internet access.

## Architecture

This infrastructure includes:
- VPC with private subnet
- EC2 instance with SSM access 
- IAM role and instance profile for SSM permissions
- VPC Endpoints for SSM connectivity (without internet access)
- S3 Gateway Endpoint for SSM patches and artifacts

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) (v1.0.0+)
- AWS account credentials configured
- An S3 bucket for Terraform state (referenced in `providers.tf`)
- A DynamoDB table for state locking (referenced in `providers.tf`)

## Project Structure

```
.
├── main.tf              # Main resource definitions
├── variables.tf         # Variable declarations
├── terraform.tfvars     # Variable values
├── outputs.tf           # Output definitions
├── providers.tf         # Provider and backend configuration
└── README.md            # This file
```

## Key Components

1. **VPC Configuration**
   - Private subnet with no internet access
   - DNS support enabled for SSM connectivity

2. **SSM Access via VPC Endpoints**
   - Interface endpoints for SSM, EC2Messages, and SSMMessages
   - Gateway endpoint for S3 access
   - Security group configuration for HTTPS access

3. **IAM Configuration**
   - IAM role with SSM managed policy
   - Instance profile for EC2 instance

4. **EC2 Instance**
   - Private instance with no public IP
   - Amazon Linux 2023 AMI
   - SSM agent pre-installed for management

## Remote State Configuration

The project uses remote state stored in S3 with DynamoDB locking:

```hcl
terraform {
  backend "s3" {
    bucket         = "my-terraform-state-bucket"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

## Usage

1. **Initialize the project**:
   ```bash
   terraform init
   ```

2. **Review the execution plan**:
   ```bash
   terraform plan
   ```

3. **Apply the configuration**:
   ```bash
   terraform apply
   ```

4. **Connect to the instance via SSM**:
   ```bash
   aws ssm start-session --target i-xxxxxxxxxxxx
   ```

## Customization

Modify `terraform.tfvars` to customize the deployment:

```hcl
region              = "us-east-1"
vpc_cidr            = "10.0.0.0/16"
private_subnet_cidr = "10.0.1.0/24"
availability_zone   = "us-east-1a"
instance_type       = "t2.micro"
ami_id              = "ami-0df435f331839b2d6"
key_name            = "my-key-pair"
tags                = {
  Environment = "Development"
  Terraform   = "True"
  Project     = "Infrastructure"
}
```

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

## Security Considerations

- The EC2 instance has no direct internet access
- Management is only possible via SSM
- All traffic stays within the AWS network
- No bastion hosts or SSH key management required