"""Build an AMD vendor catalog from the existing NVIDIA catalog.

The schema-level vendor filter (commit 4408717) only added two stub AMD
wheel items containing torch + torchaudio. The real wheels list needs the
same ~30 packages per runtime as the NVIDIA side, with only the torch and
torchaudio URLs swapped for ROCm nightlies.

This script reads catalog.json, finds the existing NVIDIA env:yue2 and
env:sheetsage entries, and produces two new wheels:rocm-* entries with
the same non-torch wheels but ROCm URLs for the two big wheels.

Run from the repo root:

    python tools/build_rocm_catalog.py \\
        --vendor=amd \\
        --torch-url <URL> \\
        --torchaudio-url <URL> \\
        [--out setup/catalog.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def build_amd_wheels(env_item: dict, torch_url: str, torchaudio_url: str,
                     torch_size: int, torchaudio_size: int,
                     torch_sha256: str, torchaudio_sha256: str) -> list[dict]:
    """Copy every wheel of ``env_item`` except torch + torchaudio; append the
    ROCm versions at the end."""
    kept = []
    for w in env_item["wheels"]:
        if w["name"] in ("torch", "torchaudio"):
            continue
        kept.append(dict(w))
    kept.append({
        "name": "torch",
        "url": torch_url,
        "size": torch_size,
        "sha256": torch_sha256,
    })
    kept.append({
        "name": "torchaudio",
        "url": torchaudio_url,
        "size": torchaudio_size,
        "sha256": torchaudio_sha256,
    })
    return kept


def main() -> int:
    doc = __doc__.splitlines() if __doc__ else []
    p = argparse.ArgumentParser(description=doc[0] if doc else None)
    p.add_argument("--catalog", type=Path, default=REPO / "setup" / "catalog.json")
    p.add_argument("--out", type=Path, default=None,
                   help="Output path (defaults to overwriting the input).")
    p.add_argument("--torch-url", required=True,
                   help="AMD ROCm torch wheel URL, e.g. "
                        "'https://rocm.nightlies.amd.com/v2/gfx120X-all/torch-...whl'")
    p.add_argument("--torchaudio-url", required=True)
    p.add_argument("--torch-size", type=int, required=True,
                   help="torch wheel size in bytes (read from the AMD index).")
    p.add_argument("--torchaudio-size", type=int, required=True)
    p.add_argument("--torch-sha256", default="")
    p.add_argument("--torchaudio-sha256", default="")
    p.add_argument("--yue2-id", default="env:yue2",
                   help="Source item id for the yue2 runtime wheels (default env:yue2).")
    p.add_argument("--sheetsage-id", default="env:sheetsage")
    p.add_argument("--rocm-yue2-id", default="wheels:rocm-yue2")
    p.add_argument("--rocm-sheetsage-id", default="wheels:rocm-sheetsage")
    args = p.parse_args()

    data = json.loads(args.catalog.read_text(encoding="utf-8"))

    sources = {args.yue2_id: args.rocm_yue2_id,
               args.sheetsage_id: args.rocm_sheetsage_id}
    seen = set()
    for item in data["items"]:
        if item["id"] in sources:
            seen.add(item["id"])
    missing = set(sources.keys()) - seen
    if missing:
        print(f"FAIL: source items not found in catalog: {sorted(missing)}", file=sys.stderr)
        return 2

    # Find the matching rocm-yue2 / rocm-sheetsage placeholder entries
    rocm_targets = {args.rocm_yue2_id, args.rocm_sheetsage_id}
    for item in data["items"]:
        if item["id"] not in rocm_targets:
            continue
        src_id = args.yue2_id if item["id"] == args.rocm_yue2_id else args.sheetsage_id
        src = next(i for i in data["items"] if i["id"] == src_id)
        item["wheels"] = build_amd_wheels(
            src, args.torch_url, args.torchaudio_url,
            args.torch_size, args.torchaudio_size,
            args.torch_sha256, args.torchaudio_sha256)
        item["size"] = sum(w["size"] for w in item["wheels"])

    out = args.out or args.catalog
    out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")

    print(f"Wrote {out}")
    for item in data["items"]:
        if item["id"] in rocm_targets:
            print(f"  {item['id']}: {len(item['wheels'])} wheels, "
                  f"{item['size']/1e9:.2f} GB total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())