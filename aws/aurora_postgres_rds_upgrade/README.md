# RDS PostgreSQL Terraform Configuration

This Terraform configuration creates an Amazon RDS PostgreSQL database instance version 14.17 in the Mumbai region (ap-south-1).

## Prerequisites

- Terraform >= 1.0
- AWS CLI version 2
- AWS Account with appropriate permissions
- Existing VPC with at least 2 subnets in different availability zones (or use default VPC)

## Resources Created

- RDS PostgreSQL Instance (version 14.17)
- DB Subnet Group
- Security Group for database access
- DB Parameter Group (postgres14 family)

## Setup Instructions

### Step 1: Install Required Tools

#### Install AWS CLI (if not already installed)

**Windows:**
```powershell
# Download and run the MSI installer
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# Verify installation
aws --version
```

**macOS:**
```bash
# Using Homebrew
brew install awscli

# Or using the installer
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Verify installation
aws --version
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify installation
aws --version
```

#### Install Terraform (if not already installed)

**Windows (using Chocolatey):**
```powershell
choco install terraform

# Or download from: https://www.terraform.io/downloads
```

**macOS:**
```bash
brew install terraform
```

**Linux:**
```bash
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify installation
terraform --version
```

### Step 2: Configure AWS CLI

#### Option A: Configure with Access Keys

```bash
# Run AWS configure command
aws configure

# You will be prompted for:
# AWS Access Key ID: [Enter your access key]
# AWS Secret Access Key: [Enter your secret key]
# Default region name: ap-south-1
# Default output format: json
```

#### Option B: Configure with Named Profile

```bash
# Create a named profile
aws configure --profile aurora-project

# Set the profile as environment variable
export AWS_PROFILE=aurora-project  # Linux/macOS
$env:AWS_PROFILE="aurora-project"  # Windows PowerShell
set AWS_PROFILE=aurora-project     # Windows CMD
```

#### Verify AWS Configuration

```bash
# Check configured credentials
aws sts get-caller-identity

# List available VPCs in Mumbai region
aws ec2 describe-vpcs --region ap-south-1

# List available subnets
aws ec2 describe-subnets --region ap-south-1 --query 'Subnets[*].[SubnetId,AvailabilityZone,VpcId,CidrBlock]' --output table
```

### Step 3: Get Your VPC and Subnet Information

**Option A: Using JSON output (works on all platforms)**

```bash
# List all VPCs in Mumbai region (JSON format)
aws ec2 describe-vpcs --region ap-south-1

# Get default VPC ID (simple and reliable)
aws ec2 describe-vpcs --region ap-south-1 --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text

# List subnets for default VPC (replace VPC ID from previous command)
aws ec2 describe-subnets --region ap-south-1 --filters Name=vpc-id,Values=vpc-0cbc028b5d53643ef

# Get subnet IDs in table format
aws ec2 describe-subnets --region ap-south-1 --filters Name=vpc-id,Values=vpc-0cbc028b5d53643ef --query "Subnets[*].[SubnetId,AvailabilityZone,CidrBlock]" --output table
```

**Option B: Windows PowerShell specific**

```powershell
# Get default VPC ID (PowerShell)
aws ec2 describe-vpcs --region ap-south-1 --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text

# Get VPC details
aws ec2 describe-vpcs --region ap-south-1 --query "Vpcs[*].{VpcId:VpcId, CIDR:CidrBlock, Default:IsDefault}" --output table

# List subnets (replace vpc-xxxxx with your VPC ID)
aws ec2 describe-subnets --region ap-south-1 --filters Name=vpc-id,Values=vpc-xxxxx --query "Subnets[*].{SubnetId:SubnetId, AZ:AvailabilityZone, CIDR:CidrBlock}" --output table

# Get first two subnet IDs
aws ec2 describe-subnets --region ap-south-1 --filters Name=vpc-id,Values=vpc-xxxxx --query "Subnets[0:2].SubnetId" --output text
```

**Option C: Step-by-step extraction**

