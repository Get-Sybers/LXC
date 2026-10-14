# lxc_distrobuilder

A [distrobuilder](https://github.com/lxc/distrobuilder) build box — the LXC and Incus image builder — in a **hardened Debian LXC**. No
Docker, no OCI runtime, no SSH, and no daemon either: `distrobuilder` is a command, run as root inside the CT, that turns an image
definition (the YAML files in [`lxc/lxc-ci`](https://github.com/lxc/lxc-ci/tree/main/images), or your own) into a rootfs tarball and a
meta tarball. The box carries `debootstrap`, the Debian and Ubuntu archive keys, `gpg` with `dirmngr`, `rsync` and the compressors
distrobuilder shells out to.

The image is baked, not installed: upstream publishes no binaries, so `bake` runs inside a build rootfs (from
[`templates/distrobuilder`](../../templates/distrobuilder/README.md) via `playbooks/bake-template.yml`) and builds the pinned release from
the Go module — `go install github.com/lxc/distrobuilder/v3/distrobuilder@v<version>`, fetched through the Go module proxy and verified
against the Go checksum database, with the toolchain the module's `go.mod` declares — then purges the toolchain and the compiler again.
The container itself is not this role's business: `container`, `connect` and `remove` hand the placement to
[`lxc_guest`](../lxc_guest/README.md), which owns the lifecycle and the hardened premise. `server` runs in the booted CT, refuses a guest
without the baseline marker or without the `distrobuilder` template marker at this role's version, and places the image definitions.
`build` is the interaction: one definition in, one image out, pulled onto the node if asked. After deployment the box is touched one way
only: this role over `pct exec`.

- **Privilege:** `container`/`connect`/`remove` run as root on the Proxmox node; `server` and `build` run as root inside the CT (over
  `community.proxmox.proxmox_pct_remote`) — distrobuilder requires root: it chroots into the rootfs it assembles, mounts `proc` and `sysfs`
  into it and creates the device nodes a bootstrap needs. In an unprivileged Proxmox CT with `nesting=1` those mounts are allowed under
  `/var/cache/lxc/` (the nested-container AppArmor profile), which is where the cache lives, and the `mknod` calls are answered by the
  node's `pve-lxc-syscalld`.
- **Collections:** `community.proxmox` (through `lxc_guest`) and `ansible.builtin`.
- **Idempotent:** yes. `server` reports `changed=0` on a settled guest; `build` does not rebuild a finished image (the rootfs tarball
  exists) unless `lxc_distrobuilder_build_force`; `bake` is run once per release into a fresh rootfs.
- **Platforms:** Debian (bookworm, trixie) CT on **Proxmox VE**. **Min ansible:** 2.19.

## Entry points

| `tasks_from` | Where it runs | What it does |
| --- | --- | --- |
| `bake` | the build rootfs (chroot) | debootstrap, the keys, gpg, rsync and the compressors; build the pinned release from the Go module, assert its version, purge the toolchain; the directories; no definitions, no build |
| `container` | node (`localhost`/`local`) | `lxc_guest` ensure path with this role's placement, template URL and checksum; the CT joins the `distrobuilder` group |
| `connect` | node | `lxc_guest` `connect` only: add the running CT to the play inventory for the build play |
| `server` | inside the CT | assert the baseline and template markers, the baked binary's version and `debootstrap`; the directories; place the definitions (`src` copied from the node, or `url` fetched by pinned checksum) |
| `build` | inside the CT | the server contract, then `distrobuilder build-lxc <definition> <images>/<name>`; `SHA256SUMS`; pull the three files onto the node when `lxc_distrobuilder_build_fetch_dir` is set |
| `remove` | node | `lxc_guest` `remove` with this role's placement (needs `-e lxc_guest_confirm_destroy=true`) |

## Inputs (selected — full list in `meta/argument_specs.yml`)

| Variable | Default | Description |
| --- | --- | --- |
| `lxc_distrobuilder_node` | `{{ lxc_node }}` | PVE node the CT lives on. |
| `lxc_distrobuilder_vmid` | `0` (refused) | CT id; the inventory sets it. |
| `lxc_distrobuilder_template_version` | `0.1.1` | This repository's release of the `distrobuilder` template (the manifest's `lxc_template_version`): names the artifact and the tag; `server` refuses a guest baked at another. |
| `lxc_distrobuilder_template` | `local:vztmpl/debian-13-distrobuilder_<template release>_<arch>.tar.zst` | The released template. |
| `lxc_distrobuilder_template_checksum` | `""` (fetch refused) | The release's `sha256:`, pinned in the inventory. |
| `lxc_distrobuilder_storage` | `{{ lxc_storage }}` | CT rootfs storage. |
| `lxc_distrobuilder_rootfs_gb` / `_cores` / `_memory_mb` | `32` / `2` / `2048` | A build unpacks a whole distribution into the cache and packs it again. |
| `lxc_distrobuilder_net0` | DHCP on `{{ lxc_bridge }}` | Full Proxmox net0; set a static `ip=/gw=` for a fixed address. |
| `lxc_distrobuilder_features` | `["nesting=1"]` | Lets a build mount `proc`/`sysfs` into the rootfs it assembles; the CT stays unprivileged. |
| `lxc_distrobuilder_version` | `3.4.0` | distrobuilder release the image carries (names the Go module version); `server` refuses a template whose marker says another. Set in `templates/distrobuilder/template.yml` for the bake. |
| `lxc_distrobuilder_go_toolchain` | `go1.25.12` | The toolchain the module declares; Debian's older `go` downloads and verifies it. |
| `lxc_distrobuilder_cache_dir` | `/var/cache/lxc/distrobuilder` | `--cache-dir`: where the rootfs is assembled, under the tree the nested profile allows `proc` mounts in. |
| `lxc_distrobuilder_definitions` | `[]` | `{name, src}` or `{name, url, checksum}` entries `server` places in `/var/lib/distrobuilder/definitions`. |
| `lxc_distrobuilder_build_definition` | `""` (required by `build`) | The definition's file name. |
| `lxc_distrobuilder_build_options` | `[]` | `-o` overrides, `key=value` each (`image.release=trixie`). |
| `lxc_distrobuilder_build_compression` | `xz` | The rootfs tarball's compression (`zstd` is the other useful one). |
| `lxc_distrobuilder_build_force` | `false` | Discard the finished image and build again. |
| `lxc_distrobuilder_build_fetch_dir` | `""` | A node directory to pull `rootfs.tar.*`, `meta.tar.xz` and `SHA256SUMS` into. |

## Dependencies

None declared. `lxc_guest` is composed at the point of need (`container.yml`, `connect.yml`, `remove.yml`). PVE API auth is supplied by the
playbook through the `group/community.proxmox.proxmox` module-defaults group reading the documented `PROXMOX_*` environment variables.

## Usage

[`playbooks/deploy-distrobuilder.yml`](../../playbooks/deploy-distrobuilder.yml) creates and verifies the box;
[`playbooks/build-distrobuilder-image.yml`](../../playbooks/build-distrobuilder-image.yml) builds one image in it. The operator procedure
is [`doc/howto/deploy-distrobuilder.md`](../../doc/howto/deploy-distrobuilder.md).

## Behaviour and security

Nothing listens: the box has no service port, and no SSH. A build runs as root inside an unprivileged CT, which is the whole of its
privilege — the node's user-namespace mapping, the devices cgroup and AppArmor apply to it as to any guest; `pve-lxc-syscalld` answers
the `mknod` calls a bootstrap makes with nodes that are inert on the node. Image definitions enter the CT either from a file on the node or
from a URL pinned by checksum, never from an unverified download; distribution sources are verified by the definition's own keys
(`debootstrap` checks the archive signatures with the baked keyrings or the keys the definition names). What comes out is a plain rootfs
tarball with a `SHA256SUMS`; it is the operator's artifact, not a released template of this collection — `lxc_guest` creates guests only
from the templates under [`templates/`](../../templates/README.md) (premise rule 9).

The `distrobuilder_negative` Molecule scenario proves `server` stops at the baseline assertion on a guest that carries no marker, before
any change.
