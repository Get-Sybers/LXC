# 05 — distrobuilder

Run [distrobuilder](https://github.com/lxc/distrobuilder) — the LXC and Incus image builder — in a hardened Debian LXC, so the lab's
custom container images are built from reviewed image definitions on the cluster, by a role, instead of on a workstation by hand.

distrobuilder runs **as a command in a hardened Debian LXC** — no Docker, no OCI runtime, no SSH, and no daemon: nothing listens. The
template bake builds the pinned release from the Go module (verified against the Go checksum database) beside `debootstrap`, the archive
keys and the compressors, then purges the toolchain again. The result is the released `distrobuilder` template
([`templates/distrobuilder`](../../templates/distrobuilder/README.md)); the node creates the CT from it, places the image definitions,
and from then on every image is one run of the build play.

## Moving parts

| Piece | What it is |
| --- | --- |
| `templates/distrobuilder` + `.github/workflows/templates.yml` | The released template: Debian 13 with distrobuilder, `debootstrap`, the keys, the compressors, the directories and the baseline baked in; published as the `distrobuilder/v<version>` GitHub Release ([build-a-template.md](build-a-template.md)). |
| `lxc_guest` role | Fetches the released template into the node's cache by its pinned checksum, creates the CT from it (unprivileged, `nesting=1`, ownership-marked), reaches it over `pct exec`, re-asserts the baseline inside it. |
| `lxc_distrobuilder` role + `deploy-distrobuilder.yml` | `bake` is what the template carries; `container` hands the placement to `lxc_guest`; `server` asserts the markers and the baked tools and places the definitions inside the CT. |
| `build-distrobuilder-image.yml` | `connect` reaches the running CT; `build` runs `distrobuilder build-lxc` on one definition and pulls the tarballs onto the node. |
| `inventory/group_vars/all/distrobuilder.yml` | The placement: node, CT id, `net0`, the released template's checksum; and the image definitions. |

## Prerequisites (node side)

- The site configuration in place: `make config`, then replace every `CHANGE-ME` in `inventory/hosts.yml`,
  `inventory/group_vars/all/lxc.yml` and `inventory/group_vars/all/distrobuilder.yml` (node names, rootfs storage, the CT id). The
  repository carries only the template, `inventory/example/`; your copies are untracked.
- The released template's checksum pinned in your `inventory/group_vars/all/distrobuilder.yml` (`lxc_distrobuilder_template_checksum`,
  from the `.sha256` asset of the `distrobuilder/v<version>` release). The play fetches the template into the node's cache itself;
  nothing is downloaded without the pin. Verify the release first if you want to:
  [build-a-template.md §5](build-a-template.md#5-verifying-a-release-by-hand).
- The node can reach `github.com` to fetch the release asset once (or place the file in `/var/lib/vz/template/cache/` yourself); the CT
  can reach the distribution archives the definitions name (`deb.debian.org`, a keyserver) when it builds.
- Room on the rootfs storage: the CT's rootfs is `32` GB by default, because a build unpacks a whole distribution into the cache and
  packs it again.
- An admin PVE API credential in the environment (`PROXMOX_TOKEN_ID` + `PROXMOX_TOKEN_SECRET`, or `PROXMOX_PASSWORD`).
- The collection installed where the plays run: `ansible-galaxy collection install -r requirements.yml` (the plays run **on the node**,
  as root).

## Step 1 — Name the image definitions

A definition is distrobuilder's YAML description of an image: the source (`debootstrap` for Debian and Ubuntu, a tarball for most
others), the packages, the files, the actions. The [`lxc/lxc-ci`](https://github.com/lxc/lxc-ci/tree/main/images) repository carries
the definitions the public image server is built from, one per distribution; your own definitions work the same way. `server` places
each entry of `lxc_distrobuilder_definitions` in the CT, from a file on the node or from a URL pinned by checksum:

```yaml
# inventory/group_vars/all/distrobuilder.yml
lxc_distrobuilder_definitions:
  - name: debian.yaml
    url: https://raw.githubusercontent.com/lxc/lxc-ci/<commit>/images/debian.yaml
    checksum: "sha256:<the file's sha256sum>"
  - name: mine.yaml
    src: /root/distrobuilder/mine.yaml
```

Pin a commit in the URL, not a branch, and take the checksum from the file you reviewed; an entry with a URL and no `sha256:`/`sha512:`
is refused.

## Step 2 — Deploy the distrobuilder LXC

The placement — node, CT id, `net0` — and the definitions are your `inventory/group_vars/all/distrobuilder.yml`; nothing is left for the
command line. The CT lands on the `lxc_hosts` node running distrobuilder `3.4.0` (`amd64`).

Run it **on the node** that will host the CT:

```bash
export PROXMOX_TOKEN_ID='root@pam!ansible' PROXMOX_TOKEN_SECRET='…'
ansible-playbook playbooks/deploy-distrobuilder.yml
```

The play fetches the released template into the cache if it is not there, creates the LXC from it, re-asserts the baseline, asserts the
baked `distrobuilder` is the pinned version and `debootstrap` is beside it, and places the definitions under
`/var/lib/distrobuilder/definitions`. Re-running it is idempotent (`changed=0`).

## Step 3 — Build an image

One run of the build play is one image: the definition's file name, distrobuilder's `-o` overrides (the release and architecture the
`lxc-ci` definitions expect), and where on the node to pull the result.

```bash
ansible-playbook playbooks/build-distrobuilder-image.yml \
  -e lxc_distrobuilder_build_definition=debian.yaml \
  -e '{"lxc_distrobuilder_build_options": ["image.release=trixie", "image.architecture=amd64"]}' \
  -e lxc_distrobuilder_build_fetch_dir=/root/distrobuilder-images
```

Inside the CT, `distrobuilder build-lxc` assembles the rootfs under `/var/cache/lxc/distrobuilder`, packs it into
`/var/lib/distrobuilder/images/debian/rootfs.tar.xz` and `meta.tar.xz`, and the role writes `SHA256SUMS` beside them and pulls the three
files to `/root/distrobuilder-images/debian/` on the node. A finished image is not rebuilt: re-running the play is `changed=0` until
`-e lxc_distrobuilder_build_force=true` discards it, or `-e lxc_distrobuilder_build_name=debian-2` names a new output directory.
`-e lxc_distrobuilder_build_compression=zstd` packs the rootfs with `zstd` instead of `xz`; `-e lxc_distrobuilder_build_timeout=3600`
bounds the build.

## Verify

- From the node: `pct exec <vmid> -- distrobuilder --version` prints the pinned version, and `sha256sum -c SHA256SUMS` in the pulled
  directory passes. (There is no SSH into the CT: `pct exec` is the way in.)
- Re-running the deploy play is idempotent (`changed=0`); re-running the build play for a finished image is too.

## Tear down

```bash
ansible-playbook playbooks/deploy-distrobuilder.yml --tags destroy -e lxc_guest_confirm_destroy=true
```

`lxc_guest` refuses without the confirmation, refuses a CT that does not carry its marker, and refuses one whose hostname is not
`distrobuilder`. The images left in the CT go with it; pull what you want to keep first.

## How it works and what to know

- **Built from the module, not downloaded.** Upstream publishes no binaries (its own install path is a snap or `go install`), so the bake
  runs `go install github.com/lxc/distrobuilder/v3/distrobuilder@v<version>` with the tags upstream's Makefile sets. The module zip is fetched
  through `proxy.golang.org` and checked against `sum.golang.org`, and so is the `go1.25.12` toolchain the module's `go.mod` declares, which
  Debian 13's older `go` downloads to build it. The toolchain, the compiler and the module cache are purged before the image is sealed.
- **Root inside an unprivileged CT.** distrobuilder must run as root: it chroots into the rootfs it assembles, mounts `proc` and `sysfs`
  into it, and creates the device nodes a bootstrap needs. In an unprivileged Proxmox CT that root is the user-namespace root, and three
  node facts make the build work: `nesting=1` (the nested-container AppArmor profile), the cache under `/var/cache/lxc/` (the tree that
  profile allows `proc` and `sysfs` to be mounted under — the reason for `lxc_distrobuilder_cache_dir`), and `pve-lxc-syscalld`, which
  answers the `mknod` calls with nodes that are inert on the node. An overlay mount is not available to the CT; the role passes
  `--disable-overlay`, and distrobuilder copies the source rootfs with `rsync` instead.
- **What comes out.** `build-lxc` produces a plain rootfs tarball and an LXC metadata tarball with a `SHA256SUMS`. It is your artifact —
  for an LXC or Incus host, or for `pct create` by hand — and not a released template of this collection: `lxc_guest` creates guests only
  from the templates under `templates/`, baked in GitHub Actions and pinned by checksum (premise rule 9).
- **Secrets hygiene.** There are none: the box holds definitions and images. Definitions arrive from a file you hold or a URL you pinned.
- **Upgrade.** Raise `lxc_distrobuilder_version` (and `lxc_distrobuilder_go_toolchain` when the new `go.mod` asks for a newer one) in
  `templates/distrobuilder/template.yml`, publish it with the Templates workflow (`distrobuilder/v<new>`), pin the new template checksum, and recreate the CT from the new
  release (`--tags destroy -e lxc_guest_confirm_destroy=true`, then the deploy play). Pull the images you want to keep first.
