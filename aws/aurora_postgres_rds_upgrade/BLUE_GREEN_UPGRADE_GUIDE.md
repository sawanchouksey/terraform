# Blue/Green Deployment - PostgreSQL Major Version Upgrade Guide

## Overview

This guide walks you through upgrading your RDS PostgreSQL database from **version 14.17 to 16.x** using AWS RDS Blue/Green deployments with **zero downtime**.

## What is Blue/Green Deployment?

Blue/Green deployment creates a **staging environment (Green)** that mirrors your **production database (Blue)**:
- **Blue Environment**: Your current production database (PostgreSQL 14.17)
- **Green Environment**: A copy of your database upgraded to PostgreSQL 16.x
- **Switchover**: Promotes Green to production with minimal downtime (typically < 1 minute)

## Benefits

✅ **Near-Zero Downtime**: < 1 minute downtime during switchover
✅ **Safe Testing**: Test the upgrade in Green environment before switching
✅ **Easy Rollback**: Can switch back to Blue if issues are found
✅ **Automatic Replication**: Blue to Green stays in sync until switchover
✅ **No Data Loss**: Uses binary log replication

## Prerequisites

### 1. Verify Current Database Version

```powershell
aws rds describe-db-instances `
    --db-instance-identifier postgres-rds-instance `
    --region ap-south-1 `
    --query 'DBInstances[0].[EngineVersion,DBInstanceStatus]' `
    --output table
```

### 2. Check Compatibility

```sql
-- Connect to your database and run:
SELECT version();

-- Check for extensions that need upgrading
SELECT * FROM pg_available_extensions WHERE installed_version IS NOT NULL;

-- Check for deprecated features
-- Review PostgreSQL 16 release notes for breaking changes
```

### 3. Backup Your Database

```powershell
# Create a manual snapshot before starting
aws rds create-db-snapshot `
    --db-instance-identifier postgres-rds-instance `
    --db-snapshot-identifier postgres-pre-upgrade-$(Get-Date -Format 'yyyy-MM-dd-HHmm') `
    --region ap-south-1
```

## Step-by-Step Upgrade Process

### Phase 1: Enable Blue/Green Deployment

#### Step 1.1: Update terraform.tfvars

```hcl
# Enable Blue/Green deployment
enable_blue_green_upgrade = true

# Target PostgreSQL version
target_engine_version = "16.1"  # or latest 16.x version

# Optional: Upgrade instance class during migration
# target_instance_class = "db.t3.small"
```

#### Step 1.2: Apply Terraform Configuration

```powershell
# Navigate to project directory
cd "C:\Users\sachouk\OneDrive - Mercedes-Benz (corpdir.onmicrosoft.com)\Documents\docs\code\auroraRdsPostgresUpgrade"

# Review changes
terraform plan

# Apply the blue/green deployment
terraform apply

# Expected output:
# - Creates PostgreSQL 16 parameter group
# - Creates Blue/Green deployment
# - Starts creating Green environment
```

#### Step 1.3: Monitor Deployment Creation

```powershell
# Check deployment status
aws rds describe-blue-green-deployments `
    --blue-green-deployment-identifier <deployment-id-from-terraform-output> `
    --region ap-south-1

# Or using Terraform output
terraform output blue_green_deployment_status

# Wait for status to become: AVAILABLE
# This typically takes 15-30 minutes
```

### Phase 2: Test Green Environment

#### Step 2.1: Get Green Environment Endpoint

```powershell
# Get the Green environment endpoint
terraform output green_environment_endpoint

# Or via AWS CLI
aws rds describe-blue-green-deployments `
    --blue-green-deployment-identifier <deployment-id> `
    --region ap-south-1 `
    --query 'BlueGreenDeployments[0].Target.Endpoint' `
    --output text
```

#### Step 2.2: Test Application Connectivity

```powershell
# Test connection to Green environment
python test_rds_connection.py

# Update the host in test script to Green endpoint temporarily
# Or use psql directly:
psql -h <green-endpoint> -U postgres -d myappdb -p 5432

# Verify version
SELECT version();
# Should show: PostgreSQL 16.x
```

#### Step 2.3: Run Application Tests

```powershell
# Test your application against Green environment
# Update your application config to point to Green endpoint

# Run comprehensive tests:
# 1. Read/Write operations
# 2. Query performance
# 3. Extension compatibility
# 4. Application functionality

