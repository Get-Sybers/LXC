# op-connect

The 1Password Connect template: Debian 13 with the `connect-api` and `connect-sync` binaries extracted from their pinned official images,
installed as native `systemd` units enabled for `multi-user.target`, an unprivileged `opuser` service user, no SSH server, and the
`lxc_guest` baseline marker. Nothing site-specific is in it: the `1password-credentials.json` and the units' first start happen on the node,
in `lxc_onepassword_connect`'s `server` entry point.

| | |
| --- | --- |
| Release tag | `op-connect/v<connect version>` (`op-connect/v1.8.3`) |
| Artifact | `debian-13-op-connect_<version>_<arch>.tar.zst` + `.sha256`, cosign bundle, provenance attestation |
| Base | `debian-13-standard_13.1-2_amd64.tar.zst` from `download.proxmox.com` |
| Bake steps | `lxc_guest` `baseline`, then `lxc_onepassword_connect` `bake` |
| Consumed by | `inventory/group_vars/all/onepassword.yml` (`lxc_onepassword_connect_template_url` / `_checksum`), `playbooks/deploy-onepassword-connect.yml` |

To raise the Connect version: change `lxc_onepassword_connect_version` here, open a PR (the workflow bakes it), tag `op-connect/v<new>`,
then pin the new release's URL and `sha256:` in the inventory.
