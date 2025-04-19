#!/usr/bin/env python3

import yaml
import requests
import hashlib
import os
import tempfile
import logging
from urllib.parse import urljoin
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MIRROR_URLS = {
    "ubuntu": "https://releases.ubuntu.com/",
    "xubuntu": "https://cdimage.ubuntu.com/xubuntu/releases/",
    "lubuntu": "https://cdimage.ubuntu.com/lubuntu/releases/",
    "kubuntu": "https://cdimage.ubuntu.com/kubuntu/releases/",
    "ubuntu-budgie": "https://cdimage.ubuntu.com/ubuntu-budgie/releases/",
    "ubuntu-mate": "https://cdimage.ubuntu.com/ubuntu-mate/releases/",
    "ubuntu-studio": "https://cdimage.ubuntu.com/ubuntustudio/releases/",
    "ubuntu-unity": "https://cdimage.ubuntu.com/ubuntu-unity/releases/",
    "ubuntu-kylin": "https://cdimage.ubuntu.com/ubuntukylin/releases/"
}

def load_yaml_config(config_file):
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def save_yaml_config(config_file, config_data):
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
    logger.info(f"Updated configuration saved to {config_file}")

def get_latest_release_info(spin_name):
    if spin_name not in MIRROR_URLS:
        return None
    
    url = MIRROR_URLS[spin_name]
    try:
        response = requests.get(url)
        response.raise_for_status()
        versions = re.findall(r'href="(\d+\.\d+(?:\.\d+)?)"', response.text)
        if versions:
            latest = sorted(versions, key=lambda v: [int(x) for x in v.split('.')], reverse=True)[0]
            return latest
    except requests.RequestException as e:
        logger.error(f"Error fetching version for {spin_name}: {e}")
    return None

def download_iso(url):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int(100 * downloaded / total_size)
                        if percent % 10 == 0:
                            logger.info(f"Download progress: {percent}%")
            return temp_file.name
    except Exception as e:
        logger.error(f"Error downloading ISO: {e}")
        return None

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def update_spin_info(config_data, spin_name, version, iso_path):
    file_size = os.path.getsize(iso_path)
    sha256 = calculate_sha256(iso_path)
    size_gb = f"{file_size / (1024*1024*1024):.1f}G"
    
    logger.info(f"New ISO information for {spin_name}:")
    logger.info(f"  Size: {size_gb}")
    logger.info(f"  SHA256: {sha256}")
    
    updated = False
    for group in config_data["spin_groups"].values():
        for spin in group["spins"]:
            if spin["name"] == spin_name and spin["version"] == version:
                spin["files"]["iso"].update({
                    "size": size_gb,
                    "sha256": sha256
                })
                updated = True
    return updated

def resolve_iso_url(spin):
    base_url = MIRROR_URLS[spin["name"]]
    path = spin["files"]["iso"]["path_template"] \
        .replace("{{ release }}", spin["release"]) \
        .replace("{{ name }}", spin["name"]) \
        .replace("{{ version }}", spin["release_title"]) \
        .replace("{{ image_type }}", spin["image_type"]) \
        .replace("{{ arch }}", spin["architectures"][0])
    return urljoin(base_url, path)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Update Ubuntu spin ISO information')
    parser.add_argument('--config', default='config/iso-settings.yaml', help='Path to YAML config file')
    parser.add_argument('--dry-run', action='store_true', help='Check for updates without making changes')
    parser.add_argument('--spin', help='Update specific spin only')
    args = parser.parse_args()

    config_data = load_yaml_config(args.config)
    updated = False

    for group_name, group in config_data["spin_groups"].items():
        for spin in group["spins"]:
            if args.spin and spin["name"] != args.spin:
                continue

            latest_version = get_latest_release_info(spin["name"])
            if not latest_version:
                continue

            if latest_version != spin["version"]:
                logger.info(f"Updating {spin['name']} from {spin['version']} to {latest_version}")
                if not args.dry_run:
                    iso_url = resolve_iso_url(spin)
                    iso_path = download_iso(iso_url)
                    if iso_path:
                        try:
                            if update_spin_info(config_data, spin["name"], spin["version"], iso_path):
                                updated = True
                        finally:
                            os.unlink(iso_path)

    if updated and not args.dry_run:
        save_yaml_config(args.config, config_data)

if __name__ == '__main__':
    main()
