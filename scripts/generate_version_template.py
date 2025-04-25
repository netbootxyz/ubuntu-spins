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
    yaml.preserve_quotes = True
    spins_file = os.path.join('config', 'spins.yaml')
    try:
        with open(spins_file, 'r') as f:
            return yaml.load(f)['spins']
    except Exception as e:
        logger.error(f"Failed to load spins config: {e}")
        raise

def load_release_codenames():
    """Load release codenames from YAML file"""
    yaml = YAML()
    yaml.preserve_quotes = True
    codenames_file = os.path.join('config', 'release_codenames.yaml')
    try:
        with open(codenames_file, 'r') as f:
            return yaml.load(f)['release_codenames']
    except Exception as e:
        logger.error(f"Failed to load release codenames: {e}")
        raise

def create_spin_template(spin_id, info, version, release, release_codename):
    return {
        'name': spin_id,
        'release': release,
        'version': version,
        'release_title': version,
        'release_codename': release_codename,
        'image_type': 'desktop',
        'files': {
            'iso': {
                'path_template': f"{{{{ release }}}}/release/{spin_id}-{{{{ version }}}}-desktop-amd64.iso",
                'url': info['url_base'],
                'sha256': '',
                'size': 0
            }
        }
    }

def create_version_template(version):
    """Create a template for a specific Ubuntu version with configured spins"""
    # Get base version (e.g., 24.04 from 24.04.2)
    base_version = '.'.join(version.split('.')[:2])
    logger.info(f"Using base version {base_version} for codename lookup")

    template = {
        'version': version,
        'datatype': 'image-downloads',
        'format': 'products:1.0',
        'spin_groups': {}
    }
    
    try:
        spins = load_spins_config()
        codenames = load_release_codenames()
        version_info = codenames.get(base_version, {})
        release_codename = version_info.get('codename', '')
        release = version_info.get('release', '')
        
        for spin_id, spin_info in spins.items():
            group = {
                'name': spin_info['name'],
                'content_id': spin_info['content_id'],
                'spins': [create_spin_template(spin_id, spin_info, version, release, release_codename)]
            }
            template['spin_groups'][spin_id] = group
        
        return template
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Generate Ubuntu version template')
    parser.add_argument('version', help='Ubuntu version (e.g., 24.04.2)')
    parser.add_argument('--output-dir', default=os.path.join('config', 'versions'),
                       help='Output directory for version configs')
    args = parser.parse_args()

    try:
        logger.info(f"Generating template for Ubuntu {args.version}")
        
        os.makedirs(args.output_dir, exist_ok=True)
        output_file = os.path.join(args.output_dir, f'{args.version}.yaml')
        
        template = create_version_template(args.version)
        
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        yaml.default_flow_style = False
        
        # Custom representer for path_template values
        def path_template_representer(dumper, data):
            if "{{" in data and "}}" in data:  # Check if it's a template string
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
            if "\n" in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
            
        yaml.representer.add_representer(str, path_template_representer)
        
        with open(output_file, 'w') as f:
            yaml.dump(template, f)
        
        logger.info(f"Template generated successfully at {output_file}")
    except Exception as e:
        logger.error(f"Failed to generate template: {e}")
        raise

if __name__ == '__main__':
    main()
