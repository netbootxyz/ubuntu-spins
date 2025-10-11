# Ubuntu Spins - Claude Development Guide

## Project Overview

This project automates the management of Ubuntu spin distributions (Kubuntu, Xubuntu, Lubuntu, Ubuntu MATE, Ubuntu Budgie, Edubuntu) for netboot.xyz's boot-via-ISO method. It discovers new versions, generates metadata, and produces JSON files consumed by netboot.xyz's mini-ISO tool.

## Architecture

### Data Flow
```
Ubuntu CDN → check_new_versions.py → Version Templates (YAML)
                                            ↓
                                    update_iso_info.py (downloads ISOs, calculates SHA256)
                                            ↓
                                    Updated YAML with checksums
                                            ↓
                                    generate_iso_json.py
                                            ↓
                                    JSON files for netboot.xyz
                                            ↓
                                    Embedded in mini-ISO initrd
```

### Directory Structure
```
ubuntu-spins/
├── config/
│   ├── spins.yaml              # Spin definitions (URL patterns, content IDs)
│   ├── release_codenames.yaml  # Version → codename mapping
│   └── versions/               # Per-version YAML configs with SHA256/sizes
│       ├── 22.04.5.yaml
│       ├── 24.04.2.yaml
│       ├── 24.04.3.yaml
│       ├── 24.10.yaml
│       └── 25.04.yaml
├── scripts/
│   ├── check_new_versions.py        # Discovers new versions, creates templates
│   ├── fetch_checksums.py           # Fast checksum fetching from SHA256SUMS files
│   ├── update_iso_info.py           # Downloads ISOs, calculates SHA256/sizes (slower)
│   ├── generate_iso_json.py         # Aggregates YAMLs → JSON
│   └── validate_json.py             # Validates JSON output format
├── output/
│   └── *.json                  # Generated JSON files (one per spin)
└── .github/workflows/
    ├── check-versions.yml      # Daily version checker (creates PRs)
    ├── update-iso-info.yml     # Manual ISO updater
    └── process-iso.yml         # Builds custom initrd with JSONs

```

## Core Scripts

### 1. `check_new_versions.py` (Primary Automation)
**Purpose**: Discover new Ubuntu versions and create templates

**Usage**:
```bash
# Check for all new versions
python3 scripts/check_new_versions.py

# Check specific version
python3 scripts/check_new_versions.py --version 24.04.3

# Dry run (show what would be done)
python3 scripts/check_new_versions.py --dry-run

# Verbose output
python3 scripts/check_new_versions.py -v
```

**What it does**:
1. Scrapes Ubuntu CDN for version directories
2. Compares against existing `config/versions/*.yaml`
3. For each new version:
   - Checks ISO availability (HEAD request) for each spin
   - Creates YAML template if ISOs exist
   - Sets SHA256/size to empty (filled later by update_iso_info.py)

### 2. `fetch_checksums.py` (Fast Checksum Fetcher - Recommended)
**Purpose**: Fetch SHA256 checksums from published SHA256SUMS files (100x faster)

**Usage**:
```bash
# Fetch checksums for all spins in a version
python3 scripts/fetch_checksums.py --config config/versions/25.10.yaml

# Fetch with verbose output
python3 scripts/fetch_checksums.py --config config/versions/25.10.yaml -v
```

**What it does**:
1. Reads version YAML
2. Fetches SHA256SUMS file from each spin's release directory
3. Parses checksums and file sizes from the published data
4. Updates YAML with checksums (completes in ~2-3 seconds)

**Performance**: ~2.5 seconds vs. ~4 hours for downloading full ISOs

### 3. `update_iso_info.py` (Checksum Calculator - Slow Method)
**Purpose**: Download ISOs and calculate SHA256 hashes (backup method)

**Usage**:
```bash
# Update all spins in a version config
python3 scripts/update_iso_info.py --config config/versions/24.04.3.yaml

# Update specific spin only
python3 scripts/update_iso_info.py --config config/versions/24.04.3.yaml --spin kubuntu

# Use torrent for faster download
python3 scripts/update_iso_info.py --config config/versions/24.04.3.yaml --use-torrent
```

