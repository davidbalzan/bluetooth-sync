#!/bin/bash
# Installation script for Bluetooth Synchronization Utility

set -e

echo "🔧 Installing Bluetooth Synchronization Utility..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "❌ Don't run this installer as root. Run normally and it will ask for sudo when needed."
    exit 1
fi

# Check Python version
python3 --version >/dev/null 2>&1 || {
    echo "❌ Python 3 is required but not installed."
    echo "Install with: sudo apt install python3 python3-pip"
    exit 1
}

# Check if pipenv is available (preferred method)
if command -v pipenv &> /dev/null; then
    echo "📦 Installing Python dependencies with pipenv..."
    pipenv install
elif command -v pip3 &> /dev/null; then
    echo "📦 Installing Python dependencies with pip..."
    pip3 install -r requirements.txt
else
    echo "📦 Installing pip..."
    sudo apt update
    sudo apt install python3-pip -y
    echo "📦 Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Make script executable
chmod +x bt_sync.py

# Create a symlink in /usr/local/bin for easy access (optional)
if [[ "$1" == "--system" ]]; then
    echo "🔗 Creating system-wide command..."
    sudo ln -sf "$(pwd)/bt_sync.py" /usr/local/bin/bt-sync
    echo "✅ Installation complete! You can now run 'sudo bt-sync' from anywhere."
else
    if command -v pipenv &> /dev/null; then
        echo "✅ Installation complete! Run with: sudo pipenv run python bt_sync.py"
    else
        echo "✅ Installation complete! Run with: sudo python3 bt_sync.py"
    fi
    echo ""
    echo "💡 Tip: Run './install.sh --system' to install system-wide command 'bt-sync'"
fi

echo ""
echo "📖 Usage:"
echo "   sudo ./bt-sync                        # Wrapper script (recommended)"
if command -v pipenv &> /dev/null; then
    echo "   pipenv run python bt_sync.py --help  # Help/testing (no sudo needed)"
fi
echo "   sudo python3 bt_sync.py               # Direct system Python"
echo "   python3 bt_sync.py --help             # Show help"
echo ""
echo "💡 For sudo execution, run: sudo ./setup_sudo.sh (one-time setup)"
echo "📝 Documentation: See README.md for detailed instructions"
