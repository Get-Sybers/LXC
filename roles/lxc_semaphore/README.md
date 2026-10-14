# lxc_semaphore

Deploy [Semaphore UI](https://semaphoreui.com/) — the web UI and API for Ansible, Terraform and OpenTofu — as a **native `systemd`
service in a hardened Debian LXC**, from the official Debian package on SQLite. No Docker, no OCI runtime: the `semaphore` binary runs as an
unprivileged `semaphore` user on port 3000, with its database and the repositories it clones under `/var/lib/semaphore`, and the tools its
tasks shell out to (`git`, `openssh-client`, `sshpass`, `rsync`, `ansible-core`) beside it.

The image is baked, not installed: `bake` runs inside a build rootfs (from [`templates/semaphore`](../../templates/semaphore/README.md) via
`playbooks/bake-template.yml`), downloads the `.deb`, refuses it unless it carries the checksum the release publishes, and puts the package,
the tools, the service user and the unit into the released template. The container itself is not this role's business: `container` and
`remove` hand the Semaphore placement and the released template to [`lxc_guest`](../lxc_guest/README.md), which owns the lifecycle and the
hardened premise. `server` runs in the booted CT, refuses a guest without the baseline marker or without the `semaphore` template marker at
this role's version, and does only the site-specific rest: `config.json`, the database migrations, the administrator, the first start, the
health check. After deployment the server is touched two ways only: its web UI and API, and this role over `pct exec`.

- **Privilege:** `container`/`remove` run as root on the Proxmox node; `server` runs as root inside the CT (over
  `community.proxmox.proxmox_pct_remote`) and drops to the service user (`runuser`) for every `semaphore` command.
- **Collections:** `community.proxmox` (through `lxc_guest`) and `ansible.builtin`.
- **Idempotent:** yes. `server` reports `changed=0` on a settled guest (the migrations report a change only when one ran, the
  administrator only when created); `bake` is run once per release into a fresh rootfs.
- **Platforms:** Debian (bookworm, trixie) CT on **Proxmox VE**. **Min ansible:** 2.19.

## Entry points

| `tasks_from` | Where it runs | What it does |
| --- | --- | --- |
| `bake` | the build rootfs (chroot) | the tools, the service user and directories, the `.deb` verified by checksum and installed, the unit + its `multi-user.target.wants` link; no configuration, no start |
| `container` | node (`localhost`/`local`) | `lxc_guest` ensure path with this role's placement, template URL and checksum; the CT joins the `semaphore` group |
| `server` | inside the CT | assert the baseline and template markers and the baked binary, write `config.json`, `semaphore migrate`, create the administrator when absent, enable + start the unit, verify `/api/ping` |
| `remove` | node | `lxc_guest` `remove` with this role's placement (needs `-e lxc_guest_confirm_destroy=true`) |

## Inputs (selected — full list in `meta/argument_specs.yml`)

| Variable | Default | Description |
| --- | --- | --- |
| `lxc_semaphore_node` | `{{ lxc_node }}` | PVE node the CT lives on. |
| `lxc_semaphore_vmid` | `0` (refused) | CT id; the inventory sets it. |
| `lxc_semaphore_template_version` | `1.0.0` | This repository's release of the `semaphore` template (the manifest's `lxc_template_version`): names the artifact and the tag; `server` refuses a guest baked at another. |
| `lxc_semaphore_template` | `local:vztmpl/debian-13-semaphore_<template release>_<arch>.tar.zst` | The released template. |
| `lxc_semaphore_template_checksum` | `""` (fetch refused) | The release's `sha256:`, pinned in the inventory. |
| `lxc_semaphore_storage` | `{{ lxc_storage }}` | CT rootfs storage. |
| `lxc_semaphore_rootfs_gb` / `_cores` / `_memory_mb` | `8` / `2` / `1024` | Semaphore clones every repository it runs and keeps task logs in its database. |
| `lxc_semaphore_net0` | DHCP on `{{ lxc_bridge }}` | Full Proxmox net0; set a static `ip=/gw=` for a fixed address. |
| `lxc_semaphore_features` | `["nesting=1"]` | Debian 13's systemd 257 needs nesting; the CT stays unprivileged. |
| `lxc_semaphore_version` | `2.19.16` | Semaphore release the image carries (names the package); `server` refuses a template whose marker says another. Set in `templates/semaphore/template.yml` for the bake. |
| `lxc_semaphore_package_checksum` | the `2.19.16` amd64 `.deb`'s `sha256:` | From the release's `semaphore_<version>_checksums.txt`; raised with the version. |
| `lxc_semaphore_bake_packages` | `ca-certificates, git, openssh-client, sshpass, rsync, ansible-core` | What the image carries beside the package. |
| `lxc_semaphore_port` | `3000` | The port the UI and API listen on. |
| `lxc_semaphore_web_host` | `""` | The external URL when the UI sits behind a reverse proxy. |
| `lxc_semaphore_extra_config` | `{}` | Further `config.json` keys, deep-merged over the ones the role writes. |
| `lxc_semaphore_admin_login` / `_name` / `_email` | `admin` / `Semaphore Admin` / `admin@localhost` | The administrator created when absent. |
| `lxc_semaphore_admin_password` | `""` | **Secret, required.** The administrator's initial password. |
| `lxc_semaphore_cookie_hash` / `_cookie_encryption` / `_access_key_encryption` | `""` | **Secret, required.** Three independent base64 32-byte keys; the last one encrypts every stored access key. |

## Dependencies

None declared. `lxc_guest` is composed at the point of need (`container.yml`, `remove.yml`). PVE API auth is supplied by the playbook through
the `group/community.proxmox.proxmox` module-defaults group reading the documented `PROXMOX_*` environment variables.

## Usage

[`playbooks/deploy-semaphore.yml`](../../playbooks/deploy-semaphore.yml) wires the three plays together; the operator procedure is
[`doc/howto/deploy-semaphore.md`](../../doc/howto/deploy-semaphore.md).

## Behaviour and security

`config.json` is written `0640` root-owned and readable by the service user; it carries the three keys, so the task that assembles it and the
one that writes it are `no_log`, as is the administrator's creation. The administrator is created once, when the login is absent from
`semaphore user list`, and its password is managed in the UI afterwards — the role never rewrites it. The unit runs with
`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full` and `ProtectHome`; the service user's home (`/var/lib/semaphore`) holds the
database, the working tree and whatever `ansible-galaxy` installs for a task.

The `semaphore_negative` Molecule scenario proves `server` stops at the baseline assertion on a guest that carries no marker, before any
change.
