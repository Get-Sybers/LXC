"""Print the pinned checksum line for a stock Proxmox system template.

Proxmox publishes its template index at download.proxmox.com/images/aplinfo.dat
with a sha512sum per template; `pveam` verifies downloads against it. A bake
manifest (templates/<name>/template.yml) pins the same value as
lxc_template_base_checksum so the build host verifies the base the same way a
node would.

Usage: scripts/base_template_checksum.py debian-13-standard_13.1-2_amd64.tar.zst
Prints: the URL and `sha512:<hex>` to paste into the manifest.
Needs: python3 only (network access to download.proxmox.com).
"""
from __future__ import annotations

import sys
import urllib.request

INDEX = "https://download.proxmox.com/images/aplinfo.dat"
IMAGES = "https://download.proxmox.com/images/"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    wanted = sys.argv[1]
    with urllib.request.urlopen(INDEX, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    for block in text.split("\n\n"):
        fields = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        fields = {k.strip(): v.strip() for k, v in fields.items()}
        if fields.get("Location", "").endswith("/" + wanted) or fields.get("Location") == wanted:
            print(f"lxc_template_base_url: \"{IMAGES}{fields['Location']}\"")
            print(f"lxc_template_base_checksum: \"sha512:{fields['sha512sum']}\"")
            return 0
    print(f"base_template_checksum: {wanted} is not in {INDEX}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