**What it does**:
1. Reads version YAML
2. Downloads each ISO (direct or torrent) - 4-7GB per ISO
3. Calculates SHA256 and file size locally
4. Updates YAML with checksums

**Note**: This method is 100x slower than fetch_checksums.py. Use only when SHA256SUMS files are unavailable.

### 4. `generate_iso_json.py` (JSON Generator)
**Purpose**: Aggregate all versions into JSON format for netboot.xyz

**Usage**:
```bash
python3 scripts/generate_iso_json.py --output-dir output/
```

**What it does**:
1. Reads all `config/versions/*.yaml` files
2. Aggregates by spin (kubuntu.json, xubuntu.json, etc.)
3. Only includes entries with valid SHA256 and size > 0
4. Outputs JSON in netboot.xyz format

## Configuration Files

### `config/spins.yaml`
Defines each Ubuntu spin with URL patterns:
```yaml
spins:
  kubuntu:
    name: Kubuntu
    content_id: "org.kubuntu:kubuntu"
    url_base: https://cdimage.ubuntu.com/kubuntu/releases/
    path_template: "{{ release }}/release/kubuntu-{{ version }}-desktop-amd64.iso"
```

### `config/release_codenames.yaml`
Maps versions to Ubuntu release names:
```yaml
release_codenames:
  "24.04":
    codename: "Noble Numbat"
    release: "noble"
```

### `config/versions/{version}.yaml`
Per-version configuration with all spins:
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
            sha256: "abc123..."  # Filled by update_iso_info.py
            size: 4527759360
```

## GitHub Workflows

### `check-versions.yml` (Automated Version Discovery)
- **Trigger**: Daily cron (00:00 UTC) or manual
- **What it does**: Runs `check_new_versions.py`, creates PR with new templates
- **Manual inputs**: `version` (specific version), `dry_run` (preview mode)

### `update-iso-info.yml` (Manual Checksum Update - Slow Method)
- **Trigger**: Manual dispatch only
- **What it does**: Downloads full ISOs, calculates checksums, updates YAMLs
- **Manual inputs**: `spin` (specific spin), `version`, `use_torrent`
- **Note**: This is the slow method (downloads 4-7GB ISOs). Consider using `fetch_checksums.py` instead (100x faster)

### `process-iso.yml` (Mini-ISO Builder)
- **Trigger**: Push to master or manual
- **What it does**:
  1. Builds mini-iso-tools
  2. Extracts vmlinuz/initrd from mini-ISO
  3. Generates JSON files
  4. Embeds JSONs in initrd
  5. Creates draft release

## Current Status

### ✅ Working
- Version template generation
- ISO availability checking
- JSON aggregation
- Multi-version support
- GitHub workflow automation

### ⚠️ Issues Found & Fixed
- ✅ Empty SHA256 in 24.04.2 Xubuntu → Need to run update_iso_info.py
- ✅ Missing 25.10 codename → Added "Questing Quetzel"
- ✅ Script only logged warnings → Now creates templates
- ✅ No requirements.txt → Created
- ✅ Workflow references non-existent files → Fixed

### 🔧 Known Gaps
1. **Ubuntu Desktop/Server not included** - Only spins are tracked (could expand to official Ubuntu)
2. **Checksum fetching optimized** - Now uses SHA256SUMS files (via fetch_checksums.py) instead of downloading entire ISOs
3. **Validation implemented** - validate_json.py ensures JSON output compatibility
4. **Only amd64 architecture** - No arm64 support yet
5. **Manual ISO updates** - update_iso_info.py requires manual trigger for checksum updates

## Recommended Workflow for Adding New Versions

### Automated (Recommended)
1. Wait for daily workflow to detect new version
2. Review PR from `check-versions` workflow
3. Merge PR (adds templates with empty checksums)
4. Fill checksums using fast method: `python3 scripts/fetch_checksums.py --config config/versions/{VERSION}.yaml`
5. Generate JSON: `python3 scripts/generate_iso_json.py --output-dir output/`
6. Commit and push changes

### Manual (Fast Method)
1. Run: `python3 scripts/check_new_versions.py --version {VERSION}`
2. Verify: `config/versions/{VERSION}.yaml` created
3. Fetch checksums (fast): `python3 scripts/fetch_checksums.py --config config/versions/{VERSION}.yaml -v`
4. Generate JSON: `python3 scripts/generate_iso_json.py --output-dir output/`
5. Validate: `python3 scripts/validate_json.py`
6. Commit and push

### Manual (Slow Method - Backup)
Use this only if SHA256SUMS files are unavailable:
1. Run: `python3 scripts/check_new_versions.py --version {VERSION}`
2. Verify: `config/versions/{VERSION}.yaml` created
3. Download ISOs and calculate checksums (slow): `python3 scripts/update_iso_info.py --config config/versions/{VERSION}.yaml`
4. Generate JSON: `python3 scripts/generate_iso_json.py --output-dir output/`
5. Commit and push

## Critical Paths

### Path 1: New Version Discovery → netboot.xyz
```
check_new_versions.py → version YAML → update_iso_info.py →
generate_iso_json.py → JSON files → process-iso.yml →
Mini-ISO with embedded JSONs → netboot.xyz
```

### Path 2: ISO Availability Verification
```
check_new_versions.py → HEAD request to CDN →
Only creates template if ISO exists → Prevents broken configs
```

## Dependencies

Install with: `pip install -r requirements.txt`
- requests (HTTP client)
- beautifulsoup4 (HTML parsing for version scraping)
- pyyaml (YAML reading)
- ruamel.yaml (YAML writing with formatting preservation)
- lxml (BS4 parser backend)

## Testing Commands

```bash
# Check what new versions would be added (dry run)
python3 scripts/check_new_versions.py --dry-run

