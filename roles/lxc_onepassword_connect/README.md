# lxc_onepassword_connect

Deploy a self-hosted [1Password Connect](https://developer.1password.com/docs/connect/) server as **native `systemd` services in a hardened
Debian LXC** — no Docker, no OCI runtime. The official `connect-api`/`connect-sync` images are single Go binaries; this role extracts those
binaries straight from the pinned images (via the Docker registry HTTP API — nothing is installed and nothing runs as a container) and runs each
as an `opuser` service, exactly as the image would (`ENTRYPOINT`, `SSL_CERT_FILE`, `~/.op` data dir, port 8080).

The image is baked, not installed: `bake` runs inside a build rootfs (from [`templates/op-connect`](../../templates/op-connect/README.md)
via `playbooks/bake-template.yml`) and puts the binaries, the units and the service user into the released template. The container itself
is not this role's business: `container` and `remove` hand the Connect placement and the released template to
[`lxc_guest`](../lxc_guest/README.md), which owns the lifecycle and the hardened premise. `server` runs in the booted CT, refuses a guest
without the baseline marker or without the `op-connect` template marker at this role's version, and does only the site-specific rest:
credentials, first start, health check. After deployment the server is touched two ways only: its HTTP API (the `lxc_onepassword_item`
role) and this role over `pct exec`.

- **Privilege:** `container`/`remove` run as root on the Proxmox node; `server` runs as root inside the CT (over
  `community.proxmox.proxmox_pct_remote`).
- **Collections:** `community.proxmox` (through `lxc_guest`) and `ansible.builtin`.
- **Idempotent:** yes. `server` reports `changed=0` on a settled guest; `bake` is run once per release into a fresh rootfs.
- **Platforms:** Debian (bookworm, trixie) CT on **Proxmox VE**. **Min ansible:** 2.19.

## Entry points

| `tasks_from` | Where it runs | What it does |
| --- | --- | --- |
| `bake` | the build rootfs (chroot) | ca-certs, service user, extract the binaries from the pinned images, units + `multi-user.target.wants` links; no credentials, no start |
| `container` | node (`localhost`/`local`) | `lxc_guest` ensure path with this role's placement, template URL and checksum; the CT joins the `onepassword_connect` group |
| `server` | inside the CT | assert the baseline and template markers and the baked binaries, credentials, enable + start the units, verify |
| `remove` | node | `lxc_guest` `remove` with this role's placement (needs `-e lxc_guest_confirm_destroy=true`) |

## Inputs (selected — full list in `meta/argument_specs.yml`)

| Variable | Default | Description |
| --- | --- | --- |
| `lxc_onepassword_connect_node` | `{{ lxc_node }}` | PVE node the CT lives on. |
| `lxc_onepassword_connect_vmid` | `950` | CT id. |
| `lxc_onepassword_connect_template` | `local:vztmpl/debian-13-op-connect_<version>_<arch>.tar.zst` | The released template. |
| `lxc_onepassword_connect_template_checksum` | `""` (fetch refused) | The release's `sha256:`, pinned in the inventory. |
| `lxc_onepassword_connect_storage` | `{{ lxc_storage }}` | CT rootfs storage (the shared Ceph pool for HA). |
| `lxc_onepassword_connect_net0` | DHCP on `{{ lxc_bridge }}` | Full Proxmox net0; set a static `ip=/gw=` for a fixed address. |
| `lxc_onepassword_connect_features` | `["nesting=1"]` | Debian 13's systemd 257 needs nesting; the CT stays unprivileged. |
| `lxc_onepassword_connect_version` | `1.8.3` | Connect release: names the template, and `server` refuses a template of another version. Set in `templates/op-connect/template.yml` for the bake. |
| `lxc_onepassword_connect_arch` | `amd64` | Image arch to extract (`arm64` on a Pi). |
| `lxc_onepassword_connect_credentials_src` | `""` | Path on the node to `1password-credentials.json` (**required**, secret). |

## Dependencies

None declared. `lxc_guest` is composed at the point of need (`container.yml`, `remove.yml`). PVE API auth is supplied by the playbook through
the `group/community.proxmox.proxmox` module-defaults group reading the documented `PROXMOX_*` environment variables.

## Usage

[`playbooks/deploy-onepassword-connect.yml`](../../playbooks/deploy-onepassword-connect.yml) wires the three plays together; the operator
procedure is [`doc/howto/deploy-onepassword-connect.md`](../../doc/howto/deploy-onepassword-connect.md).

## Behaviour and security

The `1password-credentials.json` is installed `0600` owned by `opuser` under `~/.op`, every secret-bearing task is `no_log`, and the credentials
file is reported as shape only (present + byte size), never contents. The Connect **access token** is not handled here — it belongs to the
mirror side (`lxc_onepassword_item` / `reflect-onepassword-credentials.yml`). 1Password supports Docker-Compose/Kubernetes officially; running
the binaries bare is equivalent (same entrypoint, env, user and paths) but self-supported.

The `onepassword_connect_negative` Molecule scenario proves `server` stops at the baseline assertion on a guest that carries no marker,
before any change.
