#!/usr/bin/env python3
"""Verify asset pack manifests, payload safety, and optional ZIP packages."""

import argparse
import sys
import zipfile
from pathlib import Path

from build_asset_packs import (
    discover_asset_packs,
    load_asset_pack_manifest,
    verify_asset_pack_archive,
)


def verify_asset_packs(root, check_packages=False):
    source_root = root / "asset-packs"
    packs = discover_asset_packs(source_root)
    if check_packages:
        for package_id in packs:
            archive = root / "pkg" / f"{package_id}.zip"
            if not archive.is_file():
                raise RuntimeError(f"missing asset pack package: {archive}")
            source = load_asset_pack_manifest(
                source_root / package_id / "asset-pack.toml", package_id
            )
            verify_asset_pack_archive(archive, package_id, source)
    return packs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package",
        action="store_true",
        help="also verify generated pkg/<id>.zip archives",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    packs = verify_asset_packs(root, args.package)
    suffix = f": {', '.join(packs)}" if packs else "."
    print(f"Verified {len(packs)} asset pack(s){suffix}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, UnicodeError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
