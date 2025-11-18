#!/usr/bin/env python3
"""
Check for new Ubuntu versions and automatically generate version templates.

This script:
1. Scrapes Ubuntu CDN for available versions
2. Checks which versions we don't have configured yet
3. Verifies ISO availability for each spin
4. Automatically generates version template files
"""

import requests
from bs4 import BeautifulSoup
import logging
import re
import yaml
import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urljoin
from ruamel.yaml import YAML

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Minimum supported version (YY.MM format)
MIN_VERSION = "22.04"

def version_to_float(version):
    """Convert version string to float for comparison."""
    try:
        parts = version.split('.')
        return float(parts[0]) + float(parts[1]) / 100
    except (ValueError, IndexError):
        return 0

def get_existing_versions():
    """Get list of versions we already have configured."""
    versions_dir = Path('config/versions')
    if not versions_dir.exists():
        return set()

    existing = set()
    for yaml_file in versions_dir.glob('*.yaml'):
        version = yaml_file.stem  # filename without extension
        existing.add(version)

    logger.info(f"Found {len(existing)} existing version configs: {sorted(existing)}")
    return existing

def scrape_ubuntu_versions():
    """
    Scrape available Ubuntu versions from multiple sources.
    Returns a set of version strings.
    """
    versions = set()
    min_version_float = version_to_float(MIN_VERSION)

    # Pattern to match version numbers (e.g., 24.04, 24.04.2, 25.04)
    version_pattern = re.compile(r'^(\d{2}\.\d{2}(?:\.\d+)?)/?$')

    sources = [
        'https://cdimage.ubuntu.com/releases/',
        'https://cdimage.ubuntu.com/kubuntu/releases/',
        'https://cdimage.ubuntu.com/xubuntu/releases/',
    ]

    for source_url in sources:
        try:
            logger.debug(f"Checking {source_url}")
            response = requests.get(source_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            for link in soup.find_all('a'):
                href = link.get('href', '')
                match = version_pattern.match(href)
                if match:
                    version = match.group(1)
                    if version_to_float(version) >= min_version_float:
                        versions.add(version)

        except Exception as e:
            logger.warning(f"Error scraping {source_url}: {e}")

    return versions

def check_iso_exists(url):
    """Check if an ISO file exists at the given URL using HEAD request."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.debug(f"Error checking {url}: {e}")
        return False

def verify_spin_availability(version, spin_id, spin_config, release, release_codename):
    """
    Verify that a specific spin ISO is available for download.
    Returns the ISO URL if available, None otherwise.
    """
    # Build the ISO URL based on the spin configuration
    url_base = spin_config['url_base'].rstrip('/')
    
    # Extract filename from template
    filename = spin_config['path_template'].split('/')[-1] \
        .replace('{{ version }}', version) \
        .strip('"')
    
    # Construct full ISO URL
    # For most spins: https://cdimage.ubuntu.com/kubuntu/releases/24.04/release/kubuntu-24.04-desktop-amd64.iso
    full_url = f"{url_base}/{version}/release/{filename}"
    
    # Fix up URL to ensure proper formatting
    full_url = full_url.replace('//', '/').replace('http:/', 'http://').replace('https:/', 'https://')

    # Check if ISO exists
    if check_iso_exists(full_url):
        logger.info(f"✓ Found: {spin_id} {version} at {full_url}")
        return full_url
    else:
        logger.debug(f"✗ Not found: {spin_id} {version} at {full_url}")
        return None

def load_spins_config():
    """Load spins configuration."""
    try:
        with open('config/spins.yaml', 'r') as f:
            return yaml.safe_load(f)['spins']
    except Exception as e:
        logger.error(f"Failed to load spins config: {e}")
        sys.exit(1)

def load_release_codenames():
    """Load release codenames configuration."""
    try:
        with open('config/release_codenames.yaml', 'r') as f:
            return yaml.safe_load(f)['release_codenames']
    except Exception as e:
        logger.error(f"Failed to load release codenames: {e}")
        sys.exit(1)

def get_release_info(version, codenames):
    """Get release name and codename for a version."""
    base_version = '.'.join(version.split('.')[:2])  # Convert 24.04.2 to 24.04
    version_info = codenames.get(base_version, {})
    return {
        'release': version_info.get('release', ''),
        'codename': version_info.get('codename', '')
    }

def create_spin_entry(spin_id, spin_config, version, release, release_codename):
    """Create a spin entry for the version template."""
    url_base = spin_config['url_base'].rstrip('/')

    return {
        'name': spin_id,
        'release': release,
        'version': version,
        'release_title': version,
        'release_codename': release_codename,
        'image_type': 'desktop',
        'architectures': ['amd64'],
        'files': {
            'iso': {
                'path_template': spin_config['path_template'],
                'url': f"{url_base}/{version}/release/",
                'sha256': '',
                'size': 0
            }
        }
    }

def generate_version_template(version, spins_config, codenames):
    """
    Generate a complete version template with all available spins.
    Only includes spins where ISOs are actually available.
    """
    release_info = get_release_info(version, codenames)
    release = release_info['release']
    release_codename = release_info['codename']

    if not release:
        logger.warning(f"No release codename found for version {version}. You may need to add it to release_codenames.yaml")
        # Use a placeholder based on version
        release = f"release-{version.replace('.', '-')}"
        release_codename = f"Ubuntu {version}"

    template = {
        'version': version,
        'datatype': 'image-downloads',
        'format': 'products:1.0',
        'content_id': 'com.ubuntu.releases:ubuntu',
        'spin_groups': {}
    }

    # Check each spin for availability
    available_spins = []
    for spin_id, spin_config in spins_config.items():
        iso_url = verify_spin_availability(version, spin_id, spin_config, release, release_codename)
        if iso_url:
            available_spins.append(spin_id)
            spin_entry = create_spin_entry(spin_id, spin_config, version, release, release_codename)

            template['spin_groups'][spin_id] = {
                'name': spin_config['name'],
                'content_id': spin_config['content_id'],
                'spins': [spin_entry]
            }

    if not available_spins:
        logger.warning(f"No ISOs available for version {version}")
        return None

    logger.info(f"Version {version} has {len(available_spins)} available spins: {', '.join(available_spins)}")
    return template

def save_version_template(version, template):
    """Save version template to YAML file."""
    output_dir = Path('config/versions')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{version}.yaml'

    yaml_handler = YAML()
    yaml_handler.preserve_quotes = True
    yaml_handler.indent(mapping=2, sequence=4, offset=2)
    yaml_handler.default_flow_style = False

    with open(output_file, 'w') as f:
        yaml_handler.dump(template, f)

    logger.info(f"Created version template: {output_file}")
    return output_file

def check_for_new_versions(dry_run=False, check_specific_version=None):
    """
    Main function to check for new versions and generate templates.

    Args:
        dry_run: If True, only report what would be done without creating files
        check_specific_version: If provided, only check this specific version
    """
    spins_config = load_spins_config()
    codenames = load_release_codenames()
    existing_versions = get_existing_versions()

    if check_specific_version:
        # Check specific version only
        versions_to_check = {check_specific_version}
        logger.info(f"Checking specific version: {check_specific_version}")
    else:
        # Discover all available versions
        logger.info("Discovering available Ubuntu versions...")
        all_versions = scrape_ubuntu_versions()

        if not all_versions:
            logger.error("No versions found. Check your internet connection.")
            return False

        logger.info(f"Found {len(all_versions)} available versions: {sorted(all_versions)}")
        versions_to_check = all_versions - existing_versions

    if not versions_to_check:
        logger.info("No new versions to process. All versions are up to date!")
        return True

    logger.info(f"New versions to process: {sorted(versions_to_check)}")

    created_files = []
    for version in sorted(versions_to_check):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing version: {version}")
        logger.info(f"{'='*60}")

        template = generate_version_template(version, spins_config, codenames)

        if template:
            if dry_run:
                logger.info(f"[DRY RUN] Would create template for version {version}")
            else:
                output_file = save_version_template(version, template)
                created_files.append(output_file)
        else:
            logger.warning(f"Skipping version {version} - no ISOs available")

    if created_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Successfully created {len(created_files)} new version templates:")
        for f in created_files:
            logger.info(f"  - {f}")
        logger.info(f"{'='*60}")
        return True
    else:
        logger.info("\nNo new version templates created.")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Check for new Ubuntu versions and generate templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check for all new versions and create templates
  %(prog)s

  # Check specific version
  %(prog)s --version 24.04.3

  # Dry run to see what would be created
  %(prog)s --dry-run

  # Verbose output
  %(prog)s -v
        """
    )
    parser.add_argument('--version', help='Check specific version only (e.g., 24.04.2)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        success = check_for_new_versions(
            dry_run=args.dry_run,
            check_specific_version=args.version
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=args.verbose)
        sys.exit(1)

if __name__ == '__main__':
    main()
