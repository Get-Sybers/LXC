# ghost9

The [GHOSTS](https://github.com/cmu-sei/GHOSTS) server template: Debian 13 with the full GHOSTS v9.3.0 server stack built from the
checksum-pinned source and installed as **native `systemd` services** — PostgreSQL, the .NET 10 API, the Angular UI behind nginx, n8n and
Grafana — plus the service users, the systemd units, the nginx site, the GHOSTS n8n workflows, the Grafana dashboards, no SSH server, and the
`lxc_guest` baseline marker. No Docker. Nothing site-specific is in it: the PostgreSQL role/database, the connection string, the UI's runtime
URLs, the Grafana datasource, the n8n owner account and the first start happen on the node, in `lxc_ghost9`'s `server` entry point.

| | |
| --- | --- |
| Release tag | `ghost9/v<template release>` (`ghost9/v0.1.0`; the GHOSTS version is in the marker's `service=`) |
| Artifact | `debian-13-ghost9_<version>_<arch>.tar.zst` + `.sha256`, cosign bundle, provenance attestation |
| Base | `debian-13-standard_13.6-1_amd64.tar.zst` from `download.proxmox.com` |
| Bake steps | `lxc_guest` `baseline`, then `lxc_ghost9` `bake` |
| Consumed by | `inventory/group_vars/all/ghost9.yml` (`lxc_ghost9_template_checksum`), `inventory/secrets/ghost9.yml`, `playbooks/deploy-ghost9.yml` |

To raise the GHOSTS version: change `lxc_ghost9_version` and `lxc_ghost9_source_sha256` here (the sha256 of the source tarball of the new tag,
`https://codeload.github.com/cmu-sei/GHOSTS/tar.gz/refs/tags/v<new>`) and raise `lxc_template_version` (the Version Gate requires it for every
change to the image), open a PR, then run the Templates workflow for `ghost9` with *publish* on (its reviewer approves it; the run creates
`ghost9/v<new>`), then pin the new release's URL and `sha256:` in the inventory.
