#!/usr/bin/env python3

from ruamel.yaml import YAML
import argparse
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_spins_config():
    """Load spins configuration from YAML file"""
    yaml = YAML()
    spins_file = os.path.join('config', 'spins.yaml')
    with open(spins_file, 'r') as f:
        return yaml.load(f)['spins']

def load_release_codenames():
    """Load release codenames from YAML file"""
    yaml = YAML()
    codenames_file = os.path.join('config', 'release_codenames.yaml')
    with open(codenames_file, 'r') as f:
        return yaml.load(f)['release_codenames']

def create_version_template(version):
    """Create a template for a specific Ubuntu version with configured spins"""
    template = {
        'version': version,
        'default_settings': {
            'datatype': 'image-downloads',
            'format': 'products:1.0'
        },
        'spin_groups': {}
    }
    
    # Load release information
    codenames = load_release_codenames()
    version_info = codenames.get(version, {})
    release_codename = version_info.get('codename', '')
    release = version_info.get('release', '')
    
    spins = load_spins_config()
    for spin_id, spin_info in spins.items():
        group = {
            'name': spin_info['name'],
            'content_id': spin_info['content_id'],
            'spins': [{
                'name': spin_id,
                'release': release,
                'version': version,
                'release_title': version,
                'release_codename': release_codename,
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
