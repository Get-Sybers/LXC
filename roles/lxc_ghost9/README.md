# lxc_ghost9

Deploy the [GHOSTS](https://github.com/cmu-sei/GHOSTS) server — CERT/SEI's NPC and user-simulation framework — as **native `systemd` services in a
hardened Debian LXC**. No Docker, no OCI runtime, no SSH. The full GHOSTS v9.3.0 server stack runs as regular services:

- **PostgreSQL** (loopback `5432`) — the datastore the API creates and seeds at first start.
- **ghosts-api** (`5000`) — the .NET 10 REST/SignalR C2 server (`dotnet ghosts.api.dll`), as the unprivileged `ghosts` user.
- **nginx** (`4200`) — serves the built Angular UI; the browser-facing URLs come from a templated `assets/config.json`.
- **ghosts-n8n** (`5678`) — workflow automation, SQLite-backed, with the GHOSTS workflows imported and an owner account.
- **grafana-server** (`3000`) — dashboards over the GHOSTS database, embedded in the UI (anonymous admin).

The image is baked, not installed: `bake` runs inside a build rootfs (from [`templates/ghost9`](../../templates/ghost9/README.md) via
`playbooks/bake-template.yml`), adds the Microsoft/NodeSource/Grafana apt repositories, installs .NET 10, Node.js, PostgreSQL, nginx, Grafana
and n8n, builds the API and UI from the checksum-pinned GHOSTS source, and puts the service users, the systemd units, the nginx site and the
provisioning content into the released template. The container itself is `lxc_guest`'s: `container` and `remove` hand the placement and the
released template to it. `server` runs in the booted CT, refuses a guest without the baseline marker or the `ghost9` template marker, creates
the PostgreSQL role and database, writes the site config (connection string, UI URLs, Grafana datasource), starts all five services,
provisions n8n and verifies the stack. After deployment it is touched two ways only: its own web UI/APIs, and this role over `pct exec`.

- **Privilege:** `container`/`remove` run as root on the Proxmox node; `server` runs as root inside the CT (over
  `community.proxmox.proxmox_pct_remote`) and drops to the service users for every service command.
- **Collections:** `community.proxmox` (through `lxc_guest`) and `ansible.builtin`.
- **Idempotent:** yes. `server` reports `changed=0` on a settled guest (the DB role/db, the config, the n8n owner and workflow import are all
  guarded); `bake` is run once per release into a fresh rootfs.
- **Platforms:** Debian (trixie) CT on **Proxmox VE**. **Min ansible:** 2.19.

## Entry points

| `tasks_from` | Where it runs | What it does |
| --- | --- | --- |
| `bake` | the build rootfs (chroot) | the apt repos, .NET/Node/PostgreSQL/nginx/Grafana/n8n, the API and UI built from pinned source, the service users, the systemd units + nginx site + provisioning content, enabled for `multi-user.target`; no site config, no start |
| `container` | node (`localhost`/`local`) | `lxc_guest` ensure path with this role's placement, template URL and checksum; the CT joins the `ghost9` group |
| `server` | inside the CT | assert the markers and the baked stack, open the firewall, create the Postgres role/db, write the API env / UI config / Grafana datasource, start the services, provision n8n, verify |
| `remove` | node | `lxc_guest` `remove` with this role's placement (needs `-e lxc_guest_confirm_destroy=true`) |

## Inputs (selected — full list in `meta/argument_specs.yml`)

| Variable | Default | Description |
| --- | --- | --- |
| `lxc_ghost9_node` | `{{ lxc_node }}` | PVE node the CT lives on. |
| `lxc_ghost9_vmid` | `0` (refused) | CT id; the inventory sets it. |
| `lxc_ghost9_template_version` | `0.1.1` | This repository's release of the `ghost9` template; `server` refuses a guest baked at another. |
| `lxc_ghost9_template_checksum` | `""` (fetch refused) | The release's `sha256:`, pinned in the inventory. |
| `lxc_ghost9_rootfs_gb` / `_cores` / `_memory_mb` | `20` / `4` / `6144` | Two source builds and five services. |
| `lxc_ghost9_features` | `["nesting=1"]` | Debian 13's systemd 257 needs nesting; the CT stays unprivileged. |
| `lxc_ghost9_version` | `9.3.0` | GHOSTS release the image carries; `server` refuses a template whose marker says another. Set in `templates/ghost9/template.yml` for the bake. |
| `lxc_ghost9_source_sha256` | the `v9.3.0` source tarball's `sha256:` | GHOSTS ships no checksums file, so it is the asset's own sha256; raised with the version. |
| `lxc_ghost9_ui_port` / `_api_port` / `_grafana_port` / `_n8n_port` | `4200` / `5000` / `3000` / `5678` | The ports the firewall opens. PostgreSQL (`5432`) stays loopback-only. |
| `lxc_ghost9_firewall_allow` | UI + API + Grafana + n8n | Inbound ports the in-guest firewall opens (default-deny otherwise). |
| `lxc_ghost9_public_hostname` | `{{ lxc_ghost9_hostname }}` | Fills the UI's `assets/config.json` and the API CORS origins; set it to the CT's DNS name or address. |
| `lxc_ghost9_db_password` | `""` | **Secret, required.** The PostgreSQL password (API connection string + Grafana datasource). |
| `lxc_ghost9_n8n_owner_email` / `_password` | `admin@ghosts.local` / `""` | The n8n owner account; the password is **secret, required**. |

## Dependencies

None declared. `lxc_guest` is composed at the point of need (`container.yml`, `remove.yml`). PVE API auth is supplied by the playbook through
the `group/community.proxmox.proxmox` module-defaults group reading the documented `PROXMOX_*` environment variables.

## Usage

[`playbooks/deploy-ghost9.yml`](../../playbooks/deploy-ghost9.yml) wires the three plays together; the operator procedure is
[`doc/howto/deploy-ghost9.md`](../../doc/howto/deploy-ghost9.md).

## Behaviour and security

Everything runs as a native, sandboxed `systemd` service — no container runtime, so the hardened baseline's refusal of Docker/containerd/podman
holds. The API and n8n units run with `NoNewPrivileges`, an empty capability bounding set, `ProtectSystem=strict` (only their state/log dirs
writable), private tmp/devices, the kernel protections and a `@system-service` syscall filter (filtered syscalls soft-fail with `EPERM` so a
.NET or Node runtime probe degrades gracefully rather than being killed). The API connection string and the Grafana datasource carry the DB
password, so the tasks that write them are `no_log`, as is the n8n owner creation. The in-guest `nftables` firewall default-denies inbound and
opens only the UI, API, Grafana and n8n ports; PostgreSQL stays loopback-only. Secrets live only in the vaulted `inventory/secrets/ghost9.yml`.

The `ghost9_negative` Molecule scenario proves `server` stops at the baseline assertion on a guest that carries no marker, before any change.
