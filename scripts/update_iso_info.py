#!/usr/bin/env python3

import yaml
import requests
import hashlib
import os
import tempfile
import logging
from urllib.parse import urljoin
import re
import argparse
import shutil
import subprocess
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MIRROR_URLS = {
    "ubuntu": "https://cdimage.ubuntu.com/ubuntu-mini-iso/noble/daily-live/current/",
    "kubuntu": "https://cdimage.ubuntu.com/kubuntu/releases/",
    "xubuntu": "https://cdimage.ubuntu.com/xubuntu/releases/",
    "lubuntu": "https://cdimage.ubuntu.com/lubuntu/releases/",
    "ubuntu-mate": "https://cdimage.ubuntu.com/ubuntu-mate/releases/",
    "ubuntu-budgie": "https://cdimage.ubuntu.com/ubuntu-budgie/releases/",
    "ubuntu-studio": "https://cdimage.ubuntu.com/ubuntustudio/releases/",
    "ubuntu-unity": "https://cdimage.ubuntu.com/ubuntu-unity/releases/",
    "ubuntu-kylin": "https://cdimage.ubuntu.com/ubuntukylin/releases/"
}

def load_yaml_config(config_file):
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def save_yaml_config(config_file, config_data):
    """Save only the modified fields in the YAML configuration file."""
    with open(config_file, 'r') as f:
        lines = f.readlines()

    # Track indentation levels and paths to help with matching
    current_path = []
    indent_level = 0
    in_spin = False
    current_spin = None
    updated_lines = []

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        
        # Track path based on indentation
        if indent < indent_level:
            while current_path and len(current_path) * 2 > indent:
                current_path.pop()
                in_spin = False
                current_spin = None
        
        if stripped.startswith('spin_groups:'):
            current_path = ['spin_groups']
        elif stripped.startswith('- name:'):
            spin_name = stripped.split(':')[1].strip()
            in_spin = True
            current_spin = None
            for group in config_data['spin_groups'].values():
                for spin in group['spins']:
                    if spin['name'] == spin_name and 'files' in spin and 'iso' in spin['files']:
                        current_spin = spin
                        break
                if current_spin:
                    break
        
        # Update SHA256 and size if we're at those lines and have a matching spin
        if in_spin and current_spin and 'files' in current_spin and 'iso' in current_spin['files']:
            if stripped.startswith('sha256:'):
                line = line[:indent] + f"sha256: '{current_spin['files']['iso']['sha256']}'\n"
            elif stripped.startswith('size:'):
                line = line[:indent] + f"size: {current_spin['files']['iso']['size']}\n"
        
        updated_lines.append(line)
    
    with open(config_file, 'w') as f:
        f.writelines(updated_lines)
    logger.info(f"Updated configuration saved to {config_file}")

def get_file_info(url):
    try:
        response = requests.head(url, allow_redirects=True)
        response.raise_for_status()
        return {
            'size': int(response.headers.get('content-length', 0)),
            'exists': response.status_code == 200
        }
    except:
        return {'size': 0, 'exists': False}

