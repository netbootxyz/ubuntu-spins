#!/usr/bin/env python3

from ruamel.yaml import YAML
import requests
import hashlib
import os
import logging
from urllib.parse import urljoin
import argparse
import shutil
import subprocess
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_yaml_config(config_file):
    """Load YAML configuration file."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        return yaml.load(f)

def save_yaml_config(config_file, new_data):
    """Save only SHA256 and size updates to config."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    
    with open(config_file, 'r') as f:
        data = yaml.load(f)
    
    # Only update SHA256 and size values
    for group_name, group in new_data['spin_groups'].items():
        if group_name in data['spin_groups']:
            for new_spin in group['spins']:
                for spin in data['spin_groups'][group_name]['spins']:
                    if spin['name'] == new_spin['name']:
                        if 'files' in new_spin and 'iso' in new_spin['files']:
                            if 'sha256' in new_spin['files']['iso']:
                                spin['files']['iso']['sha256'] = new_spin['files']['iso']['sha256']
                            if 'size' in new_spin['files']['iso']:
                                spin['files']['iso']['size'] = new_spin['files']['iso']['size']
    
    with open(config_file, 'w') as f:
        yaml.dump(data, f)

def download_with_progress(url, output_path):
    """Download file with progress tracking."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False

def calculate_sha256(file_path):
    """Calculate SHA256 hash of file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def download_torrent(url, output_dir):
    """Download using transmission-cli."""
    try:
        torrent_path = os.path.join(output_dir, "temp.torrent")
        kill_script = os.path.join(output_dir, "kill_transmission.sh")
        
        if not download_with_progress(url, torrent_path):
            return None
        
        # Create kill script that waits for download completion
        with open(kill_script, 'w') as f:
            f.write("""#!/bin/bash
sleep 5  # Give transmission time to start
while transmission-remote -l | grep -q '% Done'; do
    sleep 2
done
killall transmission-cli
""")
        os.chmod(kill_script, 0o755)
            
        subprocess.run(['transmission-cli', 
                       '-f', kill_script,
                       '-w', output_dir,
                       '--no-portmap',
                       '--download-dir', output_dir,
                       torrent_path], 
                      check=True,
                      timeout=3600)  # 1 hour timeout
        
        # Find downloaded ISO
        isos = [f for f in os.listdir(output_dir) if f.endswith('.iso')]
        return os.path.join(output_dir, isos[0]) if isos else None
    except Exception as e:
        logger.error(f"Torrent download failed: {e}")
        return None
    finally:
        if os.path.exists(torrent_path):
            os.unlink(torrent_path)
        if os.path.exists(kill_script):
            os.unlink(kill_script)

def update_iso_info(config_data, iso_path):
    """Update ISO information in config."""
    size = os.path.getsize(iso_path)
    sha256 = calculate_sha256(iso_path)
    
    for group in config_data['spin_groups'].values():
        for spin in group['spins']:
            if 'files' in spin and 'iso' in spin['files']:
                spin['files']['iso']['size'] = size
                spin['files']['iso']['sha256'] = sha256
                return True
    return False

def get_iso_url(spin, version):
    """Get the correct ISO URL based on spin type"""
    base_url = spin['files']['iso']['url']
    path = spin['files']['iso']['path_template'].replace('{{ version }}', version)
    return urljoin(base_url, path)

def get_torrent_url(spin, version):
    """Get the correct torrent URL for a spin"""
    iso_url = get_iso_url(spin, version)
    # Check if URL ends with .iso
    if not iso_url.endswith('.iso'):
        logger.error(f"Invalid ISO URL format: {iso_url}")
        return None
    return f"{iso_url}.torrent"

def main():
    parser = argparse.ArgumentParser(description='Update Ubuntu ISO information')
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    parser.add_argument('--spin', help='Update specific spin only')
    parser.add_argument('--use-torrent', action='store_true', help='Use torrent for downloading')
    parser.add_argument('--work-dir', default='/tmp/iso-work', help='Working directory')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    os.makedirs(args.work_dir, exist_ok=True)
    try:
        config_data = load_yaml_config(args.config)
        version = config_data.get('version')
        if not version:
            logger.error("No version specified in config")
            return

        # If specific spin requested, filter config data
        if args.spin:
            if args.spin not in config_data['spin_groups']:
                logger.error(f"Spin {args.spin} not found in config")
                return
            filtered_groups = {args.spin: config_data['spin_groups'][args.spin]}
            config_data['spin_groups'] = filtered_groups

        for group_name, group in config_data['spin_groups'].items():
            for spin in group['spins']:
                logger.info(f"Processing {spin['name']} {version}")
                
                if args.use_torrent:
                    torrent_url = get_torrent_url(spin, version)
                    if torrent_url:
                        logger.info(f"Using torrent URL: {torrent_url}")
                        downloaded_path = download_torrent(torrent_url, args.work_dir)
                        if downloaded_path:
                            size = os.path.getsize(downloaded_path)
                            sha256 = calculate_sha256(downloaded_path)
                            spin['files']['iso']['size'] = size
                            spin['files']['iso']['sha256'] = sha256
                            os.unlink(downloaded_path)
                else:
                    iso_url = get_iso_url(spin, version)
                    iso_path = os.path.join(args.work_dir, f"{spin['name']}-{version}.iso")
                    logger.info(f"Using direct ISO URL: {iso_url}")
                    if download_with_progress(iso_url, iso_path):
                        size = os.path.getsize(iso_path)
                        sha256 = calculate_sha256(iso_path)
                        spin['files']['iso']['size'] = size
                        spin['files']['iso']['sha256'] = sha256
                        os.unlink(iso_path)
        
        save_yaml_config(args.config, config_data)
                
    finally:
        shutil.rmtree(args.work_dir, ignore_errors=True)

if __name__ == '__main__':
    main()
