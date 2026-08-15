#!/usr/bin/env python3
"""
Script: generate_update_manifest.py
Purpose: Generates the production latest.json release manifest for EmpMonitor desktop auto-updates on Cloudflare R2.
Author: EmpMonitor DevOps & Automation Team
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# JSON Schema for latest.json release manifest validation
MANIFEST_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "EmpMonitorAutoUpdateManifest",
    "type": "object",
    "required": ["version", "release_date", "url", "sha256", "mandatory", "notes"],
    "properties": {
        "version": {
            "type": "string",
            "pattern": r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"
        },
        "release_date": {
            "type": "string",
            "format": "date-time"
        },
        "url": {
            "type": "string",
            "format": "uri"
        },
        "sha256": {
            "type": "string",
            "pattern": "^[a-fA-F0-9]{64}$"
        },
        "mandatory": {
            "type": "boolean"
        },
        "notes": {
            "type": "string"
        },
        "file_size_bytes": {
            "type": "integer",
            "minimum": 1
        },
        "channel": {
            "type": "string",
            "enum": ["stable", "beta", "nightly"]
        }
    }
}


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Computes SHA-256 hex digest of a file in streaming chunks."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest().lower()


def generate_manifest(
    binary_path: str,
    version: str,
    base_url: str,
    output_manifest: str,
    mandatory: bool = False,
    notes: Optional[str] = None,
    channel: str = "stable"
) -> Dict[str, Any]:
    """Builds and serializes the latest.json metadata manifest."""
    bin_file = Path(binary_path).resolve()
    
    if not bin_file.exists():
        raise FileNotFoundError(f"Binary target not found at: {bin_file}")
    
    # Strip leading 'v' if present for semantic version normalization
    clean_version = version.lstrip("v")
    
    # Compute cryptographic checksum and file size
    sha256_digest = compute_sha256(bin_file)
    file_size = bin_file.stat().st_size
    
    # Format ISO 8601 UTC timestamp
    release_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Construct binary download URL on Cloudflare R2 custom domain
    base_url_cleaned = base_url.rstrip("/")
    download_url = f"{base_url_cleaned}/{bin_file.name}"
    
    if not notes:
        notes = f"EmpMonitor Desktop Suite {clean_version} automated release build."
    
    manifest_data: Dict[str, Any] = {
        "version": clean_version,
        "release_date": release_timestamp,
        "url": download_url,
        "sha256": sha256_digest,
        "file_size_bytes": file_size,
        "mandatory": mandatory,
        "channel": channel,
        "notes": notes
    }
    
    # Output file handling
    out_path = Path(output_manifest).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
        
    print(f"[SUCCESS] Release manifest generated successfully at: {out_path}")
    print(f"  -> Version:       {manifest_data['version']}")
    print(f"  -> Release Date:  {manifest_data['release_date']}")
    print(f"  -> Download URL:  {manifest_data['url']}")
    print(f"  -> SHA256:        {manifest_data['sha256']}")
    print(f"  -> Size:          {manifest_data['file_size_bytes']} bytes")
    print(f"  -> Mandatory:     {manifest_data['mandatory']}")
    
    return manifest_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EmpMonitor Desktop Auto-Update Manifest Generator for Cloudflare R2"
    )
    parser.add_argument(
        "--binary-path",
        required=True,
        help="Path to the compiled installer binary (e.g. dist-electron/empmonitor-setup-0.1.3.exe)"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Semantic version string (e.g. 0.1.3 or v0.1.3)"
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Custom public domain URL for R2 bucket (e.g. https://updates.yourdomain.com)"
    )
    parser.add_argument(
        "--output-manifest",
        default="latest.json",
        help="Path to output manifest JSON file (default: latest.json)"
    )
    parser.add_argument(
        "--mandatory",
        action="store_true",
        default=False,
        help="Flag indicating whether this update is strictly required"
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Release notes or changelog summary text"
    )
    parser.add_argument(
        "--channel",
        default="stable",
        choices=["stable", "beta", "nightly"],
        help="Release channel (default: stable)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generate_manifest(
            binary_path=args.binary_path,
            version=args.version,
            base_url=args.base_url,
            output_manifest=args.output_manifest,
            mandatory=args.mandatory,
            notes=args.notes,
            channel=args.channel
        )
        return 0
    except Exception as err:
        print(f"[ERROR] Failed to generate update manifest: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
