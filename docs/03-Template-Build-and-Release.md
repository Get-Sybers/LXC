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

[`playbooks/bake-template.yml`](../playbooks/bake-template.yml) turns one manifest, `templates/<name>/template.yml`, into one artifact.
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

[`.github/workflows/templates.yml`](../.github/workflows/templates.yml):

- **Every pull request and push to `main`** that touches `templates/`, the bake play, a role or the pins bakes every template and keeps the
  artifacts as workflow artifacts for two weeks, so a change to an image is reviewed as a built image.
- **A tag `<name>/v<version>`** bakes that template and publishes a GitHub Release carrying the `.tar.zst`, its `.sha256`, a keyless
  cosign signature bundle (`<file>.sigstore.json`) and a GitHub build-provenance attestation. The release notes give the three
  verification commands and the inventory key to pin.

The collection's own releases are `v<version>` tags; the Galaxy publish workflow skips any tag with a `/` in it. Both tag shapes are
immutable under `.github/rulesets/tags.json`.

## 4. On the node

The inventory pins the released template per service:

```yaml
# inventory/group_vars/all/onepassword.yml
lxc_onepassword_connect_template_checksum: "sha256:<the value in the release's .sha256>"
```

The URL and the file name derive from the role's version (`lxc_onepassword_connect_version`) and the collection variable
`lxc_template_release_base` (this repository's GitHub Releases; point it at a mirror for a lab with no reach to `github.com`), so raising
the version and pinning the new checksum is the whole upgrade. `lxc_guest`'s `template` step then fetches the artifact into `/var/lib/vz/template/cache/` when it is not
there, `preflight` sees it on the storage, and `create` proceeds. The service role's `server` entry point refuses a guest whose template
marker does not say `name=<service>` at the role's version: the binaries come from the release, never from an install into a live guest.

## 5. Verifying a release by hand

```sh
sha256sum -c debian-13-op-connect_1.8.3_amd64.tar.zst.sha256
cosign verify-blob --bundle debian-13-op-connect_1.8.3_amd64.tar.zst.sigstore.json \
  --certificate-identity-regexp '^https://github.com/get-sybers/lxc/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  debian-13-op-connect_1.8.3_amd64.tar.zst
gh attestation verify debian-13-op-connect_1.8.3_amd64.tar.zst -R get-sybers/lxc
```

## 6. Raising a base template

The base is pinned by file name and Proxmox's published `sha512`. To move to a newer stock template, print the new pin and paste it into
every manifest that uses it:

```sh
python3 scripts/base_template_checksum.py debian-13-standard_13.2-1_amd64.tar.zst
```

Bake locally the same way the workflow does, from the repository root as root, with the pinned collections on the collections path:

```sh
sudo env ANSIBLE_COLLECTIONS_PATH=... ansible-playbook playbooks/bake-template.yml -e lxc_template_dir=$PWD/templates/op-connect
```
