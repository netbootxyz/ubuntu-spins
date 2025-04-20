#!/usr/bin/env python3

import yaml
import json
import os
import argparse
import glob
from collections import defaultdict

def load_yaml_config(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
        if "default_settings" not in config:
            config["default_settings"] = {
                "datatype": "image-downloads",
                "format": "products:1.0"
            }
        return config

def load_release_codenames():
    """Load release codenames mapping"""
    with open('config/release_codenames.yaml', 'r') as f:
        return yaml.safe_load(f)['release_codenames']

def get_release_info(version):
    """Get release and codename for a version"""
    codenames = load_release_codenames()
    base_version = '.'.join(version.split('.')[:2])  # Convert 24.04.2 to 24.04
    version_info = codenames.get(base_version, {})
    return {
        'release': version_info.get('release', ''),
        'release_codename': version_info.get('codename', '')
    }

def aggregate_versions(versions_dir):
    """Load and aggregate all version YAMLs from the directory."""
    aggregated_spins = defaultdict(lambda: {
        "products": {},
        "default_settings": {
            "datatype": "image-downloads",
            "format": "products:1.0"
        }
    })

    yaml_files = glob.glob(os.path.join(versions_dir, "*.yaml"))
    
    for yaml_file in sorted(yaml_files):
        config = load_yaml_config(yaml_file)
        
        for group_name, group_data in config["spin_groups"].items():
            if "content_id" not in aggregated_spins[group_name]:
                aggregated_spins[group_name]["content_id"] = group_data.get(
                    "content_id", f"org.ubuntu.{group_name}:{group_name}")
            
            for spin in group_data["spins"]:
                # Skip spins without valid SHA256 and size
                if not spin.get("files", {}).get("iso", {}).get("sha256") or \
                   not spin.get("files", {}).get("iso", {}).get("size", 0) > 0:
                    continue

                release_info = get_release_info(spin.get("version", ""))
                
                spin_data = {
                    "architectures": spin.get("architectures", ["amd64"]),
                    "image_type": spin.get("image_type", "desktop"),
                    "version": spin.get("version", spin.get("release_title", "")),
                    "release": release_info["release"],
                    "release_codename": release_info["release_codename"],
                    "release_title": spin.get("release_title", spin.get("version", ""))
                }
                
                for arch in spin_data["architectures"]:
                    content_id = aggregated_spins[group_name]["content_id"]
                    product_key = f"{content_id}:{spin_data['image_type']}:{spin_data['version']}:{arch}"
                    
                    try:
                        iso_info = spin["files"]["iso"]
                        path = iso_info["path_template"] \
                            .replace("{{ release }}", spin_data["release"]) \
                            .replace("{{ name }}", spin["name"]) \
                            .replace("{{ version }}", spin_data["version"]) \
                            .replace("{{ image_type }}", spin_data["image_type"]) \
                            .replace("{{ arch }}", arch)
                        
                        if product_key not in aggregated_spins[group_name]["products"]:
                            # Create aliases including release name for main versions
                            aliases = [spin_data["version"]]
                            if release_info["release"]:
                                aliases.append(release_info["release"])
                            
                            aggregated_spins[group_name]["products"][product_key] = {
                                "aliases": ",".join(aliases),
                                "arch": arch,
                                "image_type": spin_data["image_type"],
                                "os": spin["name"],
                                "release": release_info["release"],
                                "release_codename": release_info["release_codename"],
                                "release_title": spin_data["release_title"],
                                "version": spin_data["version"],
                                "versions": {}
                            }
                        
                        # Add version information
                        aggregated_spins[group_name]["products"][product_key]["versions"][spin_data["version"]] = {
                            "items": {
                                "iso": {
                                    "ftype": "iso",
                                    "path": path,
                                    "sha256": iso_info.get("sha256", ""),
                                    "size": int(iso_info.get("size", 0))
                                }
                            }
                        }
                        
                    except KeyError as e:
                        print(f"Warning: Missing required field {e} in spin {spin.get('name', 'unknown')}")
                        continue
    
    return dict(aggregated_spins)

def main():
    parser = argparse.ArgumentParser(description='Generate consolidated ISO JSONs from version YAMLs')
    parser.add_argument('--versions-dir', default='config/versions',
                       help='Directory containing version YAML files')
    parser.add_argument('--output-dir', required=True,
                       help='Output directory for JSON files')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.versions_dir):
        raise FileNotFoundError(f"Versions directory not found: {args.versions_dir}")
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    aggregated_data = aggregate_versions(args.versions_dir)
    
    for group_name, group_data in aggregated_data.items():
        if group_data["products"]:
            output_file = os.path.join(args.output_dir, f"{group_name}.json")
            with open(output_file, 'w') as f:
                json.dump(group_data, f, indent=2)
        else:
            print(f"Warning: No valid products found for group {group_name}")

if __name__ == '__main__':
    main()
