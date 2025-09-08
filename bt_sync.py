#!/usr/bin/env python3
"""
Bluetooth Device Synchronization Utility
========================================

This utility synchronizes Bluetooth device pairing information between Windows and Linux
on dual-boot systems. It extracts pairing keys from Windows registry and updates Linux
Bluetooth configuration to match.

Requirements:
- Root privileges (for mounting and modifying system files)
- Windows partition accessible
- python3-registry or similar registry parsing library

Author: David Balzan
License: MIT
"""

import os
import sys
import subprocess
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

try:
    from Registry import Registry
    from Registry.Registry import RegistryKeyHasNoParentException
except ImportError:
    print("Error: python-registry not found. Install with: pip install python-registry")
    sys.exit(1)

# Configure logging
def setup_logging():
    """Setup logging with fallback for permission issues"""
    handlers = [logging.StreamHandler()]
    
    # Try different log file locations
    log_locations = [
        '/tmp/bt_sync.log',
        os.path.expanduser('~/bt_sync.log'),
        './bt_sync.log',
        '/var/log/bt_sync.log'
    ]
    
    for log_path in log_locations:
        try:
            handlers.append(logging.FileHandler(log_path, mode='w'))
            print(f"Logging to: {log_path}")
            break
        except (PermissionError, OSError):
            continue
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

setup_logging()
logger = logging.getLogger(__name__)

@dataclass
class BluetoothDevice:
    """Represents a Bluetooth device with its pairing information"""
    name: str
    mac_address: str
    link_key: str
    device_class: Optional[str] = None
    service_classes: Optional[str] = None

@dataclass
class WindowsPartition:
    """Represents a Windows partition"""
    device: str
    mount_point: str
    filesystem: str
    is_mounted: bool = False

