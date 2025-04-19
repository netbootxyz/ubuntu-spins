#!/usr/bin/env python3

import yaml
from jinja2 import Environment, FileSystemLoader
import json
import os
import argparse

def load_yaml_config(config_file):
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def generate_json_for_spin_group(group_name, group_data, default_settings, output_dir):
    """Generate JSON output for a spin group."""
    data = {
        "content_id": group_data["content_id"],
        "datatype": default_settings["datatype"],
        "format": default_settings["format"],
        "products": {}
    }
    
    for spin in group_data["spins"]:
        for arch in spin["architectures"]:
            product_key = f"{group_data['content_id']}:{spin['image_type']}:{spin['version']}:{arch}"
            
            iso_info = spin["files"]["iso"]
            items = {
                "iso": {
                    "ftype": "iso",
                    "path": iso_info["path_template"]
                        .replace("{{ release }}", spin["release"])
                        .replace("{{ name }}", spin["name"])
                        .replace("{{ version }}", spin["release_title"])
                        .replace("{{ image_type }}", spin["image_type"])
                        .replace("{{ arch }}", arch),
                    "sha256": iso_info["sha256"],
                    "size": int(iso_info["size"])  # Ensure size is an integer
                }
            }
            
            data["products"][product_key] = {
                "aliases": f"{spin['version']},{spin['release']}",
                "arch": arch,
                "image_type": spin["image_type"],
                "os": spin["name"],
                "release": spin["release"],
                "release_codename": spin["release_codename"],
                "release_title": spin["release_title"],
                "version": spin["version"],
                "versions": {
                    spin["release_title"]: {
                        "items": items
                    }
                }
            }
    
    output_file = os.path.join(output_dir, f"{group_name}.json")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Generate ISO JSONs from YAML config')
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    parser.add_argument('--output-dir', required=True, help='Output directory for JSON files')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    config_data = load_yaml_config(args.config)
    
    for group_name, group_data in config_data["spin_groups"].items():
        generate_json_for_spin_group(group_name, group_data, config_data["default_settings"], args.output_dir)

if __name__ == '__main__':
    main()
