# get_sybers.lxc

The hardened LXC tier of the Get-Sybers lab. One role builds every container the same way — unprivileged, no SSH daemon, no container
runtime, reached only through `pct exec` from the Proxmox node — and each service that lives in such a container gets a build role and, where
operators need to put data into it, an API-client role. A container is touched only through the API it serves or through the roles in this
collection: the premise is [`doc/reference/hardened-lxc-premise.md`](doc/reference/hardened-lxc-premise.md), and `scripts/check_lxc_boundary.py` is its
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
| `lxc_onepassword_connect` | build | `bake` puts the `connect-api`/`connect-sync` binaries, units and service user into the template (extracted from the pinned official images; no Docker/OCI); `container` hands the placement and the released template to `lxc_guest`; `server` installs the credentials and starts the units, refusing a guest without the baseline and template markers. |
| `lxc_onepassword_item` | API client | Upsert one item into the Connect vault via `onepassword.connect.generic_item`, under `no_log` — the credential-mirror primitive. |
| `lxc_semaphore` | build | `bake` puts the official Semaphore UI package (verified against the release's checksum), the tools its tasks shell out to, the service user and the unit into the template; `container` hands the placement and the released template to `lxc_guest`; `server` writes `config.json` (SQLite), migrates, creates the administrator and starts the unit, refusing a guest without the baseline and template markers. |
| `lxc_distrobuilder` | build | `bake` builds the pinned distrobuilder release from the Go module (checksum-database verified) into the template beside `debootstrap`, the archive keys and the compressors; `container`/`connect`/`remove` hand the placement to `lxc_guest`; `server` asserts the markers and places the image definitions; `build` runs `distrobuilder build-lxc` on one definition and pulls the tarballs onto the node. |

Each role ships `meta/argument_specs.yml` (typed, described inputs), `defaults/main.yml`, a `README.md` stating its contract, and Molecule
coverage under [`extensions/molecule/`](extensions/molecule) (see [Testing](#testing)).

### Templates

Every container is created from a template built here and published as a GitHub Release ([`doc/howto/build-a-template.md`](doc/howto/build-a-template.md)).
One directory per template under [`templates/`](templates/README.md):

| Template | Release tag | Carries |
| --- | --- | --- |
| [`op-connect`](templates/op-connect/README.md) | `op-connect/v<template release>` | Debian 13, the `connect-api`/`connect-sync` binaries and units, `opuser`, the baseline (no `sshd`) |
| [`semaphore`](templates/semaphore/README.md) | `semaphore/v<template release>` | Debian 13, the `semaphore` package and unit, `git`/`openssh-client`/`sshpass`/`rsync`/`ansible-core`, the `semaphore` user, the baseline (no `sshd`) |
| [`distrobuilder`](templates/distrobuilder/README.md) | `distrobuilder/v<template release>` | Debian 13, `distrobuilder` built from the Go module, `debootstrap` + the Debian/Ubuntu keys, `gpg`/`dirmngr`, `rsync`, the compressors, the baseline (no `sshd`) |

[`playbooks/bake-template.yml`](playbooks/bake-template.yml) bakes a manifest into an artifact; [`.github/workflows/templates.yml`](.github/workflows/templates.yml)
runs it on demand only, behind the `templates` environment's required reviewer, and publishes the `<name>/v<version>` release with a
checksum, a cosign signature and a provenance attestation.
On the node, `lxc_guest` fetches the release by the checksum the inventory pins.

### Playbooks

| Play | Runs on | Does |
| --- | --- | --- |
| [`deploy-onepassword-connect.yml`](playbooks/deploy-onepassword-connect.yml) | the node (`localhost`) | `lxc_preflight` → ensure the CT → `lxc_guest` baseline inside it → install and verify Connect; `--tags destroy -e lxc_guest_confirm_destroy=true` tears it down. |
| [`deploy-semaphore.yml`](playbooks/deploy-semaphore.yml) | the node (`localhost`) | `lxc_preflight` → ensure the CT → `lxc_guest` baseline inside it → configure, migrate, create the administrator, start and verify Semaphore; `--tags destroy -e lxc_guest_confirm_destroy=true` tears it down. |
| [`deploy-distrobuilder.yml`](playbooks/deploy-distrobuilder.yml) | the node (`localhost`) | `lxc_preflight` → ensure the CT → `lxc_guest` baseline inside it → assert the baked tools and place the image definitions; `--tags destroy -e lxc_guest_confirm_destroy=true` tears it down. |
| [`build-distrobuilder-image.yml`](playbooks/build-distrobuilder-image.yml) | the node (`localhost`) | `lxc_preflight` → reach the running CT → `distrobuilder build-lxc` on one definition inside it, `SHA256SUMS`, pull the tarballs onto the node. |
| [`reflect-onepassword-credentials.yml`](playbooks/reflect-onepassword-credentials.yml) | anywhere that reaches the Connect API | Read the vaulted [`inventory/secrets/onepassword.yml`](inventory/secrets/onepassword.yml.example) and upsert each credential; idempotent. |
| [`bake-template.yml`](playbooks/bake-template.yml) | a build host, as root (the Templates workflow) | Bake `templates/<name>/template.yml` into a sealed `.tar.zst` + `.sha256`; never touches a node. |

The plays carry no configuration of their own: every site-specific value — the node, storage, bridge, CT ids, addresses, the released
template checksums — lives in [`inventory/`](inventory), which `ansible.cfg` points at so no `-i` is needed. The repository carries only
the template of that configuration, [`inventory/example/`](inventory/example); `make config` copies it into place and the copies are
untracked, so no node name, subnet or CT id is ever committed. The node-side plays run **on**
the Proxmox node as root (`pct` is node-local); PVE API auth comes from the `PROXMOX_*` environment variables
([`inventory/group_vars/all/proxmox_api.yml`](inventory/example/group_vars/all/proxmox_api.yml)).

### Documentation

[`doc/index.md`](doc/index.md) is the entry point: [how-to guides](doc/howto/index.md) (deploy 1Password Connect, Semaphore UI or distrobuilder,
build and release a template, add a service) and [reference](doc/reference/index.md) (the hardened-LXC premise and what enforces each rule, the template
manifest, the roles).

## Repository layout

```text
.
├── doc/                  # documentation: index.md, howto/, reference/
├── templates/            # one directory per LXC template: the manifest and its README
├── roles/                # lxc_preflight, lxc_guest, lxc_onepassword_connect, lxc_onepassword_item, lxc_semaphore, lxc_distrobuilder
├── playbooks/            # deploy-*, build-*, reflect-*, bake-template
├── inventory/            # the single config home (hosts, group_vars, secrets examples)
├── extensions/molecule/  # the test scenarios and their Debian substrate
├── scripts/              # check_lxc_boundary, check_pins, upgrade_pins, molecule_lanes, base_template_checksum
├── changelogs/           # antsibull-changelog fragments and the generated changelog
├── meta/, galaxy.yml     # the collection manifest
├── Makefile              # make conform: the local gate CI runs
├── AUTHORS, MAINTAINERS, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, LICENSE
└── .github/              # workflows (CI, Templates, Release, Links, Update pins, Scorecard), rulesets, issue and PR templates
```

## Development

```sh
make config      # copy the configuration template into inventory/ (untracked), then replace every CHANGE-ME
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
  assertion — never crash or silently proceed. `onepassword_connect_negative`, `semaphore_negative` and `distrobuilder_negative` are the premise's rule 5 in action:
  `server` refuses a guest without the baseline marker.
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
