#!/usr/bin/env python3
"""
Validate generated JSON files against the expected schema.
Ensures compatibility with netboot.xyz mini-iso-tools.
"""

import json
import sys
from pathlib import Path

REQUIRED_TOP_LEVEL = ['datatype', 'format', 'content_id', 'products']
REQUIRED_PRODUCT = ['aliases', 'arch', 'image_type', 'os', 'release',
                   'release_codename', 'release_title', 'version', 'versions']
REQUIRED_ISO = ['ftype', 'path', 'sha256', 'size']

def validate_json_file(json_path):
    """Validate a single JSON file."""
    errors = []
    warnings = []

    with open(json_path, 'r') as f:
        data = json.load(f)

    # Check top-level fields
    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            errors.append(f"Missing top-level field: {field}")

    # Validate expected format
    if data.get('format') != 'products:1.0':
        errors.append(f"Invalid format: {data.get('format')}, expected 'products:1.0'")

    if data.get('datatype') != 'image-downloads':
        errors.append(f"Invalid datatype: {data.get('datatype')}, expected 'image-downloads'")

    # Check products
    products = data.get('products', {})
    if not products:
        errors.append("No products defined")
        return errors, warnings

    print(f"  Found {len(products)} products")

    # Validate each product
    for product_id, product in products.items():
        # Check product fields
        missing = [f for f in REQUIRED_PRODUCT if f not in product]
        if missing:
            errors.append(f"Product {product_id} missing fields: {missing}")

        # Check versions
        if 'versions' not in product or not product['versions']:
            errors.append(f"Product {product_id} has no versions")
            continue

        # Check ISO entries
        for version, version_data in product['versions'].items():
            if 'items' not in version_data:
                errors.append(f"Product {product_id} version {version} missing 'items'")
                continue

            if 'iso' not in version_data['items']:
                errors.append(f"Product {product_id} version {version} missing 'iso' in items")
                continue

            iso = version_data['items']['iso']

            # Check ISO fields
            missing_iso = [f for f in REQUIRED_ISO if f not in iso]
            if missing_iso:
                errors.append(f"Product {product_id} version {version} ISO missing: {missing_iso}")

            # Check for empty values
            if iso.get('sha256') == '':
                warnings.append(f"Product {product_id} version {version} has empty SHA256")

            if iso.get('size', 0) == 0:
                warnings.append(f"Product {product_id} version {version} has zero size")

            # Validate ftype
            if iso.get('ftype') != 'iso':
                errors.append(f"Product {product_id} version {version} ftype should be 'iso', got '{iso.get('ftype')}'")

    return errors, warnings

def main():
    output_dir = Path('output')

    if not output_dir.exists():
        print(f"Error: {output_dir} does not exist")
        sys.exit(1)

    json_files = list(output_dir.glob('*.json'))
    if not json_files:
        print(f"Error: No JSON files found in {output_dir}")
        sys.exit(1)

    print(f"Validating {len(json_files)} JSON files...\n")

    all_errors = []
    all_warnings = []

    for json_file in sorted(json_files):
        print(f"📄 {json_file.name}")
        errors, warnings = validate_json_file(json_file)

        if errors:
            print(f"  ❌ {len(errors)} errors:")
            for err in errors:
                print(f"     - {err}")
            all_errors.extend(errors)
        else:
            print(f"  ✅ No errors")

        if warnings:
            print(f"  ⚠️  {len(warnings)} warnings:")
            for warn in warnings:
                print(f"     - {warn}")
            all_warnings.extend(warnings)

        print()

    # Summary
    print("=" * 60)
    print(f"Total: {len(json_files)} files")
    print(f"Errors: {len(all_errors)}")
    print(f"Warnings: {len(all_warnings)}")

    if all_errors:
        print("\n❌ Validation FAILED")
        sys.exit(1)
    elif all_warnings:
        print("\n⚠️  Validation passed with warnings")
        print("   (Empty checksums are OK for new versions)")
        sys.exit(0)
    else:
        print("\n✅ All validations PASSED")
        sys.exit(0)

if __name__ == '__main__':
    main()
