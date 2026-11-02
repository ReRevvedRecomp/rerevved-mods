#!/usr/bin/env python3
"""Verify first-party map pack manifests and payload layout under maps/."""

import sys
import tomllib
from pathlib import Path

from build_asset_packs import (
    PACKAGE_ID_RE,
    PACKAGE_VERSION_RE,
    _is_reparse_point,
    _require_string,
    _validate_version,
)

PAYLOAD = "assets/map-pack/dlc.fpk"
# The title refuses scenario file slots 0-4 and scenario IDs below 100.
MIN_SLOT = 5
MAX_SLOT = 31
MIN_SCENARIO_ID = 100
# The title names a pack's content rr_<id> and refuses names over 42 characters.
MAX_ID_LENGTH = 39
EXPECTED_ENTRIES = {
    "asset-pack.toml": "file",
    "assets": "dir",
    "assets/map-pack": "dir",
    PAYLOAD: "file",
}


def _require_int(value, field, path, minimum, maximum=None):
    if type(value) is not int or value < minimum or (maximum and value > maximum):
        bound = f"{minimum}..{maximum}" if maximum else f">= {minimum}"
        raise RuntimeError(f"{path}: {field} must be an integer {bound}")
    return value


def _load_manifest(path, pack_id):
    try:
        value = tomllib.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError(f"{path}: invalid TOML: {error}") from error
    if type(value.get("manifest_version")) is not int or value["manifest_version"] != 1:
        raise RuntimeError(f"{path}: manifest_version must be integer 1")
    pack = value.get("asset_pack")
    if not isinstance(pack, dict):
        raise RuntimeError(f"{path}: [asset_pack] table is required")
    found = _require_string(pack.get("id"), "[asset_pack].id", path, nonempty=True)
    if not PACKAGE_ID_RE.fullmatch(found) or len(found) > MAX_ID_LENGTH:
        raise RuntimeError(f"{path}: [asset_pack].id is not a valid package ID")
    if found != pack_id:
        raise RuntimeError(
            f"{path}: [asset_pack].id {found!r} does not match folder {pack_id!r}"
        )
    for field in ("name", "author", "description"):
        _require_string(pack.get(field), f"[asset_pack].{field}", path, nonempty=True)
    _validate_version(
        pack.get("version"),
        "[asset_pack].version",
        path,
        PACKAGE_VERSION_RE,
        "major.minor",
    )

    slot = None
    scenario_ids = []
    if "map_pack" in value:
        table = value["map_pack"]
        if not isinstance(table, dict):
            raise RuntimeError(f"{path}: [map_pack] must be a table")
        slot = _require_int(
            table.get("slot"), "[map_pack].slot", path, MIN_SLOT, MAX_SLOT
        )
        scenarios = table.get("scenarios", [])
        if not isinstance(scenarios, list):
            raise RuntimeError(f"{path}: [map_pack].scenarios must be a list")
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                raise RuntimeError(f"{path}: each scenario must be a table")
            scenario_ids.append(
                _require_int(
                    scenario.get("id"),
                    "scenario id",
                    path,
                    MIN_SCENARIO_ID,
                )
            )
            _require_string(scenario.get("name"), "scenario name", path, nonempty=True)
    return slot, scenario_ids


def _verify_layout(pack_dir):
    if _is_reparse_point(pack_dir):
        raise RuntimeError(f"{pack_dir}: map pack directory is a reparse point")
    found = {}
    for entry in sorted(pack_dir.rglob("*")):
        if _is_reparse_point(entry):
            raise RuntimeError(f"{entry}: reparse point in map pack")
        relative = entry.relative_to(pack_dir).as_posix()
        if entry.is_file():
            found[relative] = "file"
        elif entry.is_dir():
            found[relative] = "dir"
        else:
            raise RuntimeError(f"{entry}: map pack entry must be a regular file")
    if found != EXPECTED_ENTRIES:
        raise RuntimeError(
            f"{pack_dir}: map pack must hold exactly asset-pack.toml and {PAYLOAD}"
        )
    if not (pack_dir / PAYLOAD).stat().st_size:
        raise RuntimeError(f"{pack_dir / PAYLOAD}: map pack payload is empty")


def verify_map_packs(root):
    """Return the sorted IDs of the map packs under root/maps."""
    source_root = root / "maps"
    if not source_root.exists():
        return []
    slots = {}
    scenarios = {}
    packs = []
    for entry in sorted(source_root.iterdir()):
        if not entry.is_dir():
            raise RuntimeError(f"{entry}: maps/ may hold only map pack directories")
        _verify_layout(entry)
        manifest = entry / "asset-pack.toml"
        slot, scenario_ids = _load_manifest(manifest, entry.name)
        if slot is not None:
            if slot in slots:
                raise RuntimeError(
                    f"{manifest}: map pack slot {slot} is also used by {slots[slot]}"
                )
            slots[slot] = entry.name
        for scenario_id in scenario_ids:
            if scenario_id in scenarios:
                raise RuntimeError(
                    f"{manifest}: scenario id {scenario_id} is also used by "
                    f"{scenarios[scenario_id]}"
                )
            scenarios[scenario_id] = entry.name
        packs.append(entry.name)
    return packs


def main():
    root = Path(__file__).resolve().parent.parent
    packs = verify_map_packs(root)
    suffix = f": {', '.join(packs)}" if packs else "."
    print(f"Verified {len(packs)} map pack(s){suffix}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
