# Ubuntu Spins by netboot.xyz

This project extends netboot.xyz's Ubuntu support by adding various Ubuntu-based distributions and live images. While the original Ubuntu mini.iso provides a minimal network installer, this project adds support for:

- Ubuntu Desktop
- Kubuntu
- Xubuntu
- Lubuntu
- Ubuntu MATE
- Ubuntu Budgie
- Ubuntu Studio
- Ubuntu Unity
- Ubuntu Kylin
- Edubuntu

## Features

- Automated ISO metadata tracking
- SHA256 checksum verification
- Multiple architecture support
- Automated size and checksum updates
- Integration with netboot.xyz

## Requirements

- Python 3.x
- PyYAML
- requests
- transmission-cli (optional, for torrent downloads)

## Installation

```bash
pip install pyyaml requests
```

For torrent support (optional):
```bash
# macOS
brew install transmission-cli

# Ubuntu/Debian
apt-get install transmission-cli
```

## Usage

### Generate JSON Files

Generate JSON metadata files for netboot.xyz:

```bash
python3 scripts/generate_iso_json.py --config config/iso-settings.yaml --output-dir output/
```

### Update ISO Information

Update SHA256 and size information for ISOs:

```bash
# Check all spins
python3 scripts/update_iso_info.py --config config/iso-settings.yaml

# Dry run (no changes)
python3 scripts/update_iso_info.py --config config/iso-settings.yaml --dry-run

# Update specific spin
python3 scripts/update_iso_info.py --config config/iso-settings.yaml --spin ubuntu

# Update specific version
python3 scripts.update_iso_info.py --config config/iso-settings.yaml --version 24.04

# Use torrent for downloads (requires transmission-cli)
python3 scripts/update_iso_info.py --config config/iso-settings.yaml --use-torrent --download-dir /tmp

# Update specific spin using torrent
python3 scripts.update_iso_info.py --config config/iso-settings.yaml --spin ubuntu --use-torrent
```

## Configuration

The `iso-settings.yaml` file contains the template structure for all Ubuntu spins. Each spin defines:

- Base information (name, version, release)
- ISO file paths and templates
- Architecture support
- SHA256 checksums and file sizes

Example spin configuration:
```yaml
spin_groups:
  ubuntu:
    content_id: com.ubuntu.releases:ubuntu
    spins:
      - name: ubuntu
        image_type: desktop
        version: 24.04.2
        release: noble
        release_codename: Noble Numbat
        release_title: '24.04.2'
        architectures:
          - amd64
        files:
          iso:
            path_template: '{{ release }}/release/{{ name }}-{{ version }}-{{ image_type }}-{{ arch }}.iso'
            size: '3.8G'
            sha256: 'abc123'
```

## Automated Updates

This project uses GitHub Actions for automated maintenance:

### Daily Checks
A GitHub Action runs daily to:
- Check for new Ubuntu spin releases
- Update ISO checksums and sizes
- Create pull requests with updates
- Validate JSON output

### Manual Triggers
You can manually trigger updates:
- Through GitHub Actions web interface
- Using workflow_dispatch events
- Via API with appropriate tokens

### Configuration Updates
The automation handles:
- New Ubuntu releases
- Point releases
- Development versions
- LTS releases

## Integration with netboot.xyz

The generated JSON files are compatible with netboot.xyz's menu system and can be used to:
- Add new boot options
- Provide live boot capabilities
- Enable network installation
- Support multiple Ubuntu variants

## Modifying initrd

To include transmission-cli in the initrd for torrent downloads:

```bash
# Make the script executable
chmod +x scripts/inject_transmission_cli.sh

# Run with sudo to modify initrd
sudo ./scripts/inject_transmission_cli.sh
```

This will create a new initrd.gz with transmission-cli and its dependencies included.
