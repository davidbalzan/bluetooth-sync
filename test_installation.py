#!/usr/bin/env python3
"""
Test script to validate the Bluetooth synchronization utility installation.
"""

import sys
import subprocess
from pathlib import Path

def test_python_version():
    """Test Python version compatibility"""
    print("🐍 Checking Python version...")
    if sys.version_info < (3, 6):
        print("❌ Python 3.6+ is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} is compatible")
    return True

def test_dependencies():
    """Test if required dependencies are available"""
    print("\n📦 Checking dependencies...")
    
    try:
        import Registry
        print("✅ python-registry is installed")
        return True
    except ImportError:
        print("❌ python-registry is not installed")
        print("   Install with: pip install python-registry")
        return False

def test_permissions():
    """Test if script is being run with proper context"""
    print("\n🔐 Checking execution context...")
    
    # Check if we can read system bluetooth directory
    bt_dir = Path("/var/lib/bluetooth")
    if bt_dir.exists():
        print("✅ System Bluetooth directory found")
        
        # Check if we can list adapters (requires permissions)
        try:
            adapters = list(bt_dir.iterdir())
            if adapters:
                print(f"✅ Found {len(adapters)} Bluetooth adapter(s)")
            else:
                print("ℹ️  No Bluetooth adapters found (this is normal if no devices paired yet)")
        except PermissionError:
            print("⚠️  Permission denied accessing Bluetooth directory")
            print("   The main script will need to run with sudo")
    else:
        print("⚠️  System Bluetooth directory not found")
        print("   This is normal if Bluetooth has never been used")
    
    return True

def test_utilities():
    """Test if required system utilities are available"""
    print("\n🛠️  Checking system utilities...")
    
    required_utils = ['lsblk', 'mount', 'umount', 'systemctl']
    all_good = True
    
    for util in required_utils:
        try:
            subprocess.run([util, '--version'], capture_output=True, check=True)
            print(f"✅ {util} is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # Some utilities might not have --version, try --help
                subprocess.run([util, '--help'], capture_output=True, check=True)
                print(f"✅ {util} is available")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print(f"❌ {util} is not available")
                all_good = False
    
    return all_good

def main():
    """Main test function"""
    print("🔍 Testing Bluetooth Synchronization Utility Installation")
    print("=" * 60)
    
    tests = [
        test_python_version,
        test_dependencies,
        test_utilities,
        test_permissions
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("🎉 All tests passed! The utility should work correctly.")
        print("\nNext steps:")
        print("1. Run: sudo python3 bt_sync.py")
        print("2. Follow the output instructions")
        print("3. Check /tmp/bt_sync.log for detailed logs")
    else:
        print("⚠️  Some tests failed. Please address the issues above.")
        print("\nCommon solutions:")
        print("- Install missing dependencies: pip install -r requirements.txt")
        print("- Run the main script with sudo for permissions")
        print("- Install missing system utilities with your package manager")
    
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
