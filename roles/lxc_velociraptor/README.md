# lxc_velociraptor

Deploy [Velociraptor](https://docs.velociraptor.app/) — the DFIR endpoint-visibility and digital-forensics collection platform — as a
**native `systemd` service in a hardened Debian LXC**. No Docker, no OCI runtime, no SSH: the single `velociraptor` binary runs as an
unprivileged `velociraptor` user from `/usr/local/bin/velociraptor`, serving its analyst GUI on `8889` and the client frontend on `8000`,
with its datastore, hunts and logs under `/var/lib/velociraptor`. The gRPC API (`8001`) and the monitoring listener (`8003`) stay on
loopback; the in-guest firewall opens only the GUI and the frontend.

The image is baked, not installed: `bake` runs inside a build rootfs (from [`templates/velociraptor`](../../templates/velociraptor/README.md)
via `playbooks/bake-template.yml`), downloads the official release binary, refuses it unless it carries the pinned checksum, unpacks it and
puts the binary, the service user and the unit into the released template. The container itself is not this role's business: `container` and
`remove` hand the Velociraptor placement and the released template to [`lxc_guest`](../lxc_guest/README.md), which owns the lifecycle and the
hardened premise. `server` runs in the booted CT, refuses a guest without the baseline marker or without the `velociraptor` template marker at
this role's version, and does only the site-specific rest: the in-guest firewall drop-in, the generated `server.config.yaml` (self-signed CA,
the site ports and URLs), the administrator, the first start, the health check. After deployment the server is touched two ways only: its GUI
and client API, and this role over `pct exec`.

- **Privilege:** `container`/`remove` run as root on the Proxmox node; `server` runs as root inside the CT (over
  `community.proxmox.proxmox_pct_remote`) and drops to the service user (`runuser`) for every `velociraptor` command.
- **Collections:** `community.proxmox` (through `lxc_guest`) and `ansible.builtin`.
- **Idempotent:** yes. `server` reports `changed=0` on a settled guest (the configuration is generated once and kept so the self-signed CA
  stays stable; the administrator is created only when absent); `bake` is run once per release into a fresh rootfs.
- **Platforms:** Debian (bookworm, trixie) CT on **Proxmox VE**. **Min ansible:** 2.19.

## Entry points

| `tasks_from` | Where it runs | What it does |
| --- | --- | --- |
| `bake` | the build rootfs (chroot) | the service user and directories, the release binary verified by checksum and unpacked to `/usr/local/bin`, the unit + its `multi-user.target.wants` link; no configuration, no start |
| `container` | node (`localhost`/`local`) | `lxc_guest` ensure path with this role's placement, template URL and checksum; the CT joins the `velociraptor` group |
| `server` | inside the CT | assert the baseline and template markers and the baked binary, open the service ports in the in-guest firewall, generate `server.config.yaml` when absent, create the administrator when absent, enable + start the unit, verify the GUI |
| `remove` | node | `lxc_guest` `remove` with this role's placement (needs `-e lxc_guest_confirm_destroy=true`) |

## Inputs (selected — full list in `meta/argument_specs.yml`)

| Variable | Default | Description |
| --- | --- | --- |
| `lxc_velociraptor_node` | `{{ lxc_node }}` | PVE node the CT lives on. |
| `lxc_velociraptor_vmid` | `0` (refused) | CT id; the inventory sets it. |
| `lxc_velociraptor_template_version` | `0.1.0` | This repository's release of the `velociraptor` template (the manifest's `lxc_template_version`): names the artifact and the tag; `server` refuses a guest baked at another. |
| `lxc_velociraptor_template` | `local:vztmpl/debian-13-velociraptor_<template release>_<arch>.tar.zst` | The released template. |
| `lxc_velociraptor_template_checksum` | `""` (fetch refused) | The release's `sha256:`, pinned in the inventory. |
| `lxc_velociraptor_rootfs_gb` / `_cores` / `_memory_mb` | `16` / `2` / `2048` | Velociraptor keeps every client's files and the hunts in its datastore. |
| `lxc_velociraptor_net0` | DHCP on `{{ lxc_bridge }}` | Full Proxmox net0; set a static `ip=/gw=` for a fixed address. |
| `lxc_velociraptor_features` | `["nesting=1"]` | Debian 13's systemd 257 needs nesting; the CT stays unprivileged. |
| `lxc_velociraptor_version` | `0.77.3` | Velociraptor release the image carries; `server` refuses a template whose marker says another. Set in `templates/velociraptor/template.yml` for the bake. |
| `lxc_velociraptor_binary_checksum` | the `0.77.3` amd64 `.gz`'s `sha256:` | The release has no checksums file, so it is the asset's own sha256; raised with the version. |
| `lxc_velociraptor_gui_port` / `_frontend_port` | `8889` / `8000` | The GUI and the client frontend; the only ports the in-guest firewall opens. |
| `lxc_velociraptor_api_port` / `_monitoring_port` | `8001` / `8003` | The gRPC API and monitoring; loopback-only, not opened. |
| `lxc_velociraptor_firewall_allow` | GUI + frontend | Inbound ports the in-guest firewall opens (default-deny otherwise). |
| `lxc_velociraptor_public_hostname` | `{{ lxc_velociraptor_hostname }}` | Fills the GUI `public_url` and the clients' `server_urls`; set it to the CT's DNS name or address. |
| `lxc_velociraptor_admin_user` | `admin` | The GUI administrator created when absent. |
| `lxc_velociraptor_admin_password` | `""` | **Secret, required.** The administrator's initial password. |

## Dependencies

None declared. `lxc_guest` is composed at the point of need (`container.yml`, `remove.yml`). PVE API auth is supplied by the playbook through
the `group/community.proxmox.proxmox` module-defaults group reading the documented `PROXMOX_*` environment variables.

## Usage

[`playbooks/deploy-velociraptor.yml`](../../playbooks/deploy-velociraptor.yml) wires the three plays together; the operator procedure is
[`doc/howto/deploy-velociraptor.md`](../../doc/howto/deploy-velociraptor.md).

## Behaviour and security

`server.config.yaml` is written `0640` root-owned and readable by the service user; it carries the self-signed CA's private key and the
server keys, so the task that generates it and the one that writes it are `no_log`, as is the administrator's creation. The configuration is
generated **once** (when the file is absent) and kept, so the self-signed CA that every enrolled client pins stays stable across re-runs; the
ports, bind addresses and the public URL come from a JSON merge applied at generation time. The administrator is created once, when
`velociraptor user show` reports the login absent, and its password is managed in the GUI afterwards — the role never rewrites it (an
unconditional `user add` would reset it). The unit runs with `NoNewPrivileges`, an empty capability bounding set, `ProtectSystem=strict`
with only the datastore writable, private tmp and devices, the kernel protections and a `@system-service` syscall filter (filtered syscalls return `EPERM` rather than killing the process, so Velociraptor's optional `bpf` probe degrades gracefully).

The `velociraptor_negative` Molecule scenario proves `server` stops at the baseline assertion on a guest that carries no marker, before any
change.
