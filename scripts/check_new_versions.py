#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import os
import logging
import subprocess
import re
from urllib.parse import urljoin
import yaml
import argparse

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

def has_valid_data(spin):
    """Check if spin already has valid SHA256 and size values"""
    try:
        iso_info = spin['files']['iso']
        return (
            iso_info.get('sha256') and 
            isinstance(iso_info.get('size'), (int, float)) and 
            iso_info['size'] > 0
        )
    except:
        return False

def load_release_codenames():
    """Load release codenames mapping"""
    try:
        with open('config/release_codenames.yaml', 'r') as f:
            return yaml.safe_load(f)['release_codenames']
    except:
        logger.warning("Could not load release codenames")
        return {}

def load_spins_config():
    """Load spins configuration"""
    try:
        with open('config/spins.yaml', 'r') as f:
            return yaml.safe_load(f)['spins']
    except Exception as e:
        logger.error(f"Failed to load spins config: {e}")
        return {}

def process_version(version):
    """Process a specific Ubuntu version"""
    logger.info(f"Processing Ubuntu version: {version}")
    config_dir = os.path.join('config', 'versions')
    version_file = os.path.join(config_dir, f'{version}.yaml')
    
    try:
        # Load configurations
        spins_config = load_spins_config()
        codenames = load_release_codenames()
        base_version = '.'.join(version.split('.')[:2])
        version_info = codenames.get(base_version, {})
        release_codename = version_info.get('codename', '')
        release = version_info.get('release', '')

        # Load or create version config
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                config = yaml.safe_load(f)
        else:
            logger.info(f"Generating template for {version}")
            subprocess.run(['python3', 'scripts/generate_version_template.py', version],
                         check=True)
            with open(version_file, 'r') as f:
                config = yaml.safe_load(f)

        # Track which spins need updates
        spins_to_update = []
        valid_spins = {}

        # First pass: check which spins need updating
        for spin_id, spin_info in spins_config.items():
            logger.info(f"Checking spin {spin_id} for version {version}")
            
            existing_spin = None
            if spin_id in config['spin_groups']:
                existing_spin = config['spin_groups'][spin_id]['spins'][0]
                if has_valid_data(existing_spin):
                    logger.info(f"Using existing data for {spin_id} {version}")
                    valid_spins[spin_id] = config['spin_groups'][spin_id]
                    continue

            # Always attempt to update if ISO is available
            if verify_iso_availability(version, spin_id):
                logger.info(f"Will update {spin_id} {version}")
                if existing_spin:
                    valid_spins[spin_id] = config['spin_groups'][spin_id]
                else:
                    valid_spins[spin_id] = {
                        'name': spin_info['name'],
                        'content_id': spin_info['content_id'],
                        'spins': [{
                            'name': spin_id,
                            'release': release,
                            'version': version,
                            'release_title': version,
                            'release_codename': release_codename,
                            'image_type': 'desktop',
                            'architectures': ['amd64'],
                            'files': {
                                'iso': {
                                    'url': spin_info['url_base'].replace('{{ version }}', version),
                                    'path_template': spin_info['path_template'],
                                    'sha256': '',
                                    'size': 0
                                }
                            }
                        }]
                    }
                spins_to_update.append(spin_id)
            else:
                logger.warning(f"ISO not available for {spin_id} {version}")

        # Save current state before updates
        if valid_spins:
            config['spin_groups'] = valid_spins
            with open(version_file, 'w') as f:
                yaml.dump(config, f)

            # Try to update each spin individually
            for spin_id in spins_to_update:
                try:
                    logger.info(f"Attempting download for {spin_id} {version}")
                    subprocess.run(['python3', 'scripts/update_iso_info.py',
                                 '--config', version_file,
                                 '--spin', spin_id,
                                 '--use-torrent',
                                 '-v'],
                                check=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to update {spin_id}: {e}")

            # Load final state
            with open(version_file, 'r') as f:
                config = yaml.safe_load(f)

            # Keep spins that have data, remove those that failed
            final_spins = {}
            for spin_id, spin_data in config['spin_groups'].items():
                if has_valid_data(spin_data['spins'][0]):
                    final_spins[spin_id] = spin_data
                else:
                    logger.warning(f"Missing SHA256 or size for {spin_id} {version}, skipping")

            # Save final state if we have any valid spins
            if final_spins:
                config['spin_groups'] = final_spins
                with open(version_file, 'w') as f:
                    yaml.dump(config, f)
                return True
            else:
                logger.warning(f"No spins successfully downloaded for {version}, but keeping template for retry")
                return False
        else:
            logger.warning(f"No valid ISOs found for version {version}")
            return False

    except Exception as e:
        logger.error(f"Error processing version {version}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Check Ubuntu versions and update ISO information')
    parser.add_argument('version', nargs='?', help='Specific version to check (e.g., 24.04.2)')
    args = parser.parse_args()

    if args.version:
        # Process specific version only
        logger.info(f"Checking specific version: {args.version}")
        process_version(args.version)
        return

    # Regular version discovery and processing
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