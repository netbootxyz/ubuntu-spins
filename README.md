# Ubuntu Spins for netboot.xyz

Automated management of Ubuntu spin distributions (Kubuntu, Xubuntu, Lubuntu, Ubuntu MATE, Ubuntu Budgie, Edubuntu) for [netboot.xyz](https://netboot.xyz)'s boot-via-ISO method.

## What This Does

This repository automatically:
- Discovers new Ubuntu spin releases
- Fetches SHA256 checksums and file sizes
- Generates JSON metadata files
- Packages everything for netboot.xyz's mini-ISO

Users can then boot any Ubuntu flavor directly from netboot.xyz without pre-downloading ISOs.

## Supported Distributions

| Distribution | Versions | Status |
|-------------|----------|--------|
| **Kubuntu** | 22.04.5, 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |
| **Xubuntu** | 22.04.5, 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |
| **Lubuntu** | 22.04.5, 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |
| **Ubuntu MATE** | 22.04.5, 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |
| **Ubuntu Budgie** | 22.04.5, 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |
| **Edubuntu** | 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |
| **Ubuntu Studio** | 22.04.5, 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |
| **Ubuntu Cinnamon** | 24.04.2, 24.04.3, 24.10, 25.04, 25.10 | ✅ Active |

**Note**: Point releases (e.g., 24.04.2 → 24.04.3) are superseded by newer ones. Ubuntu removes older ISOs from their CDN.

## Quick Start

### Requirements

```bash
pip install -r requirements.txt
```

### Check for New Versions

```bash
# Discover all new versions
python3 scripts/check_new_versions.py

# Check specific version
python3 scripts/check_new_versions.py --version 24.10

# Dry run (preview only)
python3 scripts/check_new_versions.py --dry-run
```

### Fetch Checksums (Fast!)

Instead of downloading multi-GB ISOs, fetch checksums from Ubuntu's published SHA256SUMS files:

```bash
# Update checksums for a specific version
python3 scripts/fetch_checksums.py --config config/versions/24.04.3.yaml

# Update all versions
for file in config/versions/*.yaml; do
  python3 scripts/fetch_checksums.py --config "$file"
done
```

### Generate JSON Files

```bash
python3 scripts/generate_iso_json.py --output-dir output/
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Version Discovery                                            │
│    check_new_versions.py                                        │
│    ├─ Scrapes cdimage.ubuntu.com for version directories       │
│    ├─ Compares against existing configs                        │
│    └─ Creates YAML templates (empty checksums)                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Checksum Fetching                                            │
│    fetch_checksums.py                                           │
│    ├─ Fetches SHA256SUMS from Ubuntu CDN                       │
│    ├─ Extracts checksums and file sizes                        │
│    └─ Updates YAML files (no ISO download needed!)             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. JSON Generation                                              │
│    generate_iso_json.py                                         │
│    ├─ Aggregates all version YAMLs                             │
│    ├─ Groups by spin (kubuntu.json, xubuntu.json, etc.)        │
│    └─ Outputs in netboot.xyz format                            │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Mini-ISO Packaging                                           │
│    process-iso.yml (GitHub Actions)                             │
│    ├─ Downloads Ubuntu mini-ISO                                │
│    ├─ Extracts vmlinuz/initrd                                  │
│    ├─ Embeds JSON files in initrd                              │
│    ├─ Repackages complete bootable ISO                         │
│    └─ Releases ISO + vmlinuz/initrd + checksums                │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
ubuntu-spins/
├── config/
│   ├── spins.yaml                # Spin definitions (URLs, content IDs)
│   ├── release_codenames.yaml    # Version → codename mapping
│   └── versions/                 # Per-version configs
│       ├── 22.04.5.yaml
│       ├── 24.04.2.yaml
│       ├── 24.04.3.yaml
│       ├── 24.10.yaml
│       └── 25.04.yaml
├── scripts/
│   ├── check_new_versions.py     # Version discovery & template creation
│   ├── fetch_checksums.py        # Fast checksum fetching (NEW!)
│   ├── update_iso_info.py        # Legacy ISO downloader (slow)
│   └── generate_iso_json.py      # JSON aggregator
├── output/
│   ├── kubuntu.json              # Generated JSON files
│   ├── xubuntu.json
│   └── ... (one per spin)
└── .github/workflows/
    ├── check-versions.yml        # Daily automation
    ├── update-iso-info.yml       # Manual ISO updates
    └── process-iso.yml           # Mini-ISO builder
```

## Scripts Reference

### `check_new_versions.py`
Discovers new Ubuntu versions and creates templates.

**Features**:
- Scrapes Ubuntu CDN for available versions
- Verifies ISO availability with HEAD requests
- Creates version templates automatically
- Skips versions without available ISOs

**Examples**:
```bash
# Check for all new versions
python3 scripts/check_new_versions.py

# Check specific version
python3 scripts/check_new_versions.py --version 25.10

# Dry run
python3 scripts/check_new_versions.py --dry-run

# Verbose output
python3 scripts/check_new_versions.py -v
```

### `fetch_checksums.py` ⚡ NEW!
Fetches SHA256 checksums from Ubuntu's published files (no ISO download needed).

**Why this is better**:
- 100x faster than downloading ISOs
- Fetches from official SHA256SUMS files
- Uses HEAD requests for file sizes
- Perfect for automation

**Examples**:
```bash
# Update single version
python3 scripts/fetch_checksums.py --config config/versions/24.04.3.yaml

# Dry run
python3 scripts/fetch_checksums.py --config config/versions/24.04.3.yaml --dry-run

# Update all versions
for file in config/versions/*.yaml; do
  python3 scripts/fetch_checksums.py --config "$file"
done
```

### `generate_iso_json.py`
Aggregates version YAMLs into JSON format for netboot.xyz.

**Features**:
- Combines all versions per spin
- Only includes entries with valid checksums
- Outputs in netboot.xyz products:1.0 format
- Supports version aliases (e.g., "24.04" and "noble")

**Examples**:
```bash
python3 scripts/generate_iso_json.py --output-dir output/
```

### `update_iso_info.py` (Legacy)
Downloads ISOs and calculates checksums. **Prefer `fetch_checksums.py` instead** for speed.

**Examples**:
```bash
# Update specific version (slow - downloads ISOs)
python3 scripts/update_iso_info.py --config config/versions/24.04.3.yaml

# Update single spin only
python3 scripts/update_iso_info.py --config config/versions/24.04.3.yaml --spin kubuntu

# Use torrent (faster, requires transmission-cli)
python3 scripts/update_iso_info.py --config config/versions/24.04.3.yaml --use-torrent
```

## GitHub Actions

### Daily Version Checker
**Workflow**: `.github/workflows/check-versions.yml`
**Trigger**: Daily at 00:00 UTC or manual

Automatically discovers new versions and creates a PR with templates.

**Manual triggers**:
- `version`: Check specific version (e.g., "24.10")
- `dry_run`: Preview without creating PR

### Manual ISO Updater
**Workflow**: `.github/workflows/update-iso-info.yml`
**Trigger**: Manual only

Downloads ISOs and updates checksums (slow, use sparingly).

**Manual inputs**:
- `spin`: Update specific spin only
- `version`: Update specific version
- `use_torrent`: Use torrents for faster download

### Mini-ISO Builder
**Workflow**: `.github/workflows/process-iso.yml`
**Trigger**: Push to master, daily, or manual

Builds the netboot.xyz mini-ISO with embedded JSON files.

**What it does**:
1. Downloads the latest Ubuntu mini-ISO
2. Extracts vmlinuz and initrd
3. Embeds all spin JSON files into the initrd
4. Repackages everything into a standalone bootable ISO
5. Creates draft release with:
   - `ubuntu-netbootxyz-mini.iso` - Complete bootable ISO
   - `vmlinuz` + `initrd` - For PXE/network boot
   - SHA256 and MD5 checksums for verification

**Usage**:
- Boot the ISO directly on any system (BIOS or UEFI)
- Or use vmlinuz/initrd for network booting via netboot.xyz

## Configuration Files

### `config/spins.yaml`
Defines each Ubuntu spin with URL patterns and identifiers.

```yaml
spins:
  kubuntu:
    name: Kubuntu
    content_id: "org.kubuntu:kubuntu"
    url_base: https://cdimage.ubuntu.com/kubuntu/releases/
    path_template: "{{ release }}/release/kubuntu-{{ version }}-desktop-amd64.iso"
```

### `config/release_codenames.yaml`
Maps Ubuntu versions to release codenames.

```yaml
release_codenames:
  "24.04":
    codename: "Noble Numbat"
    release: "noble"
```

### `config/versions/{version}.yaml`
Per-version configuration with all spins and their checksums.

```yaml
version: 24.04.3
spin_groups:
  kubuntu:
    spins:
      - name: kubuntu
        version: 24.04.3
        release: noble
        files:
          iso:
            sha256: "8c69dd380e5a8969b77ca1708da59f0b9a50d0c151f0a65917180585697dd1e6"
            size: 4560015360
```

## Maintenance

### Adding a New Ubuntu Release Codename

When Ubuntu announces a new version:

1. Update `config/release_codenames.yaml`:
```yaml
release_codenames:
  "25.10":
    codename: "Questing Quetzel"
    release: "questing"
```

2. Run version checker:
```bash
python3 scripts/check_new_versions.py --version 25.10
```

### Adding a New Spin

To add a new Ubuntu flavor (e.g., Ubuntu Cinnamon):

1. Add to `config/spins.yaml`:
```yaml
spins:
  ubuntu-cinnamon:
    name: Ubuntu Cinnamon
    content_id: "org.ubuntucinnamon:ubuntu-cinnamon"
    url_base: https://cdimage.ubuntu.com/ubuntu-cinnamon/releases/
    path_template: "{{ release }}/release/ubuntu-cinnamon-{{ version }}-desktop-amd64.iso"
```

2. Run version checker to detect all available versions:
```bash
python3 scripts/check_new_versions.py
```

## Troubleshooting

### "No ISOs available for version X"
**Cause**: Ubuntu hasn't published ISOs for that version yet, or removed them.

**Solution**: Wait for release, or check if a newer point release exists (e.g., use 24.04.3 instead of 24.04.2).

### "SHA256SUMS file not found"
**Cause**: Version is too old or was removed from Ubuntu's CDN.

**Solution**: These versions are no longer downloadable. Consider removing the version config.

### Empty checksums in JSON output
**Cause**: Version YAML has empty `sha256` or `size: 0`.

**Solution**: Run `fetch_checksums.py` to update:
```bash
python3 scripts/fetch_checksums.py --config config/versions/24.04.3.yaml
```

### Workflow fails with "module not found"
**Cause**: Missing Python dependencies.

**Solution**: Ensure workflow uses `pip install -r requirements.txt`.

## Performance Notes

### Old Method (update_iso_info.py)
- Downloads 4-6 GB ISOs per spin
- 6 spins × 4 GB = 24+ GB download
- Takes hours on slow connections
- Requires significant disk space

### New Method (fetch_checksums.py)
- Fetches ~1 KB SHA256SUMS files
- Uses HEAD requests for file sizes
- Completes in seconds
- No disk space needed

**Always prefer `fetch_checksums.py`** unless you specifically need to verify ISOs locally.

## Contributing

### Reporting Issues
- Missing versions: Check if ISOs exist on [Ubuntu CDN](https://cdimage.ubuntu.com/)
- Script errors: Run with `-v` flag and include full output
- New spin requests: Provide official Ubuntu CDN URL

### Development Setup
```bash
git clone https://github.com/netbootxyz/ubuntu-spins.git
cd ubuntu-spins
pip install -r requirements.txt
```

### Testing Changes
```bash
# Test version discovery
python3 scripts/check_new_versions.py --dry-run -v

# Test checksum fetching
python3 scripts/fetch_checksums.py --config config/versions/24.04.3.yaml --dry-run

# Test JSON generation
python3 scripts/generate_iso_json.py --output-dir output/
jq . output/kubuntu.json | head -50
```

## License

This project is maintained by the netboot.xyz team for automated Ubuntu spin management.

## Links

- [netboot.xyz](https://netboot.xyz) - Main project
- [Ubuntu CDN](https://cdimage.ubuntu.com/) - ISO source
- [Issue Tracker](https://github.com/netbootxyz/ubuntu-spins/issues) - Report problems

## Changelog

### 2025-10-11
- ✨ **NEW**: Complete bootable ISO now included in releases (`ubuntu-netbootxyz-mini.iso`)
- ✨ Added `fetch_checksums.py` for fast checksum fetching (100x faster)
- ✨ Complete rewrite of `check_new_versions.py` with automatic template generation
- ✅ Added Ubuntu 25.10 "Questing Quokka" support with 8 spins
- ✅ Added Ubuntu Studio and Ubuntu Cinnamon flavors
- ✅ Added Ubuntu 24.04.3 support
- 🔧 Fixed missing Xubuntu 24.04.2 checksum (ISO removed by Ubuntu)
- 🔧 Fixed broken `update-iso-info.yml` workflow
- 🧹 Removed deprecated `generate_version_template.py` script
- 📝 Created comprehensive documentation (README, claude.md, VALIDATION.md)
- 🐛 Fixed initrd repacking to handle variable directory structures

### Earlier
- Initial project structure
- Basic version management
- GitHub Actions automation