# Example: Run failover tester against Green
python rds_postgres_testing_failover.py `
    --host <green-endpoint> `
    --user postgres `
    --password "Practice`$123#Rds" `
    --database myappdb `
    --port 5432 `
    --threads 2 `
    --sslmode require
```

#### Step 2.4: Performance Benchmarking

```sql
-- Run performance tests on Green environment
EXPLAIN ANALYZE SELECT * FROM your_table WHERE condition;

-- Compare query plans between Blue and Green
-- Check for any performance regressions
```

### Phase 3: Switchover to Green (Production Cutover)

⚠️ **WARNING**: This step promotes Green to production. Ensure all testing is complete!

#### Step 3.1: Pre-Switchover Checklist

- [ ] All application tests passed on Green environment
- [ ] Performance benchmarks acceptable
- [ ] Team notified of switchover window
- [ ] Rollback plan documented
- [ ] Database backup verified

#### Step 3.2: Perform Switchover

**Option A: Using AWS CLI**

```powershell
# Switchover with timeout (recommended: 300 seconds = 5 minutes)
aws rds switchover-blue-green-deployment `
    --blue-green-deployment-identifier <deployment-id> `
    --switchover-timeout 300 `
    --region ap-south-1

# Monitor switchover progress
aws rds describe-blue-green-deployments `
    --blue-green-deployment-identifier <deployment-id> `
    --region ap-south-1 `
    --query 'BlueGreenDeployments[0].Status'
```

**Option B: Using AWS Console**
1. Navigate to RDS → Blue/Green Deployments
2. Select your deployment
3. Click "Switch over"
4. Confirm the action

#### Step 3.3: Verify Switchover

```powershell
# Check current database version (should now be 16.x)
aws rds describe-db-instances `
    --db-instance-identifier postgres-rds-instance `
    --region ap-south-1 `
    --query 'DBInstances[0].EngineVersion' `
    --output text

# Test application connectivity
python test_rds_connection.py

# Verify endpoint hasn't changed
terraform output db_instance_endpoint
```

#### Step 3.4: Monitor Application

```powershell
# Monitor application logs
# Check for any errors or warnings

# Monitor RDS metrics in CloudWatch
aws cloudwatch get-metric-statistics `
    --namespace AWS/RDS `
    --metric-name DatabaseConnections `
    --dimensions Name=DBInstanceIdentifier,Value=postgres-rds-instance `
    --start-time $(Get-Date).AddHours(-1).ToString("yyyy-MM-ddTHH:mm:ss") `
    --end-time $(Get-Date).ToString("yyyy-MM-ddTHH:mm:ss") `
    --period 300 `
    --statistics Average `
    --region ap-south-1
```

### Phase 4: Cleanup

#### Step 4.1: Delete Blue/Green Deployment

After confirming everything works in production:

**Option 1: Keep Blue Environment (Recommended for 24-48 hours)**
```powershell
# Monitor production for 1-2 days before cleanup
# Blue environment continues to exist for quick rollback
```

**Option 2: Delete Blue Environment**

⚠️ **WARNING**: This deletes the old database. Cannot rollback after this!

```powershell
# Delete the Blue/Green deployment (and old Blue environment)
aws rds delete-blue-green-deployment `
    --blue-green-deployment-identifier <deployment-id> `
    --delete-target `
    --region ap-south-1

# Or update terraform.tfvars
enable_blue_green_upgrade = false

# Then run
terraform apply
```

#### Step 4.2: Update Terraform State

```powershell
# Update terraform.tfvars to reflect new version
engine_version = "16.1"

# Disable blue/green deployment
enable_blue_green_upgrade = false

# Apply changes
terraform apply
```

## Rollback Procedure

If issues are discovered **before switchover**:
1. Simply delete the Blue/Green deployment
2. Green environment is removed
3. Blue (production) remains untouched

If issues are discovered **after switchover**:

### Option 1: Switch Back (Within retention period)

```powershell
# Create reverse Blue/Green deployment
aws rds create-blue-green-deployment `
    --blue-green-deployment-name postgres-rollback `
    --source postgres-rds-instance `
    --target-engine-version 14.17 `
    --region ap-south-1

# After Green is ready, switchover back
aws rds switchover-blue-green-deployment `
    --blue-green-deployment-identifier <new-deployment-id> `
    --switchover-timeout 300 `
    --region ap-south-1
```

### Option 2: Restore from Snapshot

