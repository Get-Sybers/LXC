# get_sybers.lxc

The hardened LXC tier of the Get-Sybers lab. One role builds every container the same way — unprivileged, no SSH daemon, no container
runtime, reached only through `pct exec` from the Proxmox node — and each service that lives in such a container gets a build role and, where
operators need to put data into it, an API-client role. A container is touched only through the API it serves or through the roles in this
collection: the premise is [`docs/01-Hardened-LXC-Premise.md`](docs/01-Hardened-LXC-Premise.md), and `scripts/check_lxc_boundary.py` is its
detector.

This content moved here from the cluster collection (`get_sybers.cluster`, [get-sybers/proxmox](https://github.com/get-sybers/proxmox)),
which keeps the node-level operations (Ceph, SDN, the credential vault, Ludus) this tier builds on.

Licence: `AGPL-3.0-only` (see [`LICENSE`](LICENSE), declared in [`galaxy.yml`](galaxy.yml)).

## Install

```sh
ansible-galaxy collection install get_sybers.lxc
```

Consumers pin an exact version in their own `requirements.yml`. This collection's own runtime dependencies are pinned in
[`requirements.yml`](requirements.yml); the `galaxy.yml` bounds are what [`scripts/upgrade_pins.py`](scripts/upgrade_pins.py) raises within.

## Contents

### Roles

| Role | Tier | Purpose |
| --- | --- | --- |
| `lxc_preflight` | node | Admission gate every node-side play includes first: running as root, on a Proxmox VE node, with `pct` present. |
| `lxc_guest` | node + guest | The one lifecycle: facts, preflight (refuses a privileged request, a foreign CT id, a missing template or bridge), create via `community.proxmox.proxmox`, connect over `proxmox_pct_remote`, post-check from Proxmox; `baseline` inside the guest (purge `sshd`, refuse container runtimes, write the marker); opt-in `remove`. |
| `lxc_onepassword_connect` | build | Hand the Connect placement to `lxc_guest`, then run `op-connect-api`/`op-connect-sync` as native `systemd` services inside the CT (binaries extracted from the pinned official images; no Docker/OCI). `server` refuses a guest without the baseline marker. |
| `lxc_onepassword_item` | API client | Upsert one item into the Connect vault via `onepassword.connect.generic_item`, under `no_log` — the credential-mirror primitive. |

Each role ships `meta/argument_specs.yml` (typed, described inputs), `defaults/main.yml`, a `README.md` stating its contract, and Molecule
coverage under [`extensions/molecule/`](extensions/molecule) (see [Testing](#testing)).

### Playbooks

| Play | Runs on | Does |
| --- | --- | --- |
| [`deploy-onepassword-connect.yml`](playbooks/deploy-onepassword-connect.yml) | the node (`localhost`) | `lxc_preflight` → ensure the CT → `lxc_guest` baseline inside it → install and verify Connect; `--tags destroy -e lxc_guest_confirm_destroy=true` tears it down. |
| [`reflect-onepassword-credentials.yml`](playbooks/reflect-onepassword-credentials.yml) | anywhere that reaches the Connect API | Read the vaulted [`inventory/secrets/onepassword.yml`](inventory/secrets/onepassword.yml.example) and upsert each credential; idempotent. |

The plays carry no configuration of their own: every site-specific value — the node, template, storage, bridge, CT ids, addresses — lives in
[`inventory/`](inventory) (`group_vars/all/<topic>.yml`), which `ansible.cfg` points at so no `-i` is needed. The node-side plays run **on**
the Proxmox node as root (`pct` is node-local); PVE API auth comes from the `PROXMOX_*` environment variables
([`inventory/group_vars/all/proxmox_api.yml`](inventory/group_vars/all/proxmox_api.yml)).

### Documentation

- [`docs/01-Hardened-LXC-Premise.md`](docs/01-Hardened-LXC-Premise.md) — the rules, what enforces each, and how to add a service.
- [`docs/02-1Password-Connect.md`](docs/02-1Password-Connect.md) — the operator procedure for the Connect server and the credential mirror.

## Development

```sh
make deps        # install pinned collections + test tooling
prek install     # git hooks (lint, secrets, commit-msg)
make conform     # the full local gate: lint, pins, boundary, sanity, molecule, changelog, build
make upgrade     # raise every pin to its galaxy.yml ceiling, then re-run conform
```

### Testing

Molecule drives every role against a throwaway, digest-pinned Debian 13 container (the `community.docker` driver — a Proxmox node and a
Debian CT are both Debian), configured once in [`extensions/molecule/config.yml`](extensions/molecule/config.yml); each scenario overrides
only its own playbooks. The container is disposable test scaffolding — it is not a Proxmox node and never touches the cluster.

- **`default`** (positive): `lxc_guest`'s `baseline` against a substrate that `prepare` gave an SSH server — converge removes it, verify
  proves it, idempotence proves a second run is `changed=0`.
- **A negative scenario for every role** (`*_negative`): run without the role's live dependency, each role must stop at its own labelled
  assertion — never crash or silently proceed. `onepassword_connect_negative` is the premise's rule 5 in action: `server` refuses a guest
  without the baseline marker.
- **Roles that mutate a live Proxmox node** (`lxc_guest` create/connect/postcheck/remove) keep their positive path on a real node (the plays
  themselves); the container tier proves their refusal behaviour, and `ansible-lint --profile production` covers the rest.

Run the whole suite with `make molecule` (`molecule test --all`), or one scenario with `molecule test -s <scenario>`.

### CI lanes

The pull-request workflow runs only what a change can affect ([`scripts/molecule_lanes.py`](scripts/molecule_lanes.py) reads the diff): a
docs-only change skips the collection gate and molecule; a role change runs the scenarios that drive that role (so a change to `lxc_guest`
runs every scenario that includes it); a change to anything the scenarios share runs them all. Push to `main`, the nightly schedule and a
manual dispatch always run everything. The boundary check runs on every event.

Every change that touches a plugin needs a fragment in [`changelogs/fragments/`](changelogs/fragments). Releases follow standard 04: merge the
changelog, publish a GitHub release tagged `v<galaxy.yml version>`.
