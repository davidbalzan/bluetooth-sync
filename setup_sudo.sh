#!/bin/bash
# Setup script to install dependencies for sudo execution

echo "🔧 Setting up Bluetooth Sync Utility for sudo execution..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "❌ This setup script needs to be run as root (with sudo)."
    echo "Usage: sudo ./setup_sudo.sh"
    exit 1
fi

# Install system-wide dependencies
echo "📦 Installing python-registry system-wide..."

# Update package manager and install pip if needed
if command -v apt &> /dev/null; then
    apt update -qq
    apt install -y python3-pip
elif command -v dnf &> /dev/null; then
    dnf install -y python3-pip
elif command -v yum &> /dev/null; then
    yum install -y python3-pip
elif command -v pacman &> /dev/null; then
    pacman -S --noconfirm python-pip
else
    echo "❌ Unsupported package manager. Please install python3-pip manually."
    exit 1
fi

# Install python-registry system-wide
pip3 install python-registry==1.3.1

echo "✅ System-wide setup complete!"
echo ""
echo "📖 You can now use the utility in these ways:"
echo "   sudo python3 bt_sync.py           # Direct system Python"
echo "   sudo ./bt-sync                    # Wrapper script (recommended)"
echo ""
echo "🎯 The wrapper script will automatically handle environment setup."
