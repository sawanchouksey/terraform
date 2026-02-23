#!/usr/bin/env python3
"""
Simple RDS PostgreSQL Connection Test
Tests basic connectivity to RDS instance
"""

import psycopg2
import sys

def test_connection():
    conn_params = {
        'host': 'postgres-rds-instance.cpmpdmefjobs.ap-south-1.rds.amazonaws.com',
        'port': 5432,
        'database': 'myappdb',
        'user': 'postgres',
        'password': 'Practice$123#Rds',
        'connect_timeout': 10,
        'sslmode': 'require'  # Changed from 'disable' to 'require'
    }
    
    print("=" * 60)
    print("RDS PostgreSQL Connection Test")
    print("=" * 60)
    print(f"Host: {conn_params['host']}")
    print(f"Port: {conn_params['port']}")
    print(f"Database: {conn_params['database']}")
    print(f"User: {conn_params['user']}")
    print("-" * 60)
    
    try:
        print("\n🔄 Attempting to connect...")
        conn = psycopg2.connect(**conn_params)
        
        print("✅ Connection successful!")
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        print(f"\n📊 PostgreSQL Version:")
        print(version)
        
        # Get current database
        cursor.execute("SELECT current_database();")
        db = cursor.fetchone()[0]
        print(f"\n📁 Current Database: {db}")
        
        # List tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        tables = cursor.fetchall()
        
        print(f"\n📋 Tables in public schema:")
        if tables:
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("  (No tables found)")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection failed!")
        print(f"\nError details:")
        print(str(e))
        
        if "timeout" in str(e).lower():
            print("\n💡 Possible causes:")
            print("  1. Corporate firewall blocking port 5432")
            print("  2. Network connectivity issue")
            print("  3. Security group not allowing your IP")
            print("\n🔧 Solutions:")
            print("  - Try connecting from mobile hotspot")
            print("  - Check security group allows your IP")
            print("  - Use EC2 bastion host in same VPC")
        elif "password authentication failed" in str(e).lower():
            print("\n💡 Issue: Incorrect password")
        elif "database" in str(e).lower() and "does not exist" in str(e).lower():
            print("\n💡 Issue: Database name incorrect")
            print("   Try: 'postgres' instead of 'myappdb'")
        
        print("\n" + "=" * 60)
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
