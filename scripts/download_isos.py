#!/usr/bin/env python3
"""
Download Ubuntu ISOs with torrent support and local caching.

This script downloads ISOs for all configured Ubuntu spins, with support for:
- BitTorrent downloads (faster, distributed)
- Direct HTTP downloads (fallback)
- Local caching and verification
- Web server setup for local network serving
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ISODownloader:
    def __init__(self, cache_dir, use_torrents=True, verify=True):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.use_torrents = use_torrents
        self.verify = verify
        self.stats = {'downloaded': 0, 'cached': 0, 'failed': 0, 'total_bytes': 0}

    def check_torrent_support(self):
        """Check if transmission-cli is available for torrent downloads."""
        if not self.use_torrents:
            return False

        try:
            subprocess.run(['transmission-cli', '--version'],
                          capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("transmission-cli not found. Install with: apt install transmission-cli")
            return False

    def calculate_sha256(self, file_path):
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def verify_iso(self, iso_path, expected_sha256):
        """Verify ISO integrity."""
        if not self.verify or not expected_sha256:
            return True

        logger.info(f"Verifying {iso_path.name}...")
        actual_sha256 = self.calculate_sha256(iso_path)

        if actual_sha256 == expected_sha256:
            logger.info("✓ Verification successful")
            return True
        else:
            logger.error(f"✗ Verification failed! Expected: {expected_sha256}, Got: {actual_sha256}")
            return False

    def download_torrent(self, torrent_url, output_dir, expected_filename):
        """Download ISO using BitTorrent."""
        logger.info(f"Downloading via torrent: {torrent_url}")

        torrent_file = output_dir / "temp.torrent"

        # Download torrent file
        response = requests.get(torrent_url)
        response.raise_for_status()

        with open(torrent_file, 'wb') as f:
            f.write(response.content)

        # Create kill script for transmission
        kill_script = output_dir / "kill_transmission.sh"
        with open(kill_script, 'w') as f:
            f.write("#!/bin/bash\nkillall transmission-cli\n")
        kill_script.chmod(0o755)

        # Download with transmission
        try:
            subprocess.run([
                'transmission-cli',
                '-f', str(kill_script),
                '-w', str(output_dir),
                '--no-portmap',
                '--download-dir', str(output_dir),
                str(torrent_file)
            ], check=False, timeout=7200)  # 2 hour timeout
        finally:
            torrent_file.unlink(missing_ok=True)
            kill_script.unlink(missing_ok=True)

        # Find downloaded ISO
        isos = list(output_dir.glob('*.iso'))
        if isos:
            return isos[0]
        return None

    def download_http(self, url, output_path):
        """Download ISO using HTTP with progress tracking."""
        logger.info(f"Downloading via HTTP: {url}")

        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        print(f"\rProgress: {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB)",
                              end='', flush=True)
        print()  # New line after progress

        return output_path

    def download_iso(self, spin_name, version, iso_url, torrent_url, sha256, size):
        """Download an ISO with caching support."""
        filename = iso_url.split('/')[-1]
        iso_path = self.cache_dir / filename

        # Check if already cached and valid
        if iso_path.exists():
            if self.verify_iso(iso_path, sha256):
                logger.info(f"✓ Using cached: {filename}")
                self.stats['cached'] += 1
                return iso_path
            else:
                logger.warning(f"Cached file corrupted, re-downloading: {filename}")
                iso_path.unlink()

        # Try torrent download first
        if self.use_torrents and self.check_torrent_support() and torrent_url:
            try:
                result = self.download_torrent(torrent_url, self.cache_dir, filename)
                if result and self.verify_iso(result, sha256):
                    self.stats['downloaded'] += 1
                    self.stats['total_bytes'] += size
                    return result
            except Exception as e:
                logger.warning(f"Torrent download failed: {e}")

        # Fallback to HTTP download
        try:
            self.download_http(iso_url, iso_path)
            if self.verify_iso(iso_path, sha256):
                self.stats['downloaded'] += 1
                self.stats['total_bytes'] += size
                return iso_path
            else:
                iso_path.unlink()
                raise Exception("Verification failed")
        except Exception as e:
            logger.error(f"Download failed: {e}")
            self.stats['failed'] += 1
            return None

    def process_json_file(self, json_file):
        """Process a JSON file and download all ISOs."""
        logger.info(f"Processing {json_file}...")

        with open(json_file) as f:
            data = json.load(f)

        products = data.get('products', {})
        content_id = data.get('content_id', '')

        for product_id, product in products.items():
            versions = product.get('versions', {})

            for version, version_data in versions.items():
                items = version_data.get('items', {})
                iso = items.get('iso', {})

                if not iso:
                    continue

                iso_path = iso.get('path', '')
                sha256 = iso.get('sha256', '')
                size = iso.get('size', 0)

                # Construct URLs
                spin_name = product.get('os', '')
                release = product.get('release', '')

                # Get base URL from version config
                base_url = self.get_base_url(spin_name)
                iso_url = f"{base_url}/{iso_path}"
                torrent_url = f"{iso_url}.torrent" if iso_url.endswith('.iso') else None

                self.download_iso(spin_name, version, iso_url, torrent_url, sha256, size)

    def get_base_url(self, spin_name):
        """Get base URL for a spin."""
        base_urls = {
            'kubuntu': 'https://cdimage.ubuntu.com/kubuntu/releases',
            'xubuntu': 'https://cdimage.ubuntu.com/xubuntu/releases',
            'lubuntu': 'https://cdimage.ubuntu.com/lubuntu/releases',
            'ubuntu-mate': 'https://cdimage.ubuntu.com/ubuntu-mate/releases',
            'ubuntu-budgie': 'https://cdimage.ubuntu.com/ubuntu-budgie/releases',
            'edubuntu': 'https://cdimage.ubuntu.com/edubuntu/releases',
            'ubuntu-studio': 'https://cdimage.ubuntu.com/ubuntustudio/releases',
            'ubuntu-cinnamon': 'https://cdimage.ubuntu.com/ubuntucinnamon/releases',
            'ubuntu': 'https://releases.ubuntu.com',
            'ubuntu-server': 'https://releases.ubuntu.com',
        }
        return base_urls.get(spin_name, '')

    def generate_nginx_config(self):
        """Generate nginx configuration for local serving."""
        config = f"""
