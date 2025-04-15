#!/usr/bin/env python3

import yaml
import requests
import hashlib
import os
import tempfile
import subprocess
import argparse
import logging
import shutil
from datetime import datetime
from urllib.parse import urljoin
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base URLs for different Ubuntu spins
MIRROR_URLS = {
    "ubuntu": "https://releases.ubuntu.com/",
    "xubuntu": "https://cdimage.ubuntu.com/xubuntu/releases/",
    "lubuntu": "https://cdimage.ubuntu.com/lubuntu/releases/",
    "kubuntu": "https://cdimage.ubuntu.com/kubuntu/releases/",
    "ubuntu-budgie": "https://cdimage.ubuntu.com/ubuntu-budgie/releases/",
    # Add more spins as needed
}

# Base URLs for torrent files
TORRENT_URLS = {
    "ubuntu": "https://releases.ubuntu.com/",
    "xubuntu": "https://cdimage.ubuntu.com/xubuntu/releases/",
    "lubuntu": "https://cdimage.ubuntu.com/lubuntu/releases/",
    "kubuntu": "https://cdimage.ubuntu.com/kubuntu/releases/",
    "ubuntu-budgie": "https://cdimage.ubuntu.com/ubuntu-budgie/releases/",
    # Add more spins as needed
}

def load_yaml_config(config_file):
    """Load the YAML configuration file."""
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def save_yaml_config(config_file, config_data):
    """Save the updated YAML configuration file."""
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
    logger.info(f"Updated configuration saved to {config_file}")

def get_latest_release_version(spin_name):
    """Check for the latest release version of a Ubuntu spin."""
    if spin_name not in MIRROR_URLS:
        logger.error(f"No mirror URL defined for {spin_name}")
        return None
    
    url = MIRROR_URLS[spin_name]
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Look for version numbers in the HTML
        version_pattern = r'href="(\d+\.\d+)/"'
        versions = re.findall(version_pattern, response.text)
        
        # Sort versions and get the latest
        if versions:
            latest_version = sorted(versions, key=lambda v: [int(x) for x in v.split('.')], reverse=True)[0]
            return latest_version
        
        logger.warning(f"No version found for {spin_name}")
        return None
    
    except requests.RequestException as e:
        logger.error(f"Error fetching version for {spin_name}: {e}")
        return None

def download_iso_direct(url, temp_dir):
    """Download an ISO file directly to a temporary directory."""
    logger.info(f"Downloading ISO directly from {url}")
    local_filename = os.path.join(temp_dir, os.path.basename(url))
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        last_reported_percent = -1  # Track the last reported percentage
        
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Log progress only when percentage changes significantly
                    if total_size > 0:
                        current_percent = int(100 * downloaded / total_size)
                        if current_percent % 10 == 0 and current_percent > last_reported_percent:
                            logger.info(f"Download progress: {current_percent}%")
                            last_reported_percent = current_percent
        
        logger.info(f"Download completed: {local_filename}")
        return local_filename
    
    except requests.RequestException as e:
        logger.error(f"Error downloading ISO: {e}")
        return None

def download_via_torrent(torrent_url, temp_dir):
    """Download an ISO file using transmission-cli from a torrent URL."""
    logger.info(f"Downloading ISO via torrent from {torrent_url}")
    
    # First download the torrent file
    torrent_file = os.path.join(temp_dir, "ubuntu.torrent")
    try:
        response = requests.get(torrent_url, stream=True)
        response.raise_for_status()
        
        with open(torrent_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"Torrent file downloaded to {torrent_file}")
        
        # Create a script to kill transmission-cli when download completes
        kill_script = os.path.join(temp_dir, "kill_transmission.sh")
        with open(kill_script, 'w') as f:
            f.write("#!/bin/bash\nkillall transmission-cli\nexit 0")
        os.chmod(kill_script, 0o755)
        
        # Check if transmission-cli is installed
        if shutil.which("transmission-cli") is None:
            logger.error("transmission-cli is not installed. Please install it with 'brew install transmission-cli' or appropriate package manager.")
            return None
        
        # Run transmission-cli to download the ISO
        logger.info("Starting torrent download with transmission-cli...")
        subprocess.run(["transmission-cli", "-f", kill_script, "-w", temp_dir, torrent_file], check=False)
        
        # Find the ISO file in the temporary directory
        iso_files = [f for f in os.listdir(temp_dir) if f.endswith('.iso')]
        if not iso_files:
            logger.error("No ISO file found after torrent download completed")
            return None
        
        iso_file = os.path.join(temp_dir, iso_files[0])

        logger.info(f"Torrent download completed: {iso_file}")
        return iso_file
    
    except requests.RequestException as e:
        logger.error(f"Error downloading torrent file: {e}")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running transmission-cli: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during torrent download: {e}")
        return None

