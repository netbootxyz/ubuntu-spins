#!/usr/bin/env python3
"""
Fetch SHA256 checksums from Ubuntu's published SHA256SUMS files.

This is much faster than downloading entire ISOs (4-6GB each).
Ubuntu publishes SHA256SUMS files alongside their ISOs.
"""

import requests
import logging
import argparse
import sys
from pathlib import Path
from ruamel.yaml import YAML

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_sha256sums_file(base_url):
    """
    Fetch and parse SHA256SUMS file from Ubuntu CDN.

    Returns dict: {filename: {'sha256': ..., 'size': ...}}
    """
    sha256sums_url = f"{base_url.rstrip('/')}/SHA256SUMS"

    try:
        response = requests.get(sha256sums_url, timeout=10)
        response.raise_for_status()

        checksums = {}
        for line in response.text.strip().split('\n'):
            if not line.strip() or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) >= 2:
                sha256 = parts[0]
                # Handle both "file" and "*file" formats
                filename = parts[1].lstrip('*')
                checksums[filename] = {'sha256': sha256}

        logger.info(f"Fetched {len(checksums)} checksums from {sha256sums_url}")
        return checksums

    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not fetch SHA256SUMS from {sha256sums_url}: {e}")
        return {}

def get_file_size(url):
    """Get file size using HEAD request."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            size = response.headers.get('content-length')
            return int(size) if size else 0
    except Exception as e:
        logger.debug(f"Could not get size for {url}: {e}")
    return 0

def update_version_checksums(config_file, dry_run=False):
    """
    Update checksums in a version YAML file by fetching SHA256SUMS.

    Args:
        config_file: Path to version YAML file
        dry_run: If True, only show what would be updated
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(config_file, 'r') as f:
        data = yaml.load(f)

    version = data.get('version')
    logger.info(f"Processing version {version} from {config_file}")

    updated_count = 0

    for group_name, group in data.get('spin_groups', {}).items():
        for spin in group.get('spins', []):
            spin_name = spin.get('name')
            iso_info = spin.get('files', {}).get('iso', {})

            if not iso_info:
                continue

            base_url = iso_info.get('url', '').rstrip('/')
            path_template = iso_info.get('path_template', '')

            # Construct the expected ISO filename
            release = spin.get('release', '')
            iso_filename = path_template \
                .replace('{{ release }}', release) \
                .replace('{{ version }}', version) \
                .split('/')[-1]  # Get just the filename

            # Fetch SHA256SUMS file
            checksums = fetch_sha256sums_file(base_url)

            if iso_filename in checksums:
                new_sha256 = checksums[iso_filename]['sha256']

                # Get file size via HEAD request
                iso_url = f"{base_url}/{iso_filename}"
                new_size = get_file_size(iso_url)

                current_sha256 = iso_info.get('sha256', '')
                current_size = iso_info.get('size', 0)

                if current_sha256 != new_sha256 or current_size != new_size:
                    logger.info(f"✓ {spin_name}: {iso_filename}")
                    logger.info(f"  SHA256: {new_sha256}")
                    logger.info(f"  Size: {new_size:,} bytes ({new_size / (1024**3):.2f} GB)")

                    if not dry_run:
                        iso_info['sha256'] = new_sha256
                        iso_info['size'] = new_size
                        updated_count += 1
                    else:
                        logger.info(f"  [DRY RUN] Would update")
                else:
                    logger.info(f"✓ {spin_name}: Already up to date")
            else:
                logger.warning(f"✗ {spin_name}: {iso_filename} not found in SHA256SUMS")
                logger.debug(f"  Available files: {list(checksums.keys())}")

    if updated_count > 0 and not dry_run:
        with open(config_file, 'w') as f:
            yaml.dump(data, f)
        logger.info(f"\n✅ Updated {updated_count} checksums in {config_file}")
    elif dry_run:
        logger.info(f"\n[DRY RUN] Would update {updated_count} checksums")
    else:
        logger.info(f"\n✅ All checksums are up to date")

def main():
    parser = argparse.ArgumentParser(
        description='Fetch SHA256 checksums from Ubuntu SHA256SUMS files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update all checksums in a version file
  %(prog)s --config config/versions/24.04.3.yaml

  # Dry run to see what would be updated
  %(prog)s --config config/versions/24.04.3.yaml --dry-run

  # Update all version files
  for file in config/versions/*.yaml; do
    %(prog)s --config "$file"
  done
        """
    )
    parser.add_argument('--config', required=True,
                       help='Path to version YAML config file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if not Path(args.config).exists():
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)

    try:
        update_version_checksums(args.config, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=args.verbose)
        sys.exit(1)

if __name__ == '__main__':
    main()
