# 03 — Template build and release

**Premise:** a container is created only from a template this repository built. Templates are baked in GitHub Actions from a stock Proxmox
system template, published as GitHub Releases with a checksum, a signature and a build attestation, and fetched onto a node by the exact
checksum the inventory pins. A node never builds an image and never installs a service into a running guest.

One sentence governs the rest: **the release is the image, the checksum is its identity, and `pct create` is the only thing that happens
on the node.**

## 1. How Proxmox consumes a template

`pct create` takes any rootfs tarball that sits in a template storage, named `local:vztmpl/<file>`. That is all a Proxmox template is, and
it is the same thing `pveam` downloads for the stock Debian and TurnKey appliances. `pveam` itself reads only the two indexes Proxmox
hard-codes (`download.proxmox.com` and `releases.turnkeylinux.org`), so a template released here reaches the node through `lxc_guest`'s
`template` step instead: a `get_url` into the `local` storage's cache directory, verified against the pinned `sha256:`, after which the
template is indistinguishable from one `pveam` fetched. There is no second mechanism: a template that is not in the cache and has no
pinned checksum is refused, not downloaded.

## 2. The bake

[`playbooks/bake-template.yml`](../../playbooks/bake-template.yml) turns one manifest, `templates/<name>/template.yml`, into one artifact.
It runs as root on a build host (the GitHub Actions runner) and never touches a node.

| Step | What happens |
| --- | --- |
| base | The stock `debian-13-standard` template is downloaded from `download.proxmox.com` and verified against the `sha512` Proxmox publishes for it in its own index, pinned in the manifest. |
| unpack | `tar --zstd --numeric-owner --xattrs` into a work rootfs; `/proc`, `/sys`, `/dev`, `/dev/pts` are mounted; a resolver and a `policy-rc.d` that refuses service starts are dropped in for the duration of the bake. |
| bake steps | Each `lxc_template_bake` entry runs inside the rootfs over `community.general.chroot`: first `lxc_guest` `baseline` (purge `openssh-server`, refuse any container runtime, write the baseline marker), then the service role's `bake` (install, service user, units, `multi-user.target.wants` links). |
| marker | `/etc/get-sybers-lxc-template` records `name`, `version` and `base`. |
| clean | apt lists and cache cleared, the resolver and `policy-rc.d` removed, `/etc/machine-id` emptied so every container derives its own. |
| seal | `tar --zstd --numeric-owner --xattrs --acls` to `<base>-<name>_<version>_<arch>.tar.zst`; the listing is asserted to carry both markers and no `/usr/sbin/sshd`; a `.sha256` in `sha256sum` format is written beside it. |

A `bake` entry point is chroot-safe by construction: it installs, creates users, writes units and enables them by creating the
`multi-user.target.wants` symlinks (what `systemctl enable` does for `WantedBy=multi-user.target`), and it never starts a service or
touches a credential. Everything site-specific stays in `server`, which runs in the booted container.

## 3. The release

[`.github/workflows/templates.yml`](../../.github/workflows/templates.yml):

- **Manual only.** The workflow has no push or pull-request trigger: a run is started by hand (*Actions → Templates → Run workflow*),
  naming one template and whether to publish it. The job runs in the `templates` environment, whose required reviewer approves every
  run before a single step executes; nothing is baked or shipped without that approval.
- **A bake** (publish off) builds the template from any branch and keeps the `.tar.zst` and its `.sha256` as a workflow artifact for two
  weeks, so a change to an image can be inspected as a built image.
- **A publish** (publish on, `main` only) bakes, then creates the `<name>/v<version>` tag and GitHub Release carrying the `.tar.zst`, its
  `.sha256`, a keyless cosign signature bundle (`<file>.sigstore.json`) and a GitHub build-provenance attestation. The release notes give
  the three verification commands and the inventory key to pin. The version is never an input: it is the manifest's
  `lxc_template_version`, read back from the artifact the bake named, so the tag follows the reviewed manifest and nothing else.
- **The version is the template's own.** `lxc_template_version` is this repository's release of the template (`X.Y.Z`), separate from
  the service version the image carries (`lxc_template_service_version`, written to the marker as `service=`). It is raised in the pull
  request that changes the image, whether that is a new service release or a changed bake, and the Version Gate
  ([`.github/workflows/version-gate.yml`](../../.github/workflows/version-gate.yml), `scripts/check_template_pins.py`, the
  `lxc-template-pin` check the `main` ruleset requires) refuses a pull request that changes a manifest directory, the service role's
  bake inputs or the `lxc_guest` baseline without moving it forward.
- **A release is immutable.** A publish refuses a tag that already exists: the gate keeps a changed image from reaching `main` under a
  published version, and the publish refuses to overwrite one if it ever does.

The collection's own releases are `v<version>` tags; the Galaxy publish workflow skips any tag with a `/` in it. Both tag shapes are
immutable under `.github/rulesets/tags.json`. The `templates` environment is created once in the repository settings (*Settings →
Environments*): a required reviewer and no secrets.

## 4. On the node

The inventory pins the released template per service:

```yaml
# inventory/group_vars/all/onepassword.yml
lxc_onepassword_connect_template_checksum: "sha256:<the value in the release's .sha256>"
```

The URL and the file name derive from the role's template release (`lxc_onepassword_connect_template_version`, the manifest's
`lxc_template_version`) and the collection variable `lxc_template_release_base` (this repository's GitHub Releases; point it at a mirror
for a lab with no reach to `github.com`), so raising the template release and pinning the new checksum is the whole upgrade. `lxc_guest`'s `template` step then fetches the artifact into `/var/lib/vz/template/cache/` when it is not
there, `preflight` sees it on the storage, and `create` proceeds. The service role's `server` entry point refuses a guest whose template
marker does not say `name=<service>` at the role's template release and service version: the binaries come from the release, never
from an install into a live guest.

## 5. Verifying a release by hand

```sh
sha256sum -c debian-13-op-connect_1.0.0_amd64.tar.zst.sha256
cosign verify-blob --bundle debian-13-op-connect_1.0.0_amd64.tar.zst.sigstore.json \
  --certificate-identity-regexp '^https://github.com/get-sybers/lxc/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  debian-13-op-connect_1.0.0_amd64.tar.zst
gh attestation verify debian-13-op-connect_1.0.0_amd64.tar.zst -R get-sybers/lxc
```

## 6. Raising a base template

The base is pinned by file name and Proxmox's published `sha512`. To move to a newer stock template, print the new pin and paste it into
every manifest that uses it:

```sh
python3 scripts/base_template_checksum.py debian-13-standard_13.2-1_amd64.tar.zst
```

Bake locally the same way the workflow does, from the repository root as root, with the pinned collections on the collections path:

```sh
sudo env ANSIBLE_COLLECTIONS_PATH=... ansible-playbook playbooks/bake-template.yml \
  -e lxc_template_dir=$PWD/templates/op-connect -e lxc_template_workdir=$PWD/build/op-connect
```

A failed step unmounts the kernel filesystems the play mounted under the work rootfs (`proc`, `sys`, a bind of the build host's
`/dev`, `dev/pts`) and leaves the rootfs in place to inspect. Only an interrupted run can leave them mounted: check `findmnt` for
mounts under a work tree before removing it, because the host's `/dev` is bound there. The download step accepts a base file that is
already in `<workdir>/base/` at the pinned checksum, so a node's own template cache (`/var/lib/vz/template/cache/`) can stand in for
`download.proxmox.com`.