```bash
# Step 1: Get all VPC info and save to file
aws ec2 describe-vpcs --region ap-south-1 > vpcs.json

# Step 2: Manually look for VpcId where IsDefault = true
# From your output: vpc-0cbc028b5d53643ef

# Step 3: Get subnets for your VPC
aws ec2 describe-subnets --region ap-south-1 --filters Name=vpc-id,Values=vpc-0cbc028b5d53643ef > subnets.json

# Step 4: Look for at least 2 subnet IDs from different availability zones
```

### Step 4: Get Your Public IP Address

```bash
# Get your current public IP
curl ifconfig.me

# Or use AWS CLI
curl https://checkip.amazonaws.com

# Or using PowerShell (Windows)
(Invoke-WebRequest -Uri "https://api.ipify.org").Content
```

## Configuration

### 1. Update terraform.tfvars

Before applying, update the following values in `terraform.tfvars`:

```hcl
# RDS Instance Configuration
db_identifier  = "postgres-rds-instance"
engine_version = "14.17"
database_name  = "myappdb"

# Network Configuration (use values from Step 3)
vpc_id = "vpc-0123456789abcdef0"  # Your VPC ID from Step 3
subnet_ids = [
  "subnet-0123456789abcdef0",      # Subnet in AZ 1 (ap-south-1a)
  "subnet-0fedcba9876543210"       # Subnet in AZ 2 (ap-south-1b)
]

# Security - Public Access with IP Whitelisting (use IP from Step 4)
publicly_accessible = true
allowed_cidr_blocks = [
  "203.0.113.45/32"  # Your public IP from Step 4 with /32
]

# Instance Configuration
instance_class        = "db.t3.micro"  # Free tier eligible
allocated_storage     = 20             # Free tier: 20 GB
max_allocated_storage = 100            # Autoscaling limit
multi_az              = false          # Set true for HA

# Credentials - USE STRONG PASSWORD
master_username = "postgres"
master_password = "YourStrongP@ssw0rd123!"  # Change this!
```

### 2. Initialize Terraform

```bash
# Navigate to the project directory
cd /path/to/auroraRdsPostgresUpgrade

# Initialize Terraform (downloads required providers)
terraform init

# Expected output:
# Terraform has been successfully initialized!
# Expected output:
# Terraform has been successfully initialized!
```

### 3. Validate Configuration

```bash
# Validate Terraform syntax
terraform validate

# Expected output:
# Success! The configuration is valid.

# Format Terraform files
terraform fmt
```

### 4. Review the Deployment Plan

```bash
# Generate and review execution plan
terraform plan

# Save plan to a file for review
terraform plan -out=tfplan

# Review what will be created:
# - 1 RDS PostgreSQL Instance (db.t3.micro)
# - 1 DB Subnet Group
# - 1 Security Group
# - 1 Parameter Group
```

### 5. Deploy the Infrastructure

```bash
# Apply the configuration
terraform apply

# Review the plan and type 'yes' when prompted

# Or auto-approve (use with caution)
terraform apply -auto-approve

# Deployment takes approximately 5-10 minutes
```

### 6. Retrieve Connection Information

```bash
# Get all outputs
terraform output

# Get specific outputs
terraform output db_instance_endpoint
terraform output db_instance_address
terraform output db_port
terraform output database_name

# Save outputs to a file
terraform output -json > outputs.json
```

### 7. Connect to the Database

```bash
# Install PostgreSQL client if not already installed

# Windows (using Chocolatey)
choco install postgresql

# macOS
brew install postgresql

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install postgresql-client

# Connect using psql
psql -h $(terraform output -raw db_instance_address) \
     -p 5432 \
     -U postgres \
     -d myappdb

# Or with full connection string
psql "postgresql://postgres:YourPassword@your-instance-endpoint:5432/myappdb"
```

### 8. Verify Database Connection

