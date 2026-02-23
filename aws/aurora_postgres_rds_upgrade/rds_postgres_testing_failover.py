#!/usr/bin/env python3
"""
Aurora PostgreSQL Failover Downtime Tester
Tests and measures downtime during Aurora PostgreSQL cluster failover

---------------------
Usage of script
---------------------
python rds_postgres_testing_failover.py --host postgres-rds-instance-green-oagatw.cpmpdmefjobs.ap-south-1.rds.amazonaws.com --user postgres --password "Practice`$123#Rds" --database myappdb --port 5432 --thread 2 --sslmode disable
"""

import time
import threading
import signal
import sys
from datetime import datetime, timedelta
from collections import deque
import psycopg2
from psycopg2 import OperationalError, Error
import argparse
from dataclasses import dataclass
from typing import Optional
import statistics

@dataclass
class ConnectionAttempt:
    timestamp: datetime
    success: bool
    latency_ms: Optional[float]
    error_msg: Optional[str]
    thread_id: int

class FailoverTester:
    def __init__(self, host, user, password, database, port=5432, threads=5, sslmode='require'):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.threads = threads
        self.sslmode = sslmode
        
        # Statistics tracking
        self.attempts = deque(maxlen=10000)
        self.running = True
        self.lock = threading.Lock()
        
        # Downtime tracking
        self.last_success = datetime.now()
        self.first_failure = None
        self.downtime_start = None
        self.downtime_end = None
        self.total_downtime = timedelta(0)
        
        # Statistics
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0
        
    def test_connection(self, thread_id):
        """Test a single database connection"""
        start_time = time.time()
        
        try:
            # Try to connect and run a simple query
            connection = psycopg2.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                connect_timeout=2,
                sslmode=self.sslmode,
                options='-c statement_timeout=2000'  # 2 second statement timeout
            )
            
            # Set autocommit for simple queries
            connection.autocommit = True
            
            with connection.cursor() as cursor:
                # Simple query to verify connection is working
                cursor.execute("SELECT 1 as health_check, NOW() as server_time, current_database(), version()")
                result = cursor.fetchone()
            
            connection.close()
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ConnectionAttempt(
                timestamp=datetime.now(),
                success=True,
                latency_ms=latency_ms,
                error_msg=None,
                thread_id=thread_id
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)[:100]  # Truncate long error messages
            
            return ConnectionAttempt(
                timestamp=datetime.now(),
                success=False,
                latency_ms=latency_ms,
                error_msg=error_msg,
                thread_id=thread_id
            )
    
    def worker_thread(self, thread_id):
        """Worker thread that continuously tests connections"""
        consecutive_failures = 0
        
        while self.running:
            attempt = self.test_connection(thread_id)
            
            with self.lock:
                self.attempts.append(attempt)
                self.total_attempts += 1
                
                if attempt.success:
                    self.successful_attempts += 1
                    consecutive_failures = 0
                    
                    # Track recovery from downtime
                    if self.downtime_start and not self.downtime_end:
                        self.downtime_end = attempt.timestamp
                        downtime_duration = self.downtime_end - self.downtime_start
                        self.total_downtime += downtime_duration
                        print(f"\n{'='*60}")
                        print(f"🔄 FAILOVER COMPLETED!")
                        print(f"Downtime Duration: {downtime_duration.total_seconds():.2f} seconds")
                        print(f"{'='*60}\n")
                    
                    self.last_success = attempt.timestamp
                    self.first_failure = None
                    self.downtime_start = None
                    self.downtime_end = None
                    
                else:
                    self.failed_attempts += 1
                    consecutive_failures += 1
                    
                    # Track start of downtime
                    if not self.first_failure:
                        self.first_failure = attempt.timestamp
                    
                    # Mark downtime start after 3 consecutive failures
                    if consecutive_failures == 3 and not self.downtime_start:
                        self.downtime_start = self.first_failure
                        print(f"\n{'='*60}")
                        print(f"⚠️  FAILOVER DETECTED at {self.downtime_start.strftime('%H:%M:%S.%f')[:-3]}")
                        print(f"Error: {attempt.error_msg}")
                        print(f"{'='*60}\n")
            
            # Sleep between attempts (adjust as needed)
            time.sleep(0.1)  # 100ms between attempts per thread
    
    def print_status(self):
        """Print current status and statistics"""
        while self.running:
            time.sleep(1)
            
            with self.lock:
                if not self.attempts:
                    continue
                
                # Calculate recent statistics (last 1 second)
                now = datetime.now()
                recent_attempts = [a for a in self.attempts 
                                 if (now - a.timestamp).total_seconds() <= 1]
                
                if recent_attempts:
                    success_count = sum(1 for a in recent_attempts if a.success)
                    fail_count = len(recent_attempts) - success_count
                    success_rate = (success_count / len(recent_attempts)) * 100
                    
                    # Calculate latencies for successful attempts
                    latencies = [a.latency_ms for a in recent_attempts 
                               if a.success and a.latency_ms]
                    
                    if latencies:
                        avg_latency = statistics.mean(latencies)
                        p99_latency = statistics.quantiles(latencies, n=100)[98] if len(latencies) > 10 else max(latencies)
                    else:
                        avg_latency = 0
                        p99_latency = 0
                    
                    # Build status line
                    status = f"[{now.strftime('%H:%M:%S')}] "
                    status += f"Rate: {len(recent_attempts)}/s | "
                    status += f"Success: {success_rate:.1f}% | "
                    
                    if avg_latency > 0:
                        status += f"Avg: {avg_latency:.1f}ms | "
                        status += f"P99: {p99_latency:.1f}ms | "
                    
                    status += f"Total: {self.total_attempts} "
                    
                    # Add failure indicator
                    if fail_count > 0:
                        status += f"| ❌ FAILURES: {fail_count}"
                        if self.downtime_start and not self.downtime_end:
                            duration = (now - self.downtime_start).total_seconds()
                            status += f" | DOWNTIME: {duration:.1f}s"
                    else:
                        status += "| ✅ HEALTHY"
                    
                    print(status)
    
    def run(self):
        """Start the failover test"""
        print(f"\n{'='*60}")
        print(f"Aurora PostgreSQL Failover Tester")
        print(f"{'='*60}")
        print(f"Target: {self.host}:{self.port}/{self.database}")
        print(f"Threads: {self.threads}")
        print(f"Testing initial connection...")
        
        # Test initial connection
        attempt = self.test_connection(0)
        if attempt.success:
            print(f"✅ Initial connection successful")
        else:
            print(f"❌ Initial connection failed: {attempt.error_msg}")
            print("Please check your connection parameters and try again.")
            return
        
        print(f"Starting continuous connection tests...")
        print(f"{'='*60}\n")
        print("Press Ctrl+C to stop\n")
        
        # Start worker threads
        workers = []
        for i in range(self.threads):
            t = threading.Thread(target=self.worker_thread, args=(i,))
            t.daemon = True
            t.start()
            workers.append(t)
        
        # Start status printer thread
        status_thread = threading.Thread(target=self.print_status)
        status_thread.daemon = True
        status_thread.start()
        
        # Wait for interrupt
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\nStopping test...")
            self.running = False
            time.sleep(2)  # Give threads time to finish
            
            self.print_summary()
    
    def print_summary(self):
        """Print final summary statistics"""
        print(f"\n{'='*60}")
        print(f"FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total Attempts: {self.total_attempts}")
        print(f"Successful: {self.successful_attempts} ({(self.successful_attempts/self.total_attempts*100):.1f}%)")
        print(f"Failed: {self.failed_attempts} ({(self.failed_attempts/self.total_attempts*100):.1f}%)")
        
        if self.total_downtime.total_seconds() > 0:
            print(f"\nTotal Downtime: {self.total_downtime.total_seconds():.2f} seconds")
        
        # Calculate latency statistics for all successful attempts
        all_latencies = [a.latency_ms for a in self.attempts 
                        if a.success and a.latency_ms]
        
        if all_latencies:
            print(f"\nLatency Statistics (successful connections):")
            print(f"  Min: {min(all_latencies):.1f}ms")
            print(f"  Avg: {statistics.mean(all_latencies):.1f}ms")
            print(f"  Max: {max(all_latencies):.1f}ms")
            if len(all_latencies) > 10:
                print(f"  P50: {statistics.median(all_latencies):.1f}ms")
                print(f"  P99: {statistics.quantiles(all_latencies, n=100)[98]:.1f}ms")
        
        # Show unique error messages
        error_messages = set(a.error_msg for a in self.attempts if a.error_msg)
        if error_messages:
            print(f"\nUnique Error Messages During Test:")
            for error in error_messages:
                print(f"  - {error}")
        
        print(f"{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description='Test Aurora PostgreSQL failover downtime')
    parser.add_argument('--host', required=True, help='Aurora cluster endpoint')
    parser.add_argument('--user', required=True, help='Database username')
    parser.add_argument('--password', required=True, help='Database password')
    parser.add_argument('--database', required=True, help='Database name')
    parser.add_argument('--port', type=int, default=5432, help='Database port (default: 5432)')
    parser.add_argument('--threads', type=int, default=5, help='Number of test threads (default: 5)')
    
    # PostgreSQL specific options
    parser.add_argument('--sslmode', default='require', 
                       choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full'],
                       help='SSL mode for connection (default: require)')
    
    args = parser.parse_args()
    
    tester = FailoverTester(
        host=args.host,
        user=args.user,
        password=args.password,
        database=args.database,
        port=args.port,
        threads=args.threads,
        sslmode=args.sslmode
    )
    
    tester.run()

if __name__ == '__main__':
    main()
	

 
