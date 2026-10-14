"""Print the pinned checksum line for a stock Proxmox system template.

Proxmox publishes its template index over plain HTTP (download.proxmox.com is
not served over TLS; the subscription host enterprise.proxmox.com is) with a
sha512sum per template and a detached signature. `pveam update` verifies the
signature against the Proxmox trusted keyring and keeps the verified copy at
/var/lib/pve-manager/apl-info/download.proxmox.com, refreshed by the daily
update timer. This script reads that copy, so the value it prints has been
signature-checked and no network code of its own is needed. The index is per
Proxmox VE major (aplinfo-pve-9.dat on PVE 9; the older aplinfo.dat stops at
Debian 11).

A bake manifest (templates/<name>/template.yml) pins the same value as
lxc_template_base_checksum, so the build host verifies the base the way a
node does: by the checksum, not the transport.

Usage: scripts/base_template_checksum.py debian-13-standard_13.6-1_amd64.tar.zst [--index FILE]
Prints: the URL and the folded `sha512:<hex>` to paste into the manifest.
Needs: python3 on a Proxmox VE node (or --index with a copy of the verified index).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

INDEX = Path("/var/lib/pve-manager/apl-info/download.proxmox.com")
IMAGES = "http://download.proxmox.com/images/"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template", help="the base file name, e.g. debian-13-standard_13.6-1_amd64.tar.zst")
    ap.add_argument("--index", type=Path, default=INDEX, help=f"a signature-verified index (default: {INDEX})")
    args = ap.parse_args()
    if not args.index.is_file():
        print(f"base_template_checksum: {args.index} is not there. Run this on a Proxmox VE node after "
              "`pveam update` (it keeps the signature-verified index there), or pass --index.", file=sys.stderr)
        return 1
    text = args.index.read_text(encoding="utf-8")
    for block in text.split("\n\n"):
        fields = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        fields = {k.strip(): v.strip() for k, v in fields.items()}
        if fields.get("Location", "").endswith("/" + args.template) or fields.get("Location") == args.template:
            print(f"lxc_template_base_url: \"{IMAGES}{fields['Location']}\"")
            # Folded: the hex alone runs past yamllint's 160-column line.
            print("lxc_template_base_checksum: >-")
            print(f"  sha512:{fields['sha512sum']}")
            return 0
    print(f"base_template_checksum: {args.template} is not in {args.index}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
