#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import os
import logging
import subprocess
import re
from urllib.parse import urljoin
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Minimum supported version (YY.MM format)
MIN_VERSION = "23.04"  # Can be adjusted as needed

def version_to_float(version):
    """Convert Ubuntu version string to float for comparison"""
    try:
        return float(version.split('.')[0]) + float(version.split('.')[1]) / 100
    except:
        return 0

def get_available_versions():
    """Fetch available Ubuntu versions from cdimage.ubuntu.com"""
    try:
        response = requests.get("https://cdimage.ubuntu.com/releases/")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        versions = set()
        pattern = re.compile(r'(\d{2}\.\d{2}(?:\.\d+)?)')
        min_version_float = version_to_float(MIN_VERSION)
        
        for link in soup.find_all('a'):
            href = link.get('href', '')
            match = pattern.search(href)
            if match and not href.startswith('/'):
                version = match.group(1)
                if version_to_float(version) >= min_version_float:
                    versions.add(version)
            
        return sorted(list(versions))
    except Exception as e:
        logger.error(f"Error fetching versions: {e}")
        return []

def verify_spin_availability(version, spin_name):
    """Verify if a specific spin is available for this version"""
    try:
        url = f"https://cdimage.ubuntu.com/{spin_name}/releases/{version}/release/"
        response = requests.head(url)
        return response.status_code == 200
    except:
        return False

def verify_iso_availability(version, spin_name):
    """Verify if ISO exists and is downloadable"""
    try:
        url = f"https://cdimage.ubuntu.com/{spin_name}/releases/{version}/release/"
        if spin_name == "ubuntu":
            url = f"https://cdimage.ubuntu.com/ubuntu/releases/{version}/release/"
            
        path = f"{spin_name}-{version}-desktop-amd64.iso"
        if spin_name == "ubuntu":
            path = f"ubuntu-{version}-desktop-amd64.iso"
            
        full_url = urljoin(url, path)
        response = requests.head(full_url, allow_redirects=True, timeout=10)
        
        if response.status_code == 200 and 'content-length' in response.headers:
            return True
        return False
    except:
        return False

def process_version(version):
    """Process a specific Ubuntu version"""
    logger.info(f"Processing Ubuntu version: {version}")
    config_dir = os.path.join('config', 'versions')
    version_file = os.path.join(config_dir, f'{version}.yaml')
    
    # Generate template first
    if not os.path.exists(version_file):
        logger.info(f"Generating template for {version}")
        subprocess.run(['python3', 'scripts/generate_version_template.py', version],
                      check=True)
    
    # Load and validate the template
    with open(version_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Filter spins based on ISO availability
    valid_spins = {}
    for spin_name, spin_data in config['spin_groups'].items():
        if verify_iso_availability(version, spin_name):
            valid_spins[spin_name] = spin_data
        else:
            logger.warning(f"ISO not available for {spin_name} {version}, skipping")
    
    if not valid_spins:
        logger.warning(f"No valid ISOs found for version {version}, removing template")
        os.unlink(version_file)
        return
    
    # Update template with only valid spins
    config['spin_groups'] = valid_spins
    with open(version_file, 'w') as f:
        yaml.dump(config, f)
    
    # Update ISO information for valid spins
    subprocess.run(['python3', 'scripts/update_iso_info.py',
                   '--config', version_file,
                   '--use-torrent',
                   '-v'],
                  check=True)
    
    # Verify SHA256 and size were obtained
    with open(version_file, 'r') as f:
        config = yaml.safe_load(f)
        
    valid_spins = {}
    for spin_name, spin_data in config['spin_groups'].items():
        for spin in spin_data['spins']:
            if spin['files']['iso']['sha256'] and spin['files']['iso']['size'] > 0:
                valid_spins[spin_name] = spin_data
            else:
                logger.warning(f"Missing SHA256 or size for {spin_name} {version}, skipping")
    
    if not valid_spins:
        logger.warning(f"No valid spins with SHA256/size for {version}, removing template")
        os.unlink(version_file)
        return
    
    # Save final version with only valid spins
    config['spin_groups'] = valid_spins
    with open(version_file, 'w') as f:
        yaml.dump(config, f)

def main():
    versions = get_available_versions()
    if not versions:
        logger.error("No versions found")
        return

    config_dir = os.path.join('config', 'versions')
    os.makedirs(config_dir, exist_ok=True)

    for version in versions:
        try:
            process_version(version)
        except Exception as e:
            logger.error(f"Error processing version {version}: {e}")

if __name__ == '__main__':
    main()