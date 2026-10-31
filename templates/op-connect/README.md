# op-connect

The 1Password Connect template: Debian 13 with the `connect-api` and `connect-sync` binaries extracted from their pinned official images,
installed as native `systemd` units enabled for `multi-user.target`, an unprivileged `opuser` service user, no SSH server, and the
`lxc_guest` baseline marker. Nothing site-specific is in it: the `1password-credentials.json` and the units' first start happen on the node,
in `lxc_onepassword_connect`'s `server` entry point.

| | |
| --- | --- |
| Release tag | `op-connect/v<template release>` (`op-connect/v0.1.3`; the service version is in the marker's `service=`) |
| Artifact | `debian-13-op-connect_<version>_<arch>.tar.zst` + `.sha256`, cosign bundle, provenance attestation |
| Base | `debian-13-standard_13.6-1_amd64.tar.zst` from `download.proxmox.com` |
| Bake steps | `lxc_guest` `baseline`, then `lxc_onepassword_connect` `bake` |
| Consumed by | `lxc_onepassword_connect_template_image` (default `ghcr.io/get-sybers/lxc/op-connect:v<template release>`), `playbooks/deploy-onepassword-connect.yml` |

To raise the Connect version: change `lxc_onepassword_connect_version` and raise `lxc_template_version` here (the Version Gate
requires it for every change to the image), open a PR, then run the Templates workflow for `op-connect` with *publish* on (its
reviewer approves it; the run creates `op-connect/v<new>`),
then raise `lxc_onepassword_connect_template_version` in the role (the deploy pulls `ghcr.io/<owner>/lxc/op-connect:v<new>` into `local:vztmpl/op-connect_<new>.tar`) and recreate the CT.