```sql
-- After connecting, run these commands to verify

-- Check PostgreSQL version
SELECT version();

-- Check current database
SELECT current_database();

-- List databases
\l

-- Create a test table
CREATE TABLE test_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert test data
INSERT INTO test_table (name) VALUES ('Test Entry');

-- Query test data
SELECT * FROM test_table;

-- Exit psql
\q
```

## Monitoring and Management

### View Instance Status

```bash
# Get RDS instance information
aws rds describe-db-instances \
    --db-instance-identifier postgres-rds-instance \
    --region ap-south-1 \
    --query 'DBInstances[0].[DBInstanceIdentifier,DBInstanceStatus,DBInstanceClass,Endpoint.Address]' \
    --output table

# Get instance status only
aws rds describe-db-instances \
    --db-instance-identifier postgres-rds-instance \
    --region ap-south-1 \
    --query 'DBInstances[0].DBInstanceStatus' \
    --output text
```

### View Logs

```bash
# List available log files
aws rds describe-db-log-files \
    --db-instance-identifier postgres-rds-instance \
    --region ap-south-1

# Download a log file
aws rds download-db-log-file-portion \
    --db-instance-identifier postgres-rds-instance \
    --log-file-name error/postgresql.log.2026-02-23-00 \
    --region ap-south-1 \
    --output text
```

### View Costs

```bash
# Estimate monthly costs using AWS Cost Explorer
aws ce get-cost-and-usage \
    --time-period Start=2026-02-01,End=2026-02-28 \
    --granularity MONTHLY \
    --metrics "UnblendedCost" \
    --filter file://filter.json

# Set up a billing alert
aws cloudwatch put-metric-alarm \
    --alarm-name aurora-high-cost-alert \
    --alarm-description "Alert when Aurora costs exceed threshold" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 86400 \
    --evaluation-periods 1 \
    --threshold 100 \
    --comparison-operator GreaterThanThreshold
```

## Updating the Infrastructure

```bash
# Modify terraform.tfvars or *.tf files as needed

# Preview changes
terraform plan

# Apply changes
terraform apply

# Note: Some changes may require instance restart or replacement
```

## Cleanup

### Option 1: Destroy with Terraform

```bash
# Review what will be destroyed
terraform plan -destroy

# Destroy all resources
terraform destroy

# Type 'yes' when prompted

# Or auto-approve (use with caution)
terraform destroy -auto-approve
```

### Option 2: Manual Cleanup (if Terraform fails)

```bash
# Delete RDS instance
aws rds delete-db-instance \
    --db-instance-identifier postgres-rds-instance \
    --skip-final-snapshot \
    --region ap-south-1

# Wait for instance to be deleted (check status)
aws rds describe-db-instances \
    --db-instance-identifier postgres-rds-instance \
    --region ap-south-1

# Delete security group (after instance is deleted)
aws ec2 delete-security-group \
    --group-id sg-xxxxxxxxx \
    --region ap-south-1

# Delete subnet group (optional)
aws rds delete-db-subnet-group \
    --db-subnet-group-name postgres-rds-instance-subnet-group \
    --region ap-south-1
```

**Note**: If `skip_final_snapshot = false` in your configuration, a final snapshot will be created before deletion.

## Troubleshooting

### Common Issues

**Issue: "Error creating DB Subnet Group: DBSubnetGroupDoesNotCoverEnoughAZs"**
```bash
# Solution: Ensure subnets are in at least 2 different availability zones
aws ec2 describe-subnets --subnet-ids subnet-xxx subnet-yyy \
    --query 'Subnets[*].[SubnetId,AvailabilityZone]' --output table
```

**Issue: "UnauthorizedOperation: You are not authorized to perform this operation"**
```bash
# Solution: Verify AWS credentials
aws sts get-caller-identity

# Check IAM permissions - you need permissions for:
# - rds:*
# - ec2:Describe*
# - ec2:CreateSecurityGroup
# - ec2:AuthorizeSecurityGroupIngress
```

