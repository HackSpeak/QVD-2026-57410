#!/bin/bash
# Quick installation script for DSH Exploit Toolkit

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   DeepSeek Harness RCE Exploit Toolkit - Setup              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "[*] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "[+] Found Python $PYTHON_VERSION"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "[!] pip3 is not installed. Please install pip3."
    exit 1
fi

# Install dependencies
echo "[*] Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "[+] Dependencies installed successfully"
else
    echo "[!] Failed to install dependencies"
    exit 1
fi

# Make scripts executable
echo "[*] Making scripts executable..."
chmod +x dsh_exploit.py dsh_scanner.py dsh_shell.py

echo ""
echo "[+] Setup complete!"
echo ""
echo "Usage examples:"
echo "  ./dsh_exploit.py -t http://target:3000 --check"
echo "  ./dsh_scanner.py -f targets.txt"
echo "  ./dsh_shell.py -t http://target:3000"
echo ""
echo "See README.md for detailed documentation."