def download_file(url, output_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int(100 * downloaded / total_size)
                        if percent % 10 == 0:
                            logger.info(f"Download progress: {percent}%")
        return True
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return False

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def update_spin_info(config_data, spin_name, version, iso_path):
    """Update spin information with new ISO details."""
    file_size = os.path.getsize(iso_path)
    sha256 = calculate_sha256(iso_path)
    
    logger.info(f"New ISO information for {spin_name}:")
    logger.info(f"  Size: {file_size} bytes")
    logger.info(f"  SHA256: {sha256}")
    
    updated = False
    for group in config_data["spin_groups"].values():
        for spin in group.get("spins", []):
            if spin["name"] == spin_name and spin.get("version") == version:
                # Only update the size and sha256 fields
                if "files" in spin and "iso" in spin["files"]:
                    spin["files"]["iso"]["size"] = str(file_size)
                    spin["files"]["iso"]["sha256"] = sha256
                    updated = True
    
    return updated

def resolve_iso_url(spin):
    """Generate ISO URL from spin information"""
    base_url = MIRROR_URLS.get(spin["name"])
    if not base_url:
        return None
        
    if spin["name"] == "ubuntu":
        return urljoin(base_url, "noble-mini-iso-amd64.iso")
    
    path = spin["files"]["iso"]["path_template"] \
        .replace("{{ release }}", spin["release"]) \
        .replace("{{ name }}", spin["name"]) \
        .replace("{{ version }}", spin["release_title"]) \
        .replace("{{ image_type }}", spin["image_type"]) \
        .replace("{{ arch }}", "amd64")
    
    return urljoin(base_url, path)

def download_torrent(url, output_dir):
    """Download ISO using transmission-cli with proper cleanup"""
    torrent_file = None
    kill_file = None
    process = None
    downloaded_iso = None
    
    try:
        # Download and save torrent file
        torrent_file = os.path.join(output_dir, "temp.torrent")
        response = requests.get(url)
        response.raise_for_status()
        
        with open(torrent_file, 'wb') as f:
            f.write(response.content)
        
        # Create kill file
        kill_file = os.path.join(output_dir, "kill.sh")
        with open(kill_file, 'w') as f:
            f.write("killall transmission-cli")
        os.chmod(kill_file, 0o755)
        
        # Start transmission-cli with kill file
        cmd = [
            'transmission-cli',
            '-w', output_dir,
            '-f', kill_file,
            '--no-portmap',  # Disable port mapping
            torrent_file
        ]
        process = subprocess.Popen(cmd)
        
        # Wait for download to complete with timeout
        timeout = 3600  # 1 hour timeout
        start_time = time.time()
        
        # Monitor process status
        while process.poll() is None:
            if time.time() - start_time > timeout:
                raise TimeoutError("Torrent download timed out")
            time.sleep(1)
        
        # Find downloaded ISO
        isos = [f for f in os.listdir(output_dir) if f.endswith('.iso')]
        if isos:
            downloaded_iso = os.path.join(output_dir, isos[0])
            return downloaded_iso
            
    except Exception as e:
        logger.error(f"Torrent download failed: {e}")
        return None
        
    finally:
        # Cleanup processes
        if process and process.poll() is None:
            try:
                subprocess.run([kill_file], check=True)
                process.wait(timeout=5)
                if process.poll() is None:
                    process.kill()
            except Exception as e:
                logger.error(f"Error terminating transmission-cli: {e}")
        
        # Cleanup files
        for file_to_remove in [torrent_file, kill_file]:
            if file_to_remove and os.path.exists(file_to_remove):
                try:
                    os.unlink(file_to_remove)
                except Exception as e:
                    logger.error(f"Error removing {file_to_remove}: {e}")
        
        # Remove any .part files
        for file in os.listdir(output_dir):
            if file.endswith('.part'):
                try:
                    os.unlink(os.path.join(output_dir, file))
                except Exception as e:
                    logger.error(f"Error removing partial download {file}: {e}")

def resolve_torrent_url(spin):
    """Generate torrent URL from spin information"""
    if spin["name"] == "ubuntu":
        return None  # mini.iso doesn't have torrents
    
    base_url = MIRROR_URLS.get(spin["name"])
    if not base_url:
        return None
    
    path = spin["files"]["iso"]["path_template"] \
        .replace("{{ release }}", spin["release"]) \
        .replace("{{ name }}", spin["name"]) \
        .replace("{{ version }}", spin["release_title"]) \
        .replace("{{ image_type }}", spin["image_type"]) \
        .replace("{{ arch }}", "amd64")
    
    return urljoin(base_url, path + ".torrent")

def main():
    parser = argparse.ArgumentParser(description='Update Ubuntu spin ISO information')
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    parser.add_argument('--dry-run', action='store_true', help='Check for updates without making changes')
    parser.add_argument('--spin', help='Update specific spin only')
    parser.add_argument('--work-dir', default='/tmp/iso-work', help='Working directory for ISO downloads')
    parser.add_argument('--use-torrent', action='store_true', help='Use torrent for downloading')
    args = parser.parse_args()

    if not os.path.exists(args.work_dir):
        os.makedirs(args.work_dir)

    config_data = load_yaml_config(args.config)
    updated = False

    try:
        for group_name, group in config_data["spin_groups"].items():
            for spin in group.get("spins", []):
                if args.spin and spin["name"] != args.spin:
                    continue

                if args.use_torrent:
                    torrent_url = resolve_torrent_url(spin)
                    if torrent_url:
                        logger.info(f"Using torrent for {spin['name']}: {torrent_url}")
                        iso_path = download_torrent(torrent_url, args.work_dir)
                        if iso_path:
                            try:
                                if update_spin_info(config_data, spin["name"], spin.get("version"), iso_path):
                                    updated = True
                            finally:
                                if os.path.exists(iso_path):
                                    os.unlink(iso_path)
                            continue

                # Fall back to direct download if torrent fails or isn't available
                iso_url = resolve_iso_url(spin)
                if not iso_url:
                    logger.warning(f"Could not resolve URL for {spin['name']}")
                    continue

                logger.info(f"Checking {spin['name']} ISO at {iso_url}")
                file_info = get_file_info(iso_url)
                
                if not file_info['exists']:
                    logger.warning(f"ISO not found at {iso_url}")
                    continue

                if not args.dry_run:
                    iso_path = os.path.join(args.work_dir, f"{spin['name']}.iso")
                    if download_file(iso_url, iso_path):
                        try:
                            if update_spin_info(config_data, spin["name"], spin.get("version"), iso_path):
                                updated = True
                        finally:
                            os.unlink(iso_path)

        if updated and not args.dry_run:
            save_yaml_config(args.config, config_data)

    finally:
        if os.path.exists(args.work_dir):
            shutil.rmtree(args.work_dir)

if __name__ == '__main__':
    main()
