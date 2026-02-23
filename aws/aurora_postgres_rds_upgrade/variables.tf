# RDS Connection Troubleshooting Guide

## Problem: Cannot Connect to RDS Instance

If you're getting connection timeouts or failures like:
```
❌ Initial connection failed: connection to server at "postgres-rds-instance..."
```

## Root Cause Analysis

### Verified Working Components ✅
- RDS instance status: **Available**
- RDS publicly accessible: **True**
- Security group: **Correctly configured** (allows 0.0.0.0/0 on port 5432)
- Your IP: **163.116.219.95** (whitelisted)
- Subnet configuration: **Public subnet with internet gateway**

### Identified Issue ❌
**Corporate firewall blocking outbound port 5432**

## Solutions

### Solution 1: Connect from Different Network (Recommended for Testing)

Try connecting from:
- **Mobile hotspot** (bypasses corporate network)
- **Home network** (if not using corporate VPN)
- **Cloud-based environment** (AWS Cloud9, EC2 instance)

### Solution 2: Use AWS Systems Manager Session Manager

Connect via SSM without opening any ports:

```powershell
# Create an EC2 bastion instance (if you don't have one)
# Then use Session Manager to connect

# Install PostgreSQL client on bastion
sudo yum install postgresql15 -y

# Connect to RDS from bastion
psql -h postgres-rds-instance.cpmpdmefjobs.ap-south-1.rds.amazonaws.com \
     -U postgres \
     -d myappdb \
     -p 5432
```

### Solution 3: Use AWS Cloud9 IDE

1. Create Cloud9 environment in same VPC
2. Cloud9 has PostgreSQL tools pre-installed
3. Connect from Cloud9 terminal

### Solution 4: Request Firewall Exception

Contact your IT/Network team to:
- Allow outbound connections to: `postgres-rds-instance.cpmpdmefjobs.ap-south-1.rds.amazonaws.com`
- On port: `5432`
- Protocol: `TCP`

### Solution 5: Create EC2 Bastion Host

```bash
# Launch EC2 instance in same VPC
aws ec2 run-instances \
    --image-id ami-0dee22c13ea7a9a67 \
    --instance-type t2.micro \
    --key-name your-key-pair \
    --security-group-ids sg-04573b5eacdb29fc6 \
    --subnet-id subnet-00e8284becb87672b \
    --region ap-south-1

# SSH to EC2 instance
ssh -i your-key.pem ec2-user@<ec2-public-ip>

# Install PostgreSQL client
sudo yum install postgresql15 -y

# Connect to RDS
psql -h postgres-rds-instance.cpmpdmefjobs.ap-south-1.rds.amazonaws.com -U postgres -d myappdb
```

## Quick Connection Test from Mobile Hotspot

If you have mobile data:

1. **Connect to mobile hotspot**
2. **Run the test again:**

```powershell
python rds_postgres_testing_failover.py `
    --host postgres-rds-instance.cpmpdmefjobs.ap-south-1.rds.amazonaws.com `
    --user postgres `
    --password "Practice`$123#Rds" `
    --database myappdb `
    --port 5432 `
    --thread 2 `
    --sslmode disable
```

## Verify Network Connectivity

### Test 1: Check DNS Resolution
```powershell
nslookup postgres-rds-instance.cpmpdmefjobs.ap-south-1.rds.amazonaws.com
```

### Test 2: Check Port Connectivity
```powershell
Test-NetConnection -ComputerName postgres-rds-instance.cpmpdmefjobs.ap-south-1.rds.amazonaws.com -Port 5432
```

**Expected Result:**
- `TcpTestSucceeded : True` ✅

**Current Result:**
- `TcpTestSucceeded : False` ❌ (Corporate firewall blocking)

### Test 3: Check Firewall Rules
```powershell
# Check Windows Firewall
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*PostgreSQL*"}

# Check if port 5432 is blocked
Test-NetConnection -ComputerName 8.8.8.8 -Port 5432
```

## Security Group Cleanup (After Testing)

**IMPORTANT:** Remove the 0.0.0.0/0 rule after testing:

```powershell
# Remove the open rule
aws ec2 revoke-security-group-ingress `
    --group-id sg-04573b5eacdb29fc6 `
    --protocol tcp `
    --port 5432 `
    --cidr 0.0.0.0/0 `
    --region ap-south-1

# Keep only your specific IP
# (This should already exist: 163.116.219.95/32)
```

## Alternative: Use Private Connectivity

If you frequently need to access RDS from corporate network:

### Option 1: AWS VPN
- Set up Site-to-Site VPN between corporate network and VPC
- Access RDS via private IP

### Option 2: AWS Direct Connect
- Dedicated network connection from corporate office to AWS
- More expensive but better performance

### Option 3: Make RDS Private + Use VPN
```hcl
# Update terraform.tfvars
publicly_accessible = false

# Then use AWS VPN or Direct Connect to access
```

## Summary

**Root Cause:** Mercedes-Benz corporate firewall blocks outbound port 5432

**Quick Fix:** Use mobile hotspot or home network

**Long-term Fix:** 
1. Use EC2 bastion host in AWS
2. Request firewall exception from IT
3. Use AWS Systems Manager Session Manager
4. Set up VPN connection

## Next Steps

1. ✅ Try connecting from mobile hotspot to confirm RDS works
2. ✅ If successful, set up EC2 bastion or request firewall exception
3. ✅ Remove 0.0.0.0/0 from security group after testing
4. ✅ Configure proper access method for your environment