**Issue: "Cannot connect to database"**
```bash
# Check security group rules
aws ec2 describe-security-groups \
    --group-ids $(terraform output -raw security_group_id) \
    --region ap-south-1

# Verify your current IP
curl ifconfig.me

# Update security group if IP changed
terraform apply
```

**Issue: "Error: timeout while waiting for state to become 'available'"**
```bash
# RDS creation can take 5-10 minutes
# Check instance status manually:
aws rds describe-db-instances \
    --db-instance-identifier postgres-rds-instance \
    --region ap-south-1 \
    --query 'DBInstances[0].DBInstanceStatus'
```

## Outputs

After successful deployment, the following outputs will be available:

- `db_instance_endpoint`: RDS instance endpoint (hostname:port)
- `db_instance_address`: RDS instance address (hostname only)
- `db_instance_arn`: RDS instance ARN
- `db_port`: Database port (5432)
- `database_name`: Name of the created database
- `security_group_id`: Security group ID for the RDS instance
- `connection_string`: PostgreSQL connection string template (sensitive)

## Important Configuration Notes

### Security Best Practices

1. **Master Password**: Store credentials in AWS Secrets Manager instead of plain text
   ```bash
   # Create secret in AWS Secrets Manager
   aws secretsmanager create-secret \
       --name aurora-postgres-master-password \
       --secret-string "YourStrongPassword" \
       --region ap-south-1
   ```

2. **CIDR Blocks**: Restrict `allowed_cidr_blocks` to specific IPs only (using /32)
3. **Encryption**: Storage encryption is enabled by default  
4. **Backups**: Configured with 1-day retention period (minimum for cost savings)
5. **Public Access**: Enabled with IP whitelisting for remote access

### Instance Configuration (Cost-Optimized)

- **Instance Class**: `db.t3.micro` (free tier eligible - 750 hours/month for 12 months)
- **Storage**: 20 GB allocated, autoscaling up to 100 GB (GP3)
- **Storage Type**: GP3 (better performance than GP2)
- **Multi-AZ**: Disabled (single AZ for cost savings)
- **Performance Insights**: Disabled (saves costs)
- **Enhanced Monitoring**: Disabled (saves CloudWatch costs)
- **Free Tier**: Eligible for AWS free tier (first 12 months)

### Networking

- Requires at least 2 subnets in different availability zones for subnet group
- Security group allows PostgreSQL access (port 5432) from whitelisted IPs only
- Instance is publicly accessible for remote connections
- Uses default VPC or custom VPC as specified

## Estimated Costs

### Free Tier (First 12 Months)
- **Instance**: 750 hours/month of db.t3.micro (100% free if single instance)
- **Storage**: 20 GB General Purpose (SSD) storage (free)
- **Backups**: 20 GB backup storage (free)
- **Total**: $0/month within free tier limits

### After Free Tier or Over Limits
Approximate monthly cost for 1x db.t3.micro instance in ap-south-1:
- **Instance**: ~$13-15 USD/month (db.t3.micro on-demand)
- **Storage (GP3)**: ~$2.30/month for 20 GB ($0.115 per GB-month)
- **Backup storage**: Free up to database size, then $0.095 per GB-month
- **Data transfer**: $0.09 per GB out to internet
- **Total**: ~$15-20 USD/month

### Cost Comparison
- **RDS PostgreSQL (db.t3.micro)**: ~$15-20/month
- **Aurora PostgreSQL (db.t3.medium)**: ~$60-70/month
- **Savings**: ~75% cheaper than Aurora

**Cost Saving Tips:**
- Keep within free tier limits (first 12 months)
- Stop the instance when not in use (saves compute, storage still charged)
- Delete unused snapshots regularly
- Monitor usage with AWS Cost Explorer
- Use GP3 storage instead of GP2 (better price/performance)
- Disable Multi-AZ for non-production workloads

## Support

For AWS RDS documentation, visit:
- [RDS PostgreSQL Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [AWS Free Tier](https://aws.amazon.com/free/)
- [RDS Pricing](https://aws.amazon.com/rds/postgresql/pricing/)
