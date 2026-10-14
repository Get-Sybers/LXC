"""Print the pinned checksum line for a stock Proxmox system template.

Proxmox publishes its template index at download.proxmox.com/images/ with a
sha512sum per template; `pveam` verifies downloads against it. The index is
per Proxmox VE major: aplinfo-pve-9.dat is the one `pveam` reads on PVE 9
(the older aplinfo.dat stops at Debian 11 and never lists a Debian 13
template). A bake manifest (templates/<name>/template.yml) pins the same
value as lxc_template_base_checksum so the build host verifies the base the
same way a node would.

Usage: scripts/base_template_checksum.py debian-13-standard_13.6-1_amd64.tar.zst
Prints: the URL and the folded `sha512:<hex>` to paste into the manifest.
Needs: python3 only (network access to download.proxmox.com).
"""
from __future__ import annotations

import sys
import urllib.request

INDEX = "https://download.proxmox.com/images/aplinfo-pve-9.dat"
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
            # Folded: the hex alone runs past yamllint's 160-column line.
            print("lxc_template_base_checksum: >-")
            print(f"  sha512:{fields['sha512sum']}")
            return 0
    print(f"base_template_checksum: {wanted} is not in {INDEX}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