# Test specific version
python3 scripts/check_new_versions.py --version 25.10 --dry-run

# Generate JSONs and verify output
python3 scripts/generate_iso_json.py --output-dir output/
ls -lh output/

# Verify JSON structure
jq . output/kubuntu.json | head -50
```

## Troubleshooting

### Issue: Script says "No ISOs available"
- **Cause**: ISOs not yet published on CDN for that version
- **Fix**: Wait for Ubuntu to publish release, or check URL manually

### Issue: Empty SHA256/size in YAML
- **Cause**: Template created but checksums not calculated
- **Fix**: Run `update_iso_info.py` on that config file

### Issue: JSON missing versions
- **Cause**: generate_iso_json.py skips entries with empty SHA256 or size=0
- **Fix**: Update checksums first, then regenerate JSON

### Issue: Workflow fails with "module not found"
- **Cause**: Missing dependencies
- **Fix**: Ensure `requirements.txt` is used in workflow

## Next Development Priorities

### High Priority
1. **Automatic checksum updates** - Integrate fetch_checksums.py into check-versions workflow
2. **Add official Ubuntu releases** - Expand beyond just spins to include ubuntu-desktop, ubuntu-server
3. **Better error handling** - Retry logic, partial failure recovery

### Medium Priority
4. **arm64 architecture support** - Expand to more architectures
5. **Testing framework** - Unit tests for scripts
6. **Version comparison in PRs** - Show diffs between versions

### Low Priority
7. **Multiple image types** - Live, Minimal, Netboot variants
8. **Checksums for vmlinuz/initrd** - In process-iso workflow
9. **Metrics dashboard** - Track version coverage
10. **Automated deprecated version cleanup** - Remove EOL versions

## File Ownership & Dependencies

| File | Generated By | Consumed By |
|------|-------------|-------------|
| `config/spins.yaml` | Manual | check_new_versions, update_iso_info |
| `config/release_codenames.yaml` | Manual | check_new_versions, generate_iso_json |
| `config/versions/*.yaml` | check_new_versions | update_iso_info, generate_iso_json |
| `output/*.json` | generate_iso_json | process-iso workflow, netboot.xyz |
| `vmlinuz`, `initrd` | process-iso workflow | netboot.xyz users |

## Important Notes

- **Both desktop and server ISOs are supported** - The system handles both image types
- **Version templates are created with empty checksums** - Run update_iso_info.py or fetch_checksums.py to fill them
- **JSON generation skips incomplete entries** - Ensures only valid data reaches users
- **process-iso.yml** is the final step that packages everything for netboot.xyz
- **Generated JSON format** matches netboot.xyz's expected schema (products:1.0)
- **Checksum fetching is fast** - fetch_checksums.py parses SHA256SUMS files (100x faster than downloading ISOs)
