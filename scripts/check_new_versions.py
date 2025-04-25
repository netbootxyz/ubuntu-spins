#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import logging
import re
import yaml
import argparse
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Minimum supported version (YY.MM format)
MIN_VERSION = "22.04"  # Can be adjusted as needed

def version_to_float(version):
    try:
        return float(version.split('.')[0]) + float(version.split('.')[1]) / 100
    except:
        return 0

def get_available_versions():
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

def verify_iso_availability(version, spin_name):
    try:
        url = f"https://cdimage.ubuntu.com/{spin_name}/releases/{version}/release/"
        if spin_name == "ubuntu":
            url = f"https://cdimage.ubuntu.com/ubuntu/releases/{version}/release/"
            
        path = f"{spin_name}-{version}-desktop-amd64.iso"
        if spin_name == "ubuntu":
            path = f"ubuntu-{version}-desktop-amd64.iso"
            
        full_url = urljoin(url, path)
        response = requests.head(full_url, allow_redirects=True, timeout=10)
        return response.status_code == 200
    except:
        return False

def load_spins_config():
    try:
        with open('config/spins.yaml', 'r') as f:
            return yaml.safe_load(f)['spins']
    except Exception as e:
        logger.error(f"Failed to load spins config: {e}")
        return {}

def check_version(version):
    logger.info(f"Checking Ubuntu version: {version}")
    spins_config = load_spins_config()
    
    for spin_id in spins_config.keys():
        if verify_iso_availability(version, spin_id):
            logger.info(f"ISO available for {spin_id} {version}")
        else:
            logger.warning(f"ISO not available for {spin_id} {version}")

def main():
    parser = argparse.ArgumentParser(description='Check Ubuntu versions availability')
    parser.add_argument('version', nargs='?', help='Specific version to check (e.g., 24.04.2)')
    args = parser.parse_args()

    if args.version:
        logger.info(f"Checking specific version: {args.version}")
        check_version(args.version)
        return

    versions = get_available_versions()
    if not versions:
        logger.error("No versions found")
        return

    for version in versions:
        try:
            check_version(version)
        except Exception as e:
            logger.error(f"Error checking version {version}: {e}")

if __name__ == '__main__':
    main()