# Ubuntu Spins Local Mirror - Nginx Configuration
server {{
    listen 80;
    server_name ubuntu-mirror.local;

    root {self.cache_dir};
    autoindex on;
    autoindex_exact_size off;
    autoindex_format html;

    location / {{
        try_files $uri $uri/ =404;

        # CORS headers for network access
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS';

        # Cache control
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}

    # Health check endpoint
    location /health {{
        return 200 "OK";
        add_header Content-Type text/plain;
    }}
}}
"""
        config_path = self.cache_dir / "nginx.conf"
        with open(config_path, 'w') as f:
            f.write(config)

        logger.info(f"Generated nginx config: {config_path}")
        return config_path

    def generate_simple_server(self):
        """Generate a simple Python HTTP server script."""
        script = f"""#!/usr/bin/env python3
import http.server
import socketserver
import os

PORT = 8080
DIRECTORY = "{self.cache_dir}"

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

os.chdir(DIRECTORY)
with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    print(f"Serving ISOs at http://localhost:{{PORT}}")
    print(f"Directory: {{DIRECTORY}}")
    httpd.serve_forever()
"""
        script_path = self.cache_dir / "serve.py"
        with open(script_path, 'w') as f:
            f.write(script)
        script_path.chmod(0o755)

        logger.info(f"Generated HTTP server script: {script_path}")
        return script_path

    def print_stats(self):
        """Print download statistics."""
        total_gb = self.stats['total_bytes'] / (1024 ** 3)
        logger.info("\n" + "=" * 60)
        logger.info("Download Statistics:")
        logger.info(f"  Downloaded: {self.stats['downloaded']} ISOs")
        logger.info(f"  Cached: {self.stats['cached']} ISOs")
        logger.info(f"  Failed: {self.stats['failed']} ISOs")
        logger.info(f"  Total size: {total_gb:.2f} GB")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Download Ubuntu ISOs for local caching',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all ISOs to /srv/ubuntu-mirror
  %(prog)s --cache-dir /srv/ubuntu-mirror --output-dir output/

  # Download with torrent support (faster)
  %(prog)s --cache-dir /srv/ubuntu-mirror --use-torrents --output-dir output/

  # Download specific spin only
  %(prog)s --cache-dir /srv/ubuntu-mirror --spin kubuntu --output-dir output/

  # Generate server config
  %(prog)s --cache-dir /srv/ubuntu-mirror --generate-server-config --output-dir output/

After downloading:
  # Serve with Python
  cd /srv/ubuntu-mirror && python3 serve.py

  # Or with nginx
  sudo cp /srv/ubuntu-mirror/nginx.conf /etc/nginx/sites-available/ubuntu-mirror
  sudo ln -s /etc/nginx/sites-available/ubuntu-mirror /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx
        """
    )

    parser.add_argument('--cache-dir', required=True,
                       help='Directory to store downloaded ISOs')
    parser.add_argument('--output-dir', default='output/',
                       help='Directory with JSON files (default: output/)')
    parser.add_argument('--spin', help='Download specific spin only')
    parser.add_argument('--use-torrents', action='store_true',
                       help='Use BitTorrent for downloads (requires transmission-cli)')
    parser.add_argument('--no-verify', action='store_true',
                       help='Skip SHA256 verification')
    parser.add_argument('--generate-server-config', action='store_true',
                       help='Generate web server configuration files')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    downloader = ISODownloader(
        cache_dir=args.cache_dir,
        use_torrents=args.use_torrents,
        verify=not args.no_verify
    )

    # Process JSON files
    output_dir = Path(args.output_dir)
    json_files = list(output_dir.glob('*.json'))

    if args.spin:
        json_files = [f for f in json_files if f.stem == args.spin]

    if not json_files:
        logger.error(f"No JSON files found in {output_dir}")
        return 1

    logger.info(f"Found {len(json_files)} spin(s) to process")

    for json_file in json_files:
        downloader.process_json_file(json_file)

    downloader.print_stats()

    # Generate server configs if requested
    if args.generate_server_config:
        downloader.generate_nginx_config()
        downloader.generate_simple_server()
        logger.info("\nTo serve ISOs locally:")
        logger.info(f"  python3 {downloader.cache_dir}/serve.py")

    return 0 if downloader.stats['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
