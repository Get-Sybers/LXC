# distrobuilder

The [distrobuilder](https://github.com/lxc/distrobuilder) build-box template: Debian 13 with the pinned distrobuilder release built from
the Go module (verified against the Go checksum database; the toolchain and compiler purged again), `debootstrap` with the Debian and
Ubuntu archive keys, `gpg`/`dirmngr`, `rsync`, `squashfs-tools` and the compressors (`xz`, `zstd`, `gzip`, `bzip2`), the definitions,
images and cache directories, no SSH server, and the `lxc_guest` baseline marker. Nothing site-specific is in it: the image definitions
arrive on the node, in `lxc_distrobuilder`'s `server` entry point, and every image is built on demand by its `build` entry point.

| | |
| --- | --- |
| Release tag | `distrobuilder/v<distrobuilder version>` (`distrobuilder/v3.4.0`) |
| Artifact | `debian-13-distrobuilder_<version>_<arch>.tar.zst` + `.sha256`, cosign bundle, provenance attestation |
| Base | `debian-13-standard_13.1-2_amd64.tar.zst` from `download.proxmox.com` |
| Bake steps | `lxc_guest` `baseline`, then `lxc_distrobuilder` `bake` |
| Consumed by | `inventory/group_vars/all/distrobuilder.yml` (`lxc_distrobuilder_template_checksum`), `playbooks/deploy-distrobuilder.yml`, `playbooks/build-distrobuilder-image.yml` |

To raise the distrobuilder version: change `lxc_distrobuilder_version` and, when its `go.mod` moved on, `lxc_distrobuilder_go_toolchain`
here, open a PR (the workflow bakes it), tag `distrobuilder/v<new>`, then pin the new release's URL and `sha256:` in the inventory.