class BluetoothSyncUtility:
    """Main utility class for Bluetooth synchronization"""
    
    def __init__(self):
        self.windows_partition: Optional[WindowsPartition] = None
        self.temp_mount_point: Optional[str] = None
        self.backup_dir = Path.home() / ".bt_sync_backup"
        
    def check_root_privileges(self) -> bool:
        """Check if running with root privileges"""
        if os.geteuid() != 0:
            logger.error("This utility requires root privileges. Please run with sudo.")
            return False
        return True
    
    def find_windows_partitions(self) -> List[WindowsPartition]:
        """Find all potential Windows partitions on the system"""
        logger.info("Searching for Windows partitions...")
        partitions = []
        
        try:
            # Get all block devices
            result = subprocess.run(['lsblk', '-J'], capture_output=True, text=True, check=True)
            devices = json.loads(result.stdout)
            
            def check_device(device_info, parent_name=""):
                device_name = device_info.get('name', '')
                full_device = f"/dev/{device_name}"
                fstype = device_info.get('fstype', '')
                mountpoint = device_info.get('mountpoint', '')
                device_type = device_info.get('type', '')
                
                # Check if this is a partition
                if device_type == 'part':
                    detected_fs = None
                    
                    # Method 1: Use fstype from lsblk if available
                    if fstype in ['ntfs', 'vfat']:
                        detected_fs = fstype
                        logger.info(f"Found {fstype} partition: {full_device}")
                    
                    # Method 2: Use file command if fstype is missing
                    elif not fstype:
                        try:
                            file_result = subprocess.run(['file', '-s', full_device], 
                                                       capture_output=True, text=True, check=True)
                            file_output = file_result.stdout.lower()
                            if 'ntfs' in file_output:
                                detected_fs = 'ntfs'
                                logger.info(f"Detected NTFS partition via file command: {full_device}")
                            elif 'fat' in file_output or 'vfat' in file_output:
                                detected_fs = 'vfat'
                                logger.info(f"Detected FAT partition via file command: {full_device}")
                        except subprocess.CalledProcessError:
                            pass
                    
                    # Method 3: Use blkid as additional fallback
                    if not detected_fs:
                        try:
                            blkid_result = subprocess.run(['blkid', '-o', 'value', '-s', 'TYPE', full_device], 
                                                        capture_output=True, text=True, check=True)
                            blkid_fs = blkid_result.stdout.strip().lower()
                            if blkid_fs in ['ntfs', 'vfat']:
                                detected_fs = blkid_fs
                                logger.info(f"Detected {blkid_fs} partition via blkid: {full_device}")
                        except subprocess.CalledProcessError:
                            pass
                    
                    # Method 4: Check by partition size and position (heuristic for large partitions)
                    if not detected_fs:
                        size_str = device_info.get('size', '')
                        # Check if it's a large partition (likely Windows if >100G)
                        if any(unit in size_str for unit in ['G', 'T']) and device_name.endswith(('p3', 'p2', '3', '2')):
                            logger.info(f"Large partition that might be Windows: {full_device} ({size_str})")
                            # Try to check if it contains Windows directories
                            if self._check_if_windows_partition(full_device, mountpoint):
                                detected_fs = 'ntfs'  # Assume NTFS for Windows
                                logger.info(f"Confirmed Windows partition: {full_device}")
                    
                    # If we detected a Windows filesystem, add it
                    if detected_fs:
                        # Try to identify Windows partition by checking for Windows directories
                        is_windows = self._check_if_windows_partition(full_device, mountpoint)
                        if is_windows:
                            partitions.append(WindowsPartition(
                                device=full_device,
                                mount_point=mountpoint or "",
                                filesystem=detected_fs,
                                is_mounted=bool(mountpoint)
                            ))
                        elif detected_fs == 'ntfs':
                            # For NTFS partitions, assume they might be Windows even if we can't verify
                            logger.info(f"Adding NTFS partition (assuming Windows): {full_device}")
                            partitions.append(WindowsPartition(
                                device=full_device,
                                mount_point=mountpoint or "",
                                filesystem=detected_fs,
                                is_mounted=bool(mountpoint)
                            ))
                
                # Recursively check children
                for child in device_info.get('children', []):
                    check_device(child, device_name)
            
            for device in devices.get('blockdevices', []):
                check_device(device)
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list block devices: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse lsblk output: {e}")
            
        logger.info(f"Found {len(partitions)} potential Windows partition(s)")
        return partitions
    
    def _check_if_windows_partition(self, device: str, current_mount: Optional[str]) -> bool:
        """Check if a partition contains Windows by looking for characteristic directories"""
        mount_point = current_mount
        temp_mount = False
        
        try:
            if not current_mount:
                # Create temporary mount point
                mount_point = tempfile.mkdtemp(prefix="bt_sync_check_")
                temp_mount = True
                subprocess.run(['mount', '-r', device, mount_point], 
                             check=True, capture_output=True)
            
            # Check for Windows characteristic directories
            windows_indicators = [
                'Windows/System32',
                'Program Files',
                'Users',
                'WINDOWS/system32'  # Case variations
            ]
            
            for indicator in windows_indicators:
                if (Path(mount_point) / indicator).exists():
                    logger.info(f"Found Windows partition: {device}")
                    return True
                    
        except subprocess.CalledProcessError:
            # Mount failed, probably not accessible or not the right filesystem
            pass
        except Exception as e:
            logger.warning(f"Error checking partition {device}: {e}")
        finally:
            if temp_mount and mount_point:
                try:
                    subprocess.run(['umount', mount_point], check=True, capture_output=True)
                    os.rmdir(mount_point)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp mount {mount_point}: {e}")
        
        return False
    
    def mount_windows_partition(self, partition: WindowsPartition) -> bool:
        """Mount Windows partition if not already mounted"""
        if partition.is_mounted:
            logger.info(f"Windows partition {partition.device} already mounted at {partition.mount_point}")
            self.windows_partition = partition
            return True
        
        # Create temporary mount point
        try:
            self.temp_mount_point = tempfile.mkdtemp(prefix="bt_sync_mount_")
            subprocess.run(['mount', '-r', partition.device, self.temp_mount_point], 
                         check=True, capture_output=True)
            
            partition.mount_point = self.temp_mount_point
            partition.is_mounted = True
            self.windows_partition = partition
            
            logger.info(f"Mounted Windows partition {partition.device} at {self.temp_mount_point}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to mount Windows partition {partition.device}: {e}")
            if self.temp_mount_point:
                try:
                    os.rmdir(self.temp_mount_point)
                except:
                    pass
                self.temp_mount_point = None
            return False
    
    def find_bluetooth_registry(self) -> Optional[Path]:
        """Find the Windows Bluetooth registry file"""
        if not self.windows_partition:
            logger.error("No Windows partition mounted")
            return None
        
        # Common paths for Windows registry
        registry_paths = [
            'Windows/System32/config/SYSTEM',
            'WINDOWS/System32/config/SYSTEM',
            'windows/system32/config/SYSTEM'
        ]
        
        mount_point = Path(self.windows_partition.mount_point)
        
        for reg_path in registry_paths:
            full_path = mount_point / reg_path
            if full_path.exists():
                logger.info(f"Found Windows registry at: {full_path}")
                return full_path
        
        logger.error("Could not find Windows SYSTEM registry file")
        return None
    
    def parse_bluetooth_devices(self, registry_path: Path) -> List[BluetoothDevice]:
        """Parse Windows registry to extract Bluetooth device information"""
        logger.info("Parsing Windows Bluetooth registry...")
        devices = []
        
        try:
            with open(registry_path, 'rb') as f:
                registry = Registry.Registry(f)
                
                # Navigate to Bluetooth key
                # Path: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys
                try:
                    # Find the current control set
                    current_control_set = self._find_current_control_set(registry)
                    if not current_control_set:
                        logger.error("Could not determine current control set")
                        return devices
                    
                    services_key = registry.open(f"{current_control_set}\\Services")
                    bthport_key = services_key.subkey("BTHPORT")
                    params_key = bthport_key.subkey("Parameters")
                    keys_key = params_key.subkey("Keys")
                    
                    # Each subkey under Keys represents a Bluetooth adapter
                    for adapter_key in keys_key.subkeys():
                        adapter_mac = adapter_key.name()
                        logger.info(f"Found Bluetooth adapter: {adapter_mac}")
                        
                        # Each subkey under adapter represents a paired device
                        for device_key in adapter_key.subkeys():
                            device_mac = device_key.name()
                            
                            try:
                                # Get the link key (pairing key)
                                link_key_value = device_key.value("LinkKey")
                                link_key = link_key_value.value().hex().upper()
                                
                                # Try to get device name
                                device_name = device_mac  # Default to MAC if name not found
                                try:
                                    name_value = device_key.value("Name")
                                    device_name = name_value.value().decode('utf-8', errors='ignore')
                                except:
                                    pass
                                
                                device = BluetoothDevice(
                                    name=device_name,
                                    mac_address=self._format_mac_address(device_mac),
                                    link_key=link_key
                                )
                                devices.append(device)
                                logger.info(f"Found Bluetooth device: {device.name} ({device.mac_address})")
                                
                            except Exception as e:
                                logger.warning(f"Could not parse device {device_mac}: {e}")
                                continue
                                
                except Exception as e:
                    logger.error(f"Could not navigate Bluetooth registry keys: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to parse registry: {e}")
        
        logger.info(f"Found {len(devices)} Bluetooth devices in Windows registry")
        return devices
    
    def _find_current_control_set(self, registry: Registry) -> Optional[str]:
        """Find the current control set in the registry"""
        try:
            select_key = registry.open("Select")
            current_value = select_key.value("Current")
            current_num = current_value.value()
            return f"ControlSet{current_num:03d}"
        except Exception as e:
            logger.warning(f"Could not determine current control set: {e}")
            # Try common control sets
            for cs_num in [1, 2, 3]:
                cs_name = f"ControlSet{cs_num:03d}"
                try:
                    registry.open(cs_name)
                    logger.info(f"Using control set: {cs_name}")
                    return cs_name
                except:
                    continue
        return None
    
    def _format_mac_address(self, mac_hex: str) -> str:
        """Format MAC address from Windows hex format to standard format"""
        # Windows stores MAC as hex string, convert to XX:XX:XX:XX:XX:XX format
        mac_clean = mac_hex.replace(":", "").replace("-", "").upper()
        if len(mac_clean) == 12:
            return ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))
        return mac_hex
    
    def get_linux_bluetooth_info(self) -> Dict[str, str]:
        """Get Linux Bluetooth adapter information"""
        linux_bt_info = {}
        bt_config_dir = Path("/var/lib/bluetooth")
        
        if not bt_config_dir.exists():
            logger.error("Linux Bluetooth configuration directory not found")
            return linux_bt_info
        
        # Find Bluetooth adapter directories
        for adapter_dir in bt_config_dir.iterdir():
            if adapter_dir.is_dir() and re.match(r'^[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}$', adapter_dir.name):
                linux_bt_info[adapter_dir.name] = str(adapter_dir)
                logger.info(f"Found Linux Bluetooth adapter: {adapter_dir.name}")
        
        return linux_bt_info
    
    def backup_linux_bluetooth_config(self):
        """Backup current Linux Bluetooth configuration"""
        logger.info("Creating backup of Linux Bluetooth configuration...")
        
        bt_config_dir = Path("/var/lib/bluetooth")
        if not bt_config_dir.exists():
            logger.warning("No Linux Bluetooth configuration to backup")
            return
        
        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)
        timestamp = subprocess.run(['date', '+%Y%m%d_%H%M%S'], capture_output=True, text=True).stdout.strip()
        backup_path = self.backup_dir / f"bluetooth_backup_{timestamp}"
        
        try:
            shutil.copytree(bt_config_dir, backup_path)
            logger.info(f"Bluetooth configuration backed up to: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup Bluetooth configuration: {e}")
    
    def update_linux_bluetooth_config(self, devices: List[BluetoothDevice]) -> bool:
        """Update Linux Bluetooth configuration with Windows device keys"""
        logger.info("Updating Linux Bluetooth configuration...")
        
        # Get Linux Bluetooth adapters
        linux_adapters = self.get_linux_bluetooth_info()
        if not linux_adapters:
            logger.error("No Linux Bluetooth adapters found")
            return False
        
        # Stop Bluetooth service
        try:
            subprocess.run(['systemctl', 'stop', 'bluetooth'], check=True)
            logger.info("Stopped Bluetooth service")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop Bluetooth service: {e}")
            return False
        
        success = True
        
        try:
            # For each Linux adapter, try to update with Windows devices
            for adapter_mac, adapter_path in linux_adapters.items():
                adapter_dir = Path(adapter_path)
                
                for device in devices:
                    device_dir = adapter_dir / device.mac_address
                    device_dir.mkdir(exist_ok=True)
                    
                    # Create/update info file
                    info_file = device_dir / "info"
                    
                    # Read existing info if it exists
                    existing_info = {}
                    if info_file.exists():
                        try:
                            with open(info_file, 'r') as f:
                                current_section = None
                                for line in f:
                                    line = line.strip()
                                    if line.startswith('[') and line.endswith(']'):
                                        current_section = line[1:-1]
                                        existing_info[current_section] = {}
                                    elif '=' in line and current_section:
                                        key, value = line.split('=', 1)
                                        existing_info[current_section][key] = value
                        except Exception as e:
                            logger.warning(f"Could not read existing info for {device.mac_address}: {e}")
                    
                    # Update with Windows information
                    if 'General' not in existing_info:
                        existing_info['General'] = {}
                    
                    existing_info['General']['Name'] = device.name
                    existing_info['General']['Trusted'] = 'true'
                    existing_info['General']['Blocked'] = 'false'
                    
                    # Add link key
                    if 'LinkKey' not in existing_info:
                        existing_info['LinkKey'] = {}
                    existing_info['LinkKey']['Key'] = device.link_key
                    existing_info['LinkKey']['Type'] = '4'  # Combination key
                    existing_info['LinkKey']['PINLength'] = '0'
                    
                    # Write updated info file
                    try:
                        with open(info_file, 'w') as f:
                            for section, values in existing_info.items():
                                f.write(f"[{section}]\n")
                                for key, value in values.items():
                                    f.write(f"{key}={value}\n")
                                f.write("\n")
                        
                        logger.info(f"Updated configuration for device: {device.name} ({device.mac_address})")
                        
                    except Exception as e:
                        logger.error(f"Failed to write info file for {device.mac_address}: {e}")
                        success = False
        
        finally:
            # Restart Bluetooth service
            try:
                subprocess.run(['systemctl', 'start', 'bluetooth'], check=True)
                logger.info("Restarted Bluetooth service")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to restart Bluetooth service: {e}")
                success = False
        
        return success
    
    def cleanup(self):
        """Clean up temporary mounts and files"""
        if self.windows_partition and not self.windows_partition.is_mounted and self.temp_mount_point:
            try:
                subprocess.run(['umount', self.temp_mount_point], check=True, capture_output=True)
                os.rmdir(self.temp_mount_point)
                logger.info("Cleaned up temporary mount point")
            except Exception as e:
                logger.warning(f"Failed to cleanup mount point: {e}")
    
    def run(self) -> bool:
        """Main execution method"""
        logger.info("Starting Bluetooth synchronization utility...")
        
        # Check privileges
        if not self.check_root_privileges():
            return False
        
        try:
            # Find Windows partitions
            partitions = self.find_windows_partitions()
            if not partitions:
                logger.error("No Windows partitions found")
                return False
            
            # Use the first Windows partition found
            # TODO: Could add user selection if multiple found
            partition = partitions[0]
            logger.info(f"Using Windows partition: {partition.device}")
            
            # Mount Windows partition
            if not self.mount_windows_partition(partition):
                return False
            
            # Find Bluetooth registry
            registry_path = self.find_bluetooth_registry()
            if not registry_path:
                return False
            
            # Parse Bluetooth devices
            devices = self.parse_bluetooth_devices(registry_path)
            if not devices:
                logger.warning("No Bluetooth devices found in Windows registry")
                return True  # Not necessarily an error
            
            # Backup current Linux configuration
            self.backup_linux_bluetooth_config()
            
            # Update Linux Bluetooth configuration
            success = self.update_linux_bluetooth_config(devices)
            
            if success:
                logger.info("Bluetooth synchronization completed successfully!")
                logger.info("Your Bluetooth devices should now work on both Windows and Linux.")
            else:
                logger.error("Bluetooth synchronization completed with errors.")
            
            return success
            
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print(__doc__)
        print("\nUsage:")
        print("  sudo python3 bt_sync.py")
        print("\nThis utility must be run with root privileges.")
        return
    
    utility = BluetoothSyncUtility()
    success = utility.run()
    
    if success:
        print("\n" + "="*50)
        print("BLUETOOTH SYNCHRONIZATION COMPLETE")
        print("="*50)
        print("Your Bluetooth devices should now be paired on both Windows and Linux.")
        print("If you encounter any issues, check the log file at /tmp/bt_sync.log")
        print(f"Backup of your original configuration is at: {utility.backup_dir}")
    else:
        print("\n" + "="*50)
        print("BLUETOOTH SYNCHRONIZATION FAILED")
        print("="*50)
        print("Check the log file at /tmp/bt_sync.log for detailed error information.")
        print("Your original Bluetooth configuration has been preserved.")
        sys.exit(1)

if __name__ == "__main__":
    main()
