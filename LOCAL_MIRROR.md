# Local ISO Mirror Setup Guide

This guide explains how to set up a local Ubuntu ISO mirror for faster deployments and offline access.

## Why Use a Local Mirror?

- **Faster downloads** - Download once, serve to all machines on your network
- **Bandwidth savings** - Avoid re-downloading same ISOs
- **Offline access** - No internet required after initial download
- **BitTorrent support** - Faster, distributed downloads
- **Web serving** - Host ISOs on your local network

## Quick Start

### 1. Download ISOs

```bash
# Install dependencies
pip install -r requirements.txt

# Download all ISOs with torrent support (recommended)
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --output-dir output/ \
  --use-torrents \
  --generate-server-config

# Or download specific spin only
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --output-dir output/ \
  --spin kubuntu \
  --use-torrents
```

### 2. Serve ISOs Locally

**Option A: Simple Python Server**
```bash
cd /srv/ubuntu-mirror
python3 serve.py
# Access at http://localhost:8080
```

**Option B: Nginx (Better Performance)**
```bash
sudo cp /srv/ubuntu-mirror/nginx.conf /etc/nginx/sites-available/ubuntu-mirror
sudo ln -s /etc/nginx/sites-available/ubuntu-mirror /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
# Access at http://ubuntu-mirror.local
```

### 3. Configure Mini-ISO to Use Local Mirror

Add kernel parameter when booting the mini-ISO:

```
ubuntu-mirror=http://192.168.1.100:8080
```

Or set via kernel command line:
```
casper/vmlinuz ... ubuntu-mirror=http://192.168.1.100:8080
```

## Detailed Setup

### Prerequisites

**For BitTorrent downloads (recommended):**
```bash
# Ubuntu/Debian
sudo apt install transmission-cli

# RHEL/CentOS
sudo yum install transmission-cli

# macOS
brew install transmission-cli
```

**For Python dependencies:**
```bash
pip install -r requirements.txt
```

### Download Script Options

| Option | Description |
|--------|-------------|
| `--cache-dir DIR` | Directory to store ISOs (required) |
| `--output-dir DIR` | Directory with JSON files (default: output/) |
| `--spin NAME` | Download specific spin only (e.g., kubuntu) |
| `--use-torrents` | Use BitTorrent (faster, requires transmission-cli) |
| `--no-verify` | Skip SHA256 verification |
| `--generate-server-config` | Generate nginx and Python server configs |
| `-v, --verbose` | Verbose output |

### Download Examples

**Download everything with torrents:**
```bash
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --output-dir output/ \
  --use-torrents \
  -v
```

**Download only Kubuntu (HTTP fallback):**
```bash
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --output-dir output/ \
  --spin kubuntu
```

**Download without verification (faster, not recommended):**
```bash
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --output-dir output/ \
  --use-torrents \
  --no-verify
```