```powershell
# List available snapshots
aws rds describe-db-snapshots `
    --db-instance-identifier postgres-rds-instance `
    --region ap-south-1 `
    --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime]' `
    --output table

# Restore from pre-upgrade snapshot
aws rds restore-db-instance-from-db-snapshot `
    --db-instance-identifier postgres-rds-instance-restored `
    --db-snapshot-identifier postgres-pre-upgrade-<timestamp> `
    --region ap-south-1
```

## Monitoring During Upgrade

### Key Metrics to Watch

```powershell
# CPU Utilization
aws cloudwatch get-metric-statistics `
    --namespace AWS/RDS `
    --metric-name CPUUtilization `
    --dimensions Name=DBInstanceIdentifier,Value=postgres-rds-instance `
    --start-time $(Get-Date).AddHours(-1).ToString("yyyy-MM-ddTHH:mm:ss") `
    --end-time $(Get-Date).ToString("yyyy-MM-ddTHH:mm:ss") `
    --period 300 `
    --statistics Average Maximum `
    --region ap-south-1

# Database Connections
# Free Storage Space
# Read/Write IOPS
# Replication Lag (between Blue and Green)
```

## Common Issues and Solutions

### Issue 1: Blue/Green Deployment Stuck in "Creating"

**Solution:**
- Check CloudWatch logs for errors
- Verify sufficient storage space
- Ensure parameter group is compatible with PostgreSQL 16

### Issue 2: Switchover Timeout

**Solution:**
- Increase switchover timeout (default: 300 seconds)
- Reduce write traffic during switchover
- Check for long-running transactions

### Issue 3: Extension Compatibility

**Solution:**
```sql
-- Update extensions after upgrade
ALTER EXTENSION extension_name UPDATE;

-- Check extension versions
SELECT * FROM pg_available_extensions;
```

### Issue 4: Performance Regression

**Solution:**
- Update table statistics: `ANALYZE;`
- Rebuild indexes if needed
- Check for new PostgreSQL 16 configuration tuning opportunities

## Cost Considerations

- **During Blue/Green**: Pay for both Blue and Green instances
- **Typical Duration**: 15-30 minutes for Green creation + testing time
- **Estimated Cost**: ~$15-30 (if testing for 1-2 days with db.t3.micro)
- **Recommendation**: Delete Blue environment after 24-48 hours of stable operation

## Best Practices

1. ✅ **Test First**: Always test in non-production environment first
2. ✅ **Off-Peak Hours**: Schedule switchover during low-traffic periods
3. ✅ **Communication**: Notify stakeholders of maintenance window
4. ✅ **Monitoring**: Have monitoring dashboard ready during switchover
5. ✅ **Backup**: Always create manual snapshot before upgrade
6. ✅ **Documentation**: Document any application changes needed
7. ✅ **Gradual Rollout**: Consider testing with subset of users first

## PostgreSQL 14 to 16 Breaking Changes

Review these potential compatibility issues:

1. **Removed Features**: Check PostgreSQL 16 release notes
2. **Deprecated Functions**: Update application code if needed
3. **Configuration Changes**: Some parameters may have different defaults
4. **Extension Updates**: Update all extensions to compatible versions

## Timeline Example

| Time | Activity | Duration |
|------|----------|----------|
| T+0 | Create snapshot & start Blue/Green | 5 min |
| T+5 | Wait for Green environment | 15-30 min |
| T+35 | Test Green environment | 2-24 hours |
| T+36 | Switchover | 1-5 min |
| T+41 | Verify & monitor | 2-4 hours |
| T+45 | Normal operations | - |
| T+48h | Delete Blue environment | 5 min |

## Support Resources

- [AWS RDS Blue/Green Deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/blue-green-deployments.html)
- [PostgreSQL 16 Release Notes](https://www.postgresql.org/docs/16/release-16.html)
- [PostgreSQL Upgrade Documentation](https://www.postgresql.org/docs/current/upgrading.html)

## Quick Reference Commands

```powershell
# Enable upgrade
terraform apply

# Check status
terraform output blue_green_deployment_status

# Get Green endpoint
terraform output green_environment_endpoint

# Switchover
aws rds switchover-blue-green-deployment --blue-green-deployment-identifier <id> --switchover-timeout 300 --region ap-south-1

# Cleanup
terraform apply  # after setting enable_blue_green_upgrade = false
```
