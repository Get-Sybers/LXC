# velociraptor

The [Velociraptor](https://docs.velociraptor.app/) template: Debian 13 with the official `velociraptor` release binary (verified against the
sha256 of its gzipped release asset), unpacked to `/usr/local/bin/velociraptor`, an unprivileged `velociraptor` service user with its
datastore directory, a native `systemd` unit enabled for `multi-user.target`, no SSH server, and the `lxc_guest` baseline marker. Nothing
site-specific is in it: the generated `server.config.yaml` (the self-signed CA, the GUI/frontend ports and bind addresses, the public URL),
the administrator account and the unit's first start happen on the node, in `lxc_velociraptor`'s `server` entry point.

| | |
| --- | --- |
| Release tag | `velociraptor/v<template release>` (`velociraptor/v0.1.0`; the service version is in the marker's `service=`) |
| Artifact | `debian-13-velociraptor_<version>_<arch>.tar.zst` + `.sha256`, cosign bundle, provenance attestation |
| Base | `debian-13-standard_13.6-1_amd64.tar.zst` from `download.proxmox.com` |
| Bake steps | `lxc_guest` `baseline`, then `lxc_velociraptor` `bake` |
| Consumed by | `inventory/group_vars/all/velociraptor.yml` (`lxc_velociraptor_template_checksum`), `inventory/secrets/velociraptor.yml`, `playbooks/deploy-velociraptor.yml` |

To raise the Velociraptor version: change `lxc_velociraptor_version` and `lxc_velociraptor_binary_checksum` here (the sha256 of the release's
`velociraptor-v<version>-linux-amd64.gz`, which the release has no checksums file for — compute it from the asset) and raise
`lxc_template_version` (the Version Gate requires it for every change to the image; the release tag carries it, not the Velociraptor version),
open a PR, then run the Templates workflow for `velociraptor` with *publish* on (its reviewer approves it; the run creates
`velociraptor/v<new>`), then pin the new release's URL and `sha256:` in the inventory.
