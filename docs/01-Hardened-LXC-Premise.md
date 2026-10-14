# 01 — The hardened LXC premise

**Premise:** every container this collection builds is a sealed appliance. It is created unprivileged on a Proxmox node from a plain Debian
template, it runs its service natively under `systemd`, and it is touched in exactly two ways afterwards: through the API the service itself
serves, and through the Ansible roles in this collection, which reach it only by `pct exec` from the node. Nothing else gets in.

One sentence governs the rest: **a container has no door of its own — the node is the door, and the roles here hold the only key.**

## 1. The rules

| # | Rule | Enforced by |
| --- | --- | --- |
| 1 | **Unprivileged, always.** `unprivileged: 1` is a constant of `lxc_guest`, not an input. A request to create a privileged container is refused in preflight; a privileged container found in post-check fails the run. | `lxc_guest` `vars/main.yml`, `preflight.yml`, `postcheck.yml` |
| 2 | **No SSH into a guest.** The guest carries no SSH daemon (`baseline` purges `openssh-server` and refuses an `sshd` binary). Ansible reaches the guest over `community.proxmox.proxmox_pct_remote`, which is `pct exec` on the node. No play or role in this repository sets `ansible_connection: ssh` for a guest, and `raw:` is never used. | `lxc_guest` `baseline.yml`, `connect.yml`; `scripts/check_lxc_boundary.py` |
| 3 | **No container runtime inside a guest.** The service runs as native `systemd` units under an unprivileged system user. Docker, containerd, podman, nerdctl and nested LXC are refused by `baseline` — refused, not removed, because their presence means someone put them there on purpose. | `lxc_guest` `baseline.yml` |
| 4 | **Node-side mechanics live in one role.** Only `lxc_guest` calls `pct`, `pvesh` or `community.proxmox.proxmox`. A service role (`lxc_<service>`) hands its placement to `lxc_guest` and otherwise runs only inside the guest. | `scripts/check_lxc_boundary.py` |
| 5 | **A service role refuses a guest that skipped the baseline.** `baseline` writes a marker (`lxc_baseline_marker_path`); every service role's in-guest entry point asserts it before changing anything. | each `lxc_<service>` role; `scripts/check_lxc_boundary.py` |
| 6 | **The collection owns what it creates, and only that.** `create` stamps an ownership marker into the container description; `preflight` refuses a CT id that exists without it; `remove` is opt-in (`lxc_guest_confirm_destroy=true`), refuses a CT without the marker, and refuses one whose hostname is not the one described. | `lxc_guest` `create.yml`, `preflight.yml`, `remove.yml` |
| 7 | **Interaction with a running service is its API.** Writing data into a service (credentials into 1Password Connect) goes through the service's own API from an `lxc_<service>_item`-style client role, under `no_log`, never by editing files in the guest. | `lxc_onepassword_item`; the service's design |
| 8 | **Secrets are supplied, never stored.** PVE API credentials come from `PROXMOX_*` environment variables; service credentials from a vaulted `inventory/secrets/` file passed with `-e`; every secret-bearing task is `no_log` and reports shape only. | `inventory/group_vars/all/proxmox_api.yml`, `inventory/secrets/` |

## 2. What this buys

- **A small, known surface.** A guest answers on its service port and nothing else. There is no SSH key to rotate, no `authorized_keys` to
  audit, no password to leak.
- **One lifecycle.** Every container is created, verified, hardened and destroyed by the same code; a new service is a service role plus a
  placement file, never a second copy of the container mechanics.
- **Loud failure.** Each rule is an assertion with a `fail_msg` that names the fix. Config drift on an existing container is reconciled
  by `create` (`update: true`) and then proved by `postcheck` from Proxmox; what cannot be reconciled in place (a privileged container) fails
  the run.

## 3. What it does not claim

- **It is not a Ludus range asset.** Range containers (the GHOSTS LXC in `get_sybers.range`) are deliberately *unhardened* — that tier's
  premise is "robust, not hardened". They stay in the Ludus source tree and never come here.
- **It is not the cluster tier.** Node-level operations (Ceph, SDN, the credential vault, Ludus) stay in `get_sybers.cluster`
  (`get-sybers/proxmox`). This collection needs only a node, a template, a bridge and an admin PVE API credential from that tier.
- **`nesting=1` is not a breach.** Debian 13's systemd 257 needs nested namespaces to boot; the feature is per-guest input
  (`lxc_guest_features`) and the container stays unprivileged. A *container runtime* inside the guest is the thing rule 3 refuses.

## 4. Adding a service

1. **A role `lxc_<service>`** with three entry points: `container` (node side — include `lxc_guest` with the placement), `server` (guest
   side — assert the baseline marker first, then configure), `remove` (node side — include `lxc_guest` `tasks_from: remove`). Its defaults
   point at the collection variables in `inventory/group_vars/all/lxc.yml`.
2. **An API-client role `lxc_<service>_item`** (or similar) if operators need to put data into the running service.
3. **A play `deploy-<service>.yml`** sequencing: `lxc_preflight` → `container` → `lxc_guest` `baseline` → `server`, plus the opt-in destroy play
   under `--tags destroy`.
4. **A placement file** `inventory/group_vars/all/<service>.yml` and, if it needs secrets, a `inventory/secrets/<service>.yml.example`.
5. **Molecule**: a negative scenario proving `server` refuses a guest without the marker; `make conform` runs the boundary check.

The boundary check is the detector for rules 2, 4 and 5. A rule with no detector is a suggestion.