def download_iso(url, temp_dir, use_torrent=False):
    """Download an ISO file to a temporary directory, using torrent if specified."""
    if use_torrent:
        # Attempt to construct a torrent URL from the direct ISO URL
        # This assumes torrent files are available at the same location with .torrent extension
        torrent_url = re.sub(r'\.iso$', '.iso.torrent', url)
        
        # Try to download via torrent
        try:
            logger.info(f"Attempting to download via torrent: {torrent_url}")
            # First check if the torrent file exists
            response = requests.head(torrent_url)
            if response.status_code == 200:
                result = download_via_torrent(torrent_url, temp_dir)
                if result:
                    return result
                else:
                    logger.warning("Torrent download failed, falling back to direct download")
            else:
                logger.warning(f"Torrent file not found at {torrent_url}, falling back to direct download")
        except Exception as e:
            logger.warning(f"Error during torrent download attempt: {e}. Falling back to direct download.")
    
    # Fall back to direct download if torrent fails or is not requested
    return download_iso_direct(url, temp_dir)

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
            
    return sha256_hash.hexdigest()

def update_spin_info(config_data, spin_group, spin, iso_file):
    """Update the spin information with new ISO details."""
    file_size = os.path.getsize(iso_file)
    sha256 = calculate_sha256(iso_file)
    
    logger.info(f"Updating {spin['name']} information:")
    logger.info(f"  - SHA256: {sha256}")
    logger.info(f"  - Size: {file_size} bytes")
    
    # Update the configuration
    spin_group_data = config_data["spin_groups"][spin_group]
    for s in spin_group_data["spins"]:
        if s["name"] == spin["name"]:
            s["files"]["iso"]["sha256"] = sha256
            s["files"]["iso"]["size"] = file_size
            
            # Update the updated timestamp
            config_data["default_settings"]["updated"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            return True
    
    return False

def create_git_pr(config_file, branches):
    """Create a git commit and pull request with the changes."""
    try:
        # Get the current date for the branch name
        date_str = datetime.now().strftime("%Y%m%d")
        branch_name = f"update-iso-info-{date_str}"
        
        # Create a new branch
        subprocess.run(["git", "checkout", "-b", branch_name], check=True)
        
        # Add the modified file
        subprocess.run(["git", "add", config_file], check=True)
        
        # Create a commit
        commit_message = f"Update ISO information for {', '.join(branches)} - {date_str}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        
        # Push to remote
        subprocess.run(["git", "push", "-u", "origin", branch_name], check=True)
        
        logger.info(f"Changes pushed to branch: {branch_name}")
        logger.info("Create a PR through the GitHub UI or use the GitHub CLI for full automation")
        
        return branch_name
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        return None

def resolve_iso_url(spin, latest_version):
    """Construct the URL for the ISO file."""
    base_url = MIRROR_URLS[spin["name"]]
    
    # Create the path from the template
    path = spin["files"]["iso"]["path_template"]
    path = path.replace("{{ release }}", latest_version)
    path = path.replace("{{ name }}", spin["name"])
    path = path.replace("{{ version }}", latest_version)
    path = path.replace("{{ image_type }}", spin["image_type"])
    path = path.replace("{{ arch }}", spin["architectures"][0])  # Using first architecture
    
    return urljoin(base_url, path)

def check_and_update_spins(config_file, dry_run=False, specific_version=None, specific_spin=None, use_torrent=False):
    """Check for updates to Ubuntu spins and update the configuration."""
    config_data = load_yaml_config(config_file)
    updated_spins = []
    
    # Create a temporary directory for ISO downloads
    with tempfile.TemporaryDirectory() as temp_dir:
        for spin_group, group_data in config_data["spin_groups"].items():
            for spin in group_data["spins"]:
                # Skip if a specific spin is requested and this isn't it
                if specific_spin and spin["name"] != specific_spin:
                    logger.info(f"Skipping {spin['name']} as it doesn't match the requested spin: {specific_spin}")
                    continue
                
                logger.info(f"Checking for updates to {spin['name']}")
                
                # Skip if no mirror URL defined
                if spin["name"] not in MIRROR_URLS:
                    logger.warning(f"No mirror URL defined for {spin['name']}, skipping")
                    continue
                
                # Get the latest version or use the specific version if provided
                if specific_version:
                    target_version = specific_version
                    logger.info(f"Using specified version: {target_version}")
                else:
                    target_version = get_latest_release_version(spin["name"])
                    if not target_version:
                        logger.warning(f"Could not determine latest version for {spin['name']}, skipping")
                        continue
                
                # Check if the version is different from current or force update is requested
                if target_version != spin["version"] or specific_version:
                    action_text = "New version detected" if target_version != spin["version"] else "Forcing update"
                    logger.info(f"{action_text} for {spin['name']}: {target_version} (current: {spin['version']})")
                    
                    if dry_run:
                        logger.info("Dry run mode, not downloading ISO")
                        updated_spins.append(spin["name"])
                        continue
                    
                    # Download the ISO
                    # Temporarily set the version in spin to resolve the URL correctly
                    original_version = spin["version"]
                    spin["version"] = target_version
                    iso_url = resolve_iso_url(spin, target_version)
                    spin["version"] = original_version  # Restore original version
                    
                    iso_file = download_iso(iso_url, temp_dir, use_torrent)
                    
                    if not iso_file:
                        logger.error(f"Failed to download ISO for {spin['name']}, skipping")
                        continue
                    
                    # Update the spin information
                    if update_spin_info(config_data, spin_group, spin, iso_file):
                        # Update the version in the configuration
                        spin["version"] = target_version
                        updated_spins.append(spin["name"])
                else:
                    logger.info(f"{spin['name']} is already at the latest version: {target_version}")
    
    if updated_spins:
        if not dry_run:
            # Save the updated configuration
            save_yaml_config(config_file, config_data)
            
            # Create a git PR
            create_git_pr(config_file, updated_spins)
        else:
            logger.info(f"Dry run completed, {len(updated_spins)} spins would be updated: {', '.join(updated_spins)}")
    else:
        logger.info("No updates found for any Ubuntu spin")

def main():
    parser = argparse.ArgumentParser(description='Update Ubuntu spin ISO information')
    parser.add_argument('--config', default='config/iso-settings.yaml', help='Path to YAML config file')
    parser.add_argument('--dry-run', action='store_true', help='Check for updates without downloading ISOs or making changes')
    parser.add_argument('--version', help='Specify a specific Ubuntu version to check/update (e.g., 22.04)')
    parser.add_argument('--spin', help='Specify a specific spin to check/update (e.g., ubuntu, kubuntu, xubuntu)')
    parser.add_argument('--use-torrent', action='store_true', help='Use torrent to download ISOs when available (requires transmission-cli)')
    
    args = parser.parse_args()
    
    logger.info("Starting ISO information update process")
    check_and_update_spins(args.config, args.dry_run, args.version, args.spin, args.use_torrent)
    logger.info("Update process completed")

if __name__ == '__main__':
    main()