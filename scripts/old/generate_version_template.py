#!/usr/bin/env python3

from ruamel.yaml import YAML
import argparse
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

UBUNTU_SPINS = {
    'ubuntu': {
        'name': 'Ubuntu',
        'url_base': 'https://cdimage.ubuntu.com/ubuntu/releases/{{ version }}/release/',
        'path_template': 'ubuntu-{{ version }}-desktop-amd64.iso'
    },
    'kubuntu': {
        'name': 'Kubuntu',
        'url_base': 'https://cdimage.ubuntu.com/kubuntu/releases/{{ version }}/release/',
        'path_template': 'kubuntu-{{ version }}-desktop-amd64.iso'
    },
    'xubuntu': {
        'name': 'Xubuntu',
        'url_base': 'https://cdimage.ubuntu.com/xubuntu/releases/{{ version }}/release/',
        'path_template': 'xubuntu-{{ version }}-desktop-amd64.iso'
    },
    'lubuntu': {
        'name': 'Lubuntu',
        'url_base': 'https://cdimage.ubuntu.com/lubuntu/releases/{{ version }}/release/',
        'path_template': 'lubuntu-{{ version }}-desktop-amd64.iso'
    },
    'ubuntu-mate': {
        'name': 'Ubuntu MATE',
        'url_base': 'https://cdimage.ubuntu.com/ubuntu-mate/releases/{{ version }}/release/',
        'path_template': 'ubuntu-mate-{{ version }}-desktop-amd64.iso'
    },
    'ubuntu-budgie': {
        'name': 'Ubuntu Budgie',
        'url_base': 'https://cdimage.ubuntu.com/ubuntu-budgie/releases/{{ version }}/release/',
        'path_template': 'ubuntu-budgie-{{ version }}-desktop-amd64.iso'
    },
    'ubuntu-studio': {
        'name': 'Ubuntu Studio',
        'url_base': 'https://cdimage.ubuntu.com/ubuntustudio/releases/{{ version }}/release/',
        'path_template': 'ubuntustudio-{{ version }}-desktop-amd64.iso'
    },
    'edubuntu': {
        'name': 'Edubuntu',
        'url_base': 'https://cdimage.ubuntu.com/edubuntu/releases/{{ version }}/release/',
        'path_template': 'edubuntu-{{ version }}-desktop-amd64.iso'
    }
}

def create_version_template(version):
    """Create a template for a specific Ubuntu version with all spins"""
    template = {
        'version': version,
        'default_settings': {
            'datatype': 'image-downloads',
            'format': 'products:1.0'
        },
        'spin_groups': {}
    }
    
    for spin_id, spin_info in UBUNTU_SPINS.items():
        group = {
            'name': spin_info['name'],
            'content_id': f'org.ubuntu.{spin_id}:{spin_id}',
            'spins': [{
                'name': spin_id,
                'release': version,
                'version': version,
                'release_title': version,
                'release_codename': '',  # Will be filled by update script
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
        template['spin_groups'][spin_id] = group
    
    return template

def main():
    parser = argparse.ArgumentParser(description='Generate Ubuntu version template')
    parser.add_argument('version', help='Ubuntu version (e.g., noble)')
    parser.add_argument('--output-dir', default=os.path.join('config', 'versions'), 
                       help='Output directory for version configs')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    output_file = os.path.join(args.output_dir, f'{args.version}.yaml')

    template = create_version_template(args.version)
    
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    
    with open(output_file, 'w') as f:
        yaml.dump(template, f)
    
    logger.info(f"Generated template for Ubuntu {args.version} at {output_file}")

if __name__ == '__main__':
    main()