## Architecture

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Download ISOs (One Time)                                 │
│    download_isos.py                                         │
│    ├─ Read JSON files (output/*.json)                      │
│    ├─ Check local cache                                    │
│    ├─ Download via BitTorrent (preferred)                  │
│    ├─ Fallback to HTTP if torrent fails                    │
│    └─ Verify SHA256 checksums                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Serve ISOs Locally                                       │
│    serve.py or nginx                                        │
│    ├─ HTTP server on port 8080/80                          │
│    ├─ Directory listing enabled                            │
│    ├─ CORS headers for network access                      │
│    └─ Cache headers (30 days)                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Mini-ISO Detects Local Mirror                           │
│    (Future: mini-iso-tools enhancement)                    │
│    ├─ Check ubuntu-mirror= kernel parameter                │
│    ├─ Try local mirror first                               │
│    └─ Fallback to official CDN                             │
└─────────────────────────────────────────────────────────────┘
```

### Directory Structure

After downloading, your cache directory will look like:

```
/srv/ubuntu-mirror/
├── kubuntu-25.10-desktop-amd64.iso
├── xubuntu-25.10-desktop-amd64.iso
├── lubuntu-25.10-desktop-amd64.iso
├── ubuntu-mate-25.10-desktop-amd64.iso
├── ubuntu-budgie-25.10-desktop-amd64.iso
├── edubuntu-25.10-desktop-amd64.iso
├── ubuntustudio-25.10-desktop-amd64.iso
├── ubuntucinnamon-25.10-desktop-amd64.iso
├── nginx.conf         # Generated nginx config
└── serve.py           # Python HTTP server script
```

## Network Setup

### DNS Configuration (Optional)

Add to `/etc/hosts` on client machines:
```
192.168.1.100  ubuntu-mirror.local
```

### Firewall Rules

**Allow HTTP traffic:**
```bash
# Ubuntu/Debian
sudo ufw allow 80/tcp
sudo ufw allow 8080/tcp

# RHEL/CentOS
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

## Performance Optimization

### Nginx Tuning

For serving multiple concurrent clients:

```nginx
# Add to nginx.conf
worker_processes auto;
worker_connections 1024;

# Inside http block
sendfile on;
tcp_nopush on;
tcp_nodelay on;

# Increase buffer sizes
client_body_buffer_size 128k;
client_max_body_size 100M;
```

### Storage Recommendations

- **SSD recommended** for serving ISOs (faster read speeds)
- **Minimum 50 GB** free space for all spins
- **100 GB** recommended for multiple versions

## Disk Space Requirements

Approximate sizes per Ubuntu version:

| Distribution | Typical Size | Notes |
|-------------|--------------|-------|
| Kubuntu | 4.5 - 5 GB | KDE Plasma desktop |
| Xubuntu | 4 - 4.5 GB | Xfce desktop |
| Lubuntu | 3 - 3.5 GB | LXQt desktop (lightest) |
| Ubuntu MATE | 3.5 - 4 GB | MATE desktop |
| Ubuntu Budgie | 3.5 - 4 GB | Budgie desktop |
| Edubuntu | 6 - 7 GB | Education-focused |
| Ubuntu Studio | 7 - 8 GB | Multimedia production |
| Ubuntu Cinnamon | 4.5 - 5 GB | Cinnamon desktop |

**Total for all 8 spins**: ~35-40 GB per Ubuntu version

## Automation

### Cron Job for Updates

Update ISOs weekly:

```bash
# Add to /etc/cron.weekly/update-ubuntu-mirror
#!/bin/bash
cd /path/to/ubuntu-spins
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --output-dir output/ \
  --use-torrents \
  >> /var/log/ubuntu-mirror-update.log 2>&1
```

### Systemd Service (Auto-start)

Create `/etc/systemd/system/ubuntu-mirror.service`:

```ini
[Unit]
Description=Ubuntu ISO Mirror HTTP Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/srv/ubuntu-mirror
ExecStart=/usr/bin/python3 /srv/ubuntu-mirror/serve.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ubuntu-mirror
sudo systemctl start ubuntu-mirror
```

## Troubleshooting

### ISOs Not Downloading

**Check transmission-cli:**
```bash
transmission-cli --version
```

**Check disk space:**
```bash
df -h /srv/ubuntu-mirror
```

**Try HTTP fallback:**
```bash
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --output-dir output/
```

### Verification Failures

**Re-download specific ISO:**
```bash
rm /srv/ubuntu-mirror/kubuntu-25.10-desktop-amd64.iso
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --spin kubuntu
```

**Skip verification (not recommended):**
```bash
python3 scripts/download_isos.py \
  --cache-dir /srv/ubuntu-mirror \
  --no-verify
```

### Server Not Accessible

**Check if server is running:**
```bash
netstat -tuln | grep 8080
# or
ss -tuln | grep 8080
```

**Test locally:**
```bash
curl http://localhost:8080
```

**Check firewall:**
```bash
sudo ufw status
# or
sudo firewall-cmd --list-all
```

## Advanced: Custom Mirror URLs

### Future Enhancement (Requires mini-iso-tools update)

The mini-iso-tools would need to support custom mirror URLs. Here's the proposed implementation:

**Kernel parameter:**
```
ubuntu-mirror=http://192.168.1.100:8080
```

**Mini-iso-tools logic (json.c):**
```c
const char *get_iso_url(iso_data_t *iso, const char *mirror_url) {
    if (mirror_url && strlen(mirror_url) > 0) {
        // Extract filename from ISO path
        const char *filename = strrchr(iso->path, '/');
        if (filename) {
            return saprintf("%s/%s", mirror_url, filename + 1);
        }
    }
    return iso->url;  // Fallback to official URL
}
```

## Security Considerations

- **HTTPS**: For production, use nginx with Let's Encrypt SSL
- **Authentication**: Add basic auth for access control
- **Integrity**: Always verify SHA256 checksums
- **Updates**: Keep ISOs updated with security patches

## See Also

- [README.md](README.md) - Main project documentation
- [scripts/download_isos.py](scripts/download_isos.py) - Download script
- [mini-iso-tools](https://github.com/netbootxyz/mini-iso-tools) - Boot menu tool
