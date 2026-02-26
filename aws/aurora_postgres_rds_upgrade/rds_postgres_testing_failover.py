"""
Aurora PostgreSQL Failover Downtime Tester
Tests and measures downtime during Aurora PostgreSQL cluster failover

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
import json
import os
from pathlib import Path
import getpass

# Platform-specific imports for password masking with asterisks
if sys.platform == 'win32':
    import msvcrt
else:
    import termios
    import tty

# Platform-specific imports for password masking with asterisks
if sys.platform == 'win32':
    import msvcrt
else:
    import termios
    import tty

def getpass_with_asterisks(prompt="Password: "):
    """
    Get password input with asterisks (*) shown for each character.
    Works on both Windows and Unix-like systems.
    
    Args:
        prompt: The prompt to display
    
    Returns:
        The entered password as a string
    """
    print(prompt, end='', flush=True)
    password = ""
    
    if sys.platform == 'win32':
        # Windows implementation using msvcrt
        while True:
            char = msvcrt.getch()
            
            if char in (b'\r', b'\n'):  # Enter key
                print()  # New line
                break
            elif char == b'\x08':  # Backspace
                if len(password) > 0:
                    password = password[:-1]
                    # Erase the last asterisk
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif char == b'\x03':  # Ctrl+C
                print()
                raise KeyboardInterrupt
            else:
                # Add character to password
                try:
                    password += char.decode('utf-8')
                    sys.stdout.write('*')
                    sys.stdout.flush()
                except UnicodeDecodeError:
                    pass  # Ignore non-UTF8 characters
    else:
        # Unix-like systems implementation
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                char = sys.stdin.read(1)
                
                if char in ('\r', '\n'):
                    print()
                    break
                elif char == '\x7f':  # Backspace (DEL key on Unix)
                    if len(password) > 0:
                        password = password[:-1]
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                elif char == '\x03':  # Ctrl+C
                    print()
                    raise KeyboardInterrupt
                else:
                    password += char
                    sys.stdout.write('*')
                    sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    return password

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

        # ── Attempt log (shared; protected by self.lock) ────────────────────
        self.attempts = deque(maxlen=10000)
        self.running = True
        self.lock = threading.Lock()

        # ── Downtime tracking ────────────────────────────────────────────────
        # last_success_time  – wall-clock time of the most recent successful
        #                      connection across ALL worker threads.
        self.last_success_time = datetime.now()

        # outage_in_progress – True while no thread has connected since the
        #                      outage was declared by health_monitor_thread.
        self.outage_in_progress = False

        # outage_start_time  – timestamp of the first failure that opened the
        #                      current outage (back-dated by health monitor).
        self.outage_start_time = None

        # downtime_periods   – list of (start, end, duration) for every
        #                      completed outage; populated on recovery.
        self.downtime_periods = []

        # total_downtime     – cumulative sum of all completed outage durations.
        self.total_downtime = timedelta(0)

        # outage_count       – number of distinct outages detected.
        self.outage_count = 0

        # ── Warmup ───────────────────────────────────────────────────────────
        # Tunnel warmup causes harmless failures in the first few seconds.
        # Outage detection is suppressed until this timestamp.
        self.warmup_until = None  # Set in run() after initial connection

        # ── Counters ─────────────────────────────────────────────────────────
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
                connect_timeout=5,
                sslmode=self.sslmode,
                options='-c statement_timeout=5000'  # 5 second statement timeout
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
        """
        Worker thread: fire connection attempts continuously.

        Responsibilities (intentionally minimal):
          - Append every attempt to self.attempts.
          - On success: update last_success_time; close any in-progress outage.
          - On failure: increment counter only.

        Outage START detection is delegated entirely to health_monitor_thread
        to avoid the per-thread consecutive-failure race condition that caused
        false positives (one thread succeeding while others still fail would
        flip the shared state back to "healthy" mid-outage).
        """
        while self.running:
            attempt = self.test_connection(thread_id)

            with self.lock:
                self.attempts.append(attempt)
                self.total_attempts += 1

                if attempt.success:
                    self.successful_attempts += 1

                    # ── Recovery: first thread to succeed closes the outage ──
                    if self.outage_in_progress:
                        end_time = attempt.timestamp
                        duration = end_time - self.outage_start_time
                        self.downtime_periods.append((
                            self.outage_start_time,
                            end_time,
                            duration,
                        ))
                        self.total_downtime += duration
                        self.outage_in_progress = False
                        self.outage_start_time = None

                    self.last_success_time = attempt.timestamp
                else:
                    self.failed_attempts += 1

            time.sleep(0.1)  # 100 ms between attempts per thread

    def health_monitor_thread(self):
        """
        Single-thread outage detector — avoids the per-thread
        consecutive-failure race condition.

        Algorithm
        ─────────
        Every CHECK_INTERVAL seconds:
          1. Compute gap = now − last_success_time  (all workers update this).
          2. If gap ≥ OUTAGE_THRESHOLD and not already in an outage, declare one.
          3. Back-date outage_start_time to the first failure recorded after
             last_success_time, giving accurate wall-clock downtime figures.
          4. Outage END is handled by the first worker_thread that reconnects.

        Tuning notes
        ────────────
        OUTAGE_THRESHOLD should be slightly above connect_timeout (currently 5 s)
        so that a single slow connection never triggers a false alarm.
        """
        OUTAGE_THRESHOLD = 8.0   # seconds without any success → declare outage
        CHECK_INTERVAL   = 0.25  # seconds between health checks

        while self.running:
            time.sleep(CHECK_INTERVAL)

            with self.lock:
                if self.outage_in_progress:
                    continue  # Already tracking; worker_thread closes it on recovery

                # Skip detection during tunnel warmup period
                if self.warmup_until and datetime.now() < self.warmup_until:
                    continue

                gap = (datetime.now() - self.last_success_time).total_seconds()
                if gap < OUTAGE_THRESHOLD:
                    continue  # Still healthy

                # ── Declare outage ──────────────────────────────────────────
                self.outage_in_progress = True
                self.outage_count += 1

                # Back-date to the first failure after the last known-good success
                last_good = self.last_success_time
                failures_after = [
                    a for a in self.attempts
                    if not a.success and a.timestamp > last_good
                ]
                self.outage_start_time = (
                    min(a.timestamp for a in failures_after)
                    if failures_after
                    else last_good  # fallback (should rarely happen)
                )

    def print_status(self):
        """Print a rolling one-line status update every second."""
        while self.running:
            time.sleep(1)

            with self.lock:
                if not self.attempts:
                    continue

                now = datetime.now()
                recent = [a for a in self.attempts
                          if (now - a.timestamp).total_seconds() <= 1.0]
                if not recent:
                    continue

                success_count = sum(1 for a in recent if a.success)
                fail_count    = len(recent) - success_count
                success_rate  = (success_count / len(recent)) * 100

                latencies = [a.latency_ms for a in recent if a.success and a.latency_ms]
                if latencies:
                    avg_latency = statistics.mean(latencies)
                    slowest     = max(latencies)
                else:
                    avg_latency = slowest = 0

                is_warmup = self.warmup_until and now < self.warmup_until

                status = f"[{now.strftime('%H:%M:%S')}] "
                status += f"Rate: {len(recent)}/s | "
                status += f"Success: {success_rate:.1f}% | "
                if avg_latency > 0:
                    status += f"Avg: {avg_latency:.0f}ms | Slowest: {slowest:.0f}ms | "
                status += f"Total: {self.total_attempts}"

                if is_warmup:
                    status += " | \U0001f504 WARMING UP (tunnel stabilising)"
                elif self.outage_in_progress and self.outage_start_time:
                    elapsed = (now - self.outage_start_time).total_seconds()
                    status += f" | \u26a0\ufe0f  OUTAGE #{self.outage_count}: {elapsed:.1f}s"
                elif fail_count > 0:
                    status += f" | \u26a1 {fail_count}/{len(recent)} slow/failed (tunnel jitter)"
                else:
                    status += " | \u2705 HEALTHY"

                print(status)
    
    def run(self):
        """Start the failover test"""
        print(f"\n{'='*60}")
        print(f"Aurora PostgreSQL Failover Tester")
        print(f"{'='*60}")
        print(f"Target: {self.host}:{self.port}/{self.database}")
        print(f"Threads: {self.threads}")
        print(f"Testing initial connection...")
        
        # Retry initial connection for up to 30 seconds
        max_wait = 30
        start = time.time()
        attempt = None
        while time.time() - start < max_wait:
            attempt = self.test_connection(0)
            if attempt.success:
                break
            elapsed = time.time() - start
            remaining = max_wait - elapsed
            if remaining <= 0:
                break
            print(f"  ⏳ Connection failed ({attempt.error_msg[:60]}), retrying... "
                  f"({remaining:.0f}s remaining)")
            time.sleep(2)

        if not attempt or not attempt.success:
            print(f"❌ Could not connect after {max_wait}s: {attempt.error_msg if attempt else 'unknown'}")
            print("Please check your connection parameters and try again.")
            return

        print(f"✅ Initial connection successful (latency: {attempt.latency_ms:.0f}ms)")

        # Give the tunnel 10 seconds to stabilise before counting failures
        WARMUP_SECONDS = 10
        self.warmup_until = datetime.now() + timedelta(seconds=WARMUP_SECONDS)
        self.last_success_time = datetime.now()  # Reset so warmup failures don't trigger outage

        print(f"Starting continuous connection tests...")
        print(f"Tunnel warmup grace period : {WARMUP_SECONDS}s (failures ignored)")
        print(f"Outage detection threshold : 8s without any successful connection")
        print(f"Results are consolidated at end — no mid-run outage banners")
        print(f"{'='*60}\n")
        print("Press Ctrl+C to stop\n")

        # Start worker threads
        workers = []
        for i in range(self.threads):
            t = threading.Thread(target=self.worker_thread, args=(i,), daemon=True)
            t.start()
            workers.append(t)

        # Start the single outage-detector thread
        hm_thread = threading.Thread(target=self.health_monitor_thread, daemon=True)
        hm_thread.start()

        # Start status printer
        status_thread = threading.Thread(target=self.print_status, daemon=True)
        status_thread.start()

        # Wait for interrupt
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\nStopping test...")
            self.running = False
            time.sleep(1)  # Let threads finish current attempts

            self.print_summary()
    
    def print_summary(self):
        """
        Print the consolidated final report.
        All outage data is shown here — nothing is printed mid-run.
        If an outage was still in progress when Ctrl+C was pressed it is
        closed at the stop time and included in the report.
        """
        # ── Close any open outage ──────────────────────────────────────────
        if self.outage_in_progress and self.outage_start_time:
            end_time = datetime.now()
            duration = end_time - self.outage_start_time
            self.downtime_periods.append((self.outage_start_time, end_time, duration))
            self.total_downtime += duration
            self.outage_in_progress = False

        print(f"\n{'='*60}")
        print(f"FINAL SUMMARY")
        print(f"{'='*60}")

        if self.total_attempts == 0:
            print("No attempts recorded.")
            print(f"{'='*60}\n")
            return

        print(f"Total Attempts : {self.total_attempts}")
        print(f"Successful     : {self.successful_attempts}"
              f" ({self.successful_attempts / self.total_attempts * 100:.1f}%)")
        print(f"Failed         : {self.failed_attempts}"
              f" ({self.failed_attempts / self.total_attempts * 100:.1f}%)")

        # ── Outage table ───────────────────────────────────────────────────
        if self.downtime_periods:
            durations = [p[2].total_seconds() for p in self.downtime_periods]
            total_s   = self.total_downtime.total_seconds()

            print(f"\n{'-'*60}")
            print(f"OUTAGE REPORT  ({len(self.downtime_periods)} outage(s) detected)")
            print(f"{'-'*60}")
            print(f"  Total cumulative downtime : {total_s:.3f} s")
            print(f"  Shortest outage           : {min(durations):.3f} s")
            print(f"  Longest outage            : {max(durations):.3f} s")
            print(f"  Average outage            : {statistics.mean(durations):.3f} s")
            if len(durations) > 1:
                print(f"  Median outage             : {statistics.median(durations):.3f} s")

            print(f"\n  {'#':<4} {'Start':<16} {'End':<16} {'Duration':>12}")
            print(f"  {'─'*56}")
            for i, (start, end, dur) in enumerate(self.downtime_periods, 1):
                print(
                    f"  {i:<4} "
                    f"{start.strftime('%H:%M:%S.%f')[:-3]:<16} "
                    f"{end.strftime('%H:%M:%S.%f')[:-3]:<16} "
                    f"{dur.total_seconds():>10.3f} s"
                )
            print(f"  {'─'*56}")
        else:
            print(f"\n✅ No outages detected during test")

        # ── Latency ────────────────────────────────────────────────────────
        all_latencies = [a.latency_ms for a in self.attempts if a.success and a.latency_ms]
        if all_latencies:
            print(f"\n{'-'*60}")
            print(f"LATENCY  (successful connections)")
            print(f"{'-'*60}")
            sorted_lat = sorted(all_latencies)
            print(f"  Fastest  : {sorted_lat[0]:.0f} ms")
            print(f"  Average  : {statistics.mean(sorted_lat):.0f} ms")
            print(f"  Slowest  : {sorted_lat[-1]:.0f} ms")
            if len(sorted_lat) > 10:
                mid = sorted_lat[len(sorted_lat) // 2]
                worst1pct = sorted_lat[int(len(sorted_lat) * 0.99)]
                print(f"  Typical  : {mid:.0f} ms  (middle value)")
                print(f"  Worst 1% : {worst1pct:.0f} ms  (slowest 1 in 100)")

        # ── Error breakdown ────────────────────────────────────────────────
        error_counts = {}
        for a in self.attempts:
            if a.error_msg:
                key = a.error_msg[:120]
                error_counts[key] = error_counts.get(key, 0) + 1

        if error_counts:
            print(f"\n{'-'*60}")
            print(f"ERROR BREAKDOWN")
            print(f"{'-'*60}")
            for msg, count in sorted(error_counts.items(), key=lambda x: -x[1]):
                print(f"  [{count:>5}x]  {msg}")

        print(f"\n{'='*60}\n")

def load_credentials_from_json(env=None, creds_file='creds.json'):
    """
    Load database credentials from JSON file based on environment
    Note: Password is NOT loaded from JSON for security reasons - it will be prompted
    
    Args:
        env: Environment name (dev, int, prod) or None for manual entry
        creds_file: Path to credentials JSON file
    
    Returns:
        dict with keys: host, user, database, port, sslmode (password excluded)
    """
    creds = {}
    
    # Try to load from JSON file if env is provided
    if env:
        creds_path = Path(creds_file)
        
        if creds_path.exists():
            try:
                with open(creds_path, 'r') as f:
                    all_creds = json.load(f)
                
                if env in all_creds:
                    env_creds = all_creds[env].copy()
                    # Remove password from JSON if present (for security)
                    env_creds.pop('password', None)
                    print(f"✅ Loaded credentials for environment: {env}")
                    return env_creds
                else:
                    print(f"⚠️  Environment '{env}' not found in {creds_file}")
                    print(f"Available environments: {', '.join(all_creds.keys())}")
                    print("Falling back to manual entry...\n")
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing {creds_file}: {e}")
                print("Falling back to manual entry...\n")
            except Exception as e:
                print(f"❌ Error reading {creds_file}: {e}")
                print("Falling back to manual entry...\n")
        else:
            print(f"⚠️  Credentials file '{creds_file}' not found")
            print("Falling back to manual entry...\n")
    
    # Manual entry
    print("Please enter database connection details:")
    creds['host'] = input("Host: ").strip()
    creds['user'] = input("Username: ").strip()
    creds['database'] = input("Database: ").strip()
    creds['port'] = int(input("Port [5432]: ").strip() or "5432")
    creds['sslmode'] = input("SSL Mode [require]: ").strip() or "require"
    
    return creds

def main():
    parser = argparse.ArgumentParser(
        description='Test Aurora PostgreSQL failover downtime',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment from creds.json
  python %(prog)s dev
  python %(prog)s int --threads 2
  
  # Manual entry (no environment specified)
  python %(prog)s
  
  # Override specific parameters
  python %(prog)s dev --port 5432
  
  # Full manual specification
  python %(prog)s --host myhost --user myuser --database mydb
        """)
    
    # Positional argument for environment
    parser.add_argument('env', nargs='?', choices=['dev', 'int', 'prod'], 
                       help='Environment to load from creds.json (dev, int, prod). If not specified, manual entry will be prompted.')
    
    # Credentials file option
    parser.add_argument('--creds-file', default='creds.json',
                       help='Path to credentials JSON file (default: creds.json)')
    
    # Connection parameters (optional if using env)
    parser.add_argument('--host', help='Aurora cluster endpoint')
    parser.add_argument('--user', help='Database username')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--port', type=int, help='Database port (default: 5432)')
    
    # Test configuration
    parser.add_argument('--threads', type=int, default=5, 
                       help='Number of test threads (default: 5)')
    
    # PostgreSQL specific options
    parser.add_argument('--sslmode', 
                       choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full'],
                       help='SSL mode for connection (default: require)')
    
    args = parser.parse_args()
    
    # Load credentials from JSON or manual entry (excludes password)
    creds = load_credentials_from_json(args.env, args.creds_file)
    
    # Override with command-line arguments if provided
    host = args.host or creds.get('host')
    user = args.user or creds.get('user')
    database = args.database or creds.get('database')
    port = args.port or creds.get('port', 5432)
    sslmode = args.sslmode or creds.get('sslmode', 'require')
    
    # Validate required parameters (except password)
    if not all([host, user, database]):
        print("\n❌ Error: Missing required connection parameters")
        print("Please provide either --env or all connection parameters (--host, --user, --database)")
        sys.exit(1)
    
    # Always prompt for password (unless provided via command line for automation)
    if args.password:
        password = args.password
    else:
        print(f"\nConnecting to: {user}@{host}:{port}/{database}")
        password = getpass_with_asterisks(f"Enter password for {user}: ")
    
    if not password:
        print("\n❌ Error: Password is required")
        sys.exit(1)
    
    tester = FailoverTester(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        threads=args.threads,
        sslmode=sslmode
    )
    
    tester.run()

if __name__ == '__main__':
    main()
 
