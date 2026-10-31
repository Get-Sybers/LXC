# 03 — Template build and release

**Premise:** a container is created only from a template this repository built. Templates are baked in GitHub Actions from a stock Proxmox
system template, published to the GitHub Container Registry (GHCR) as signed, attested **OCI images**, and imported onto a node through
Proxmox's own OCI support. A node never builds an image and never installs a service into a running guest.

One sentence governs the rest: **the image is the template, its digest is its identity, and `pct create` is the only thing that happens
on the node.**

## 1. How Proxmox consumes a template

The sealed template is a single rootfs tarball (`.tar.zst`). It is published as an **OCI image** whose one layer is that exact tarball
(reported as `application/vnd.oci.image.layer.v1.tar+zstd`), under a real OCI image config that carries the template's labels. Proxmox VE
9 reads OCI images natively: `pct create` detects an OCI archive and maps its config into the container config, so an image published here
runs as a system container just like a `pveam` appliance. The node pulls it with `skopeo` (built into PVE's OCI support) — the registry
token handshake and the layer are handled for you, so there is no checksum to paste for the pull; the image digest is the identity.

There is no second mechanism: `pct create` takes either a `pveam`/release rootfs tarball in `local:vztmpl/<file>` or an OCI image pulled
into that same storage. A template with no image in the registry and nothing in the cache is not created.

## 2. The bake

[`playbooks/bake-template.yml`](../../playbooks/bake-template.yml) turns one manifest, `templates/<name>/template.yml`, into one artifact.
It runs as root on a build host (the GitHub Actions runner) and never touches a node.

| Step | What happens |
| --- | --- |
| base | The stock `debian-13-standard` template is downloaded from `download.proxmox.com` over plain HTTP, as `pveam` fetches it (the host is not served over TLS), and verified against the `sha512` Proxmox publishes for it in its own signed index, pinned in the manifest: the checksum is the verification. |
| unpack | `tar --zstd --numeric-owner --xattrs` into a work rootfs; `/proc`, `/sys`, `/dev`, `/dev/pts` are mounted; a resolver and a `policy-rc.d` that refuses service starts are dropped in for the duration of the bake. |
| bake steps | Each `lxc_template_bake` entry runs inside the rootfs over `community.general.chroot`: first `lxc_guest` `baseline` (purge `openssh-server`, refuse any container runtime, write the baseline marker), then the service role's `bake` (install, service user, units, `multi-user.target.wants` links). |
| marker | `/etc/get-sybers-lxc-template` records `name`, `version` and `base`. |
| clean | apt lists and cache cleared, the resolver and `policy-rc.d` removed, `/etc/machine-id` emptied so every container derives its own. |
| seal | `tar --zstd --numeric-owner --xattrs --acls` to `<base>-<name>_<version>_<arch>.tar.zst`; the listing is asserted to carry both markers and no `/usr/sbin/sshd`; a `.sha256` in `sha256sum` format is written beside it. |

A `bake` entry point is chroot-safe by construction: it installs, creates users, writes units and enables them by creating the
`multi-user.target.wants` symlinks (what `systemctl enable` does for `WantedBy=multi-user.target`), and it never starts a service or
touches a credential. Everything site-specific stays in `server`, which runs in the booted container.

## 3. The publish

[`.github/workflows/templates.yml`](../../.github/workflows/templates.yml):

- **Manual only.** The workflow has no push or pull-request trigger: a run is started by hand (*Actions → Templates → Run workflow*),
  naming one template and whether to publish it. The job runs in the `templates` environment, whose required reviewer approves every
  run before a single step executes; nothing is baked or shipped without that approval.
- **A bake** (publish off) builds the template from any branch and keeps the `.tar.zst` and its `.sha256` as a workflow artifact for two
  weeks, so a change to an image can be inspected as a built image.
- **A publish** (publish on, `main` only) bakes, then pushes the sealed `.tar.zst` unchanged — as the single `tar+zstd` layer of an OCI
  image under a real `image.config.v1+json` config carrying the template labels — to `ghcr.io/<owner>/lxc/<name>:v<version>`. It signs
  the image (keyless cosign), attaches a GitHub build-provenance attestation to the registry, and tags the commit `<name>/v<version>`.
  Authentication is the workflow's built-in `GITHUB_TOKEN` with `packages: write`; no secret or key is configured. The version is never
  an input: it is the manifest's `lxc_template_version`, read back from the artifact the bake named. **No GitHub Release is created.**
- **The version is the template's own.** `lxc_template_version` is this repository's release of the template (`X.Y.Z`), separate from
  the service version the image carries (`lxc_template_service_version`, written to the marker as `service=`). It is raised in the pull
  request that changes the image, whether that is a new service release or a changed bake, and the Version Gate
  ([`.github/workflows/version-gate.yml`](../../.github/workflows/version-gate.yml), `scripts/check_template_pins.py`, the
  `lxc-template-pin` check the `main` ruleset requires) refuses a pull request that changes a manifest directory, the service role's
  bake inputs or the `lxc_guest` baseline without moving it forward, using the `<name>/v<version>` git tags to know what has shipped. A
  version that was never tagged may be renumbered (backwards included) instead.
- **A publish is immutable.** The workflow refuses to push a `ghcr.io/<owner>/lxc/<name>:v<version>` tag that already exists, and the gate
  keeps a changed image from reaching `main` under an already-tagged version.

The `<name>/v<version>` git tag is immutable under `.github/rulesets/tags.json`. The `templates` environment is created once in the
repository settings (*Settings → Environments*): a required reviewer and no secrets. The package is private on first publish; make it
public once per template in its GHCR settings so nodes can pull it without credentials.

## 4. On the node — importing from GHCR

Browse the published versions, then pull one into a template storage and create the container from it. Run on the node:

```sh
# list the versions published for a template
pvesh get /nodes/<node>/query-oci-repo-tags --reference ghcr.io/<owner>/lxc/<name>

# pull a version into the `local` storage's template cache (uses skopeo; no checksum to paste)
pvesh create /nodes/<node>/storage/local/oci-registry-pull \
  --reference ghcr.io/<owner>/lxc/<name>:v<version> --filename <name>_<version>

# create the container from it — pct detects the OCI image and maps its config
pct create <vmid> local:vztmpl/<name>_<version>.tar --hostname <name> --rootfs <storage>:<gb> \
  --unprivileged 1 --features nesting=1 --memory <mb> --cores <n> --net0 name=eth0,bridge=<bridge>,ip=dhcp
```

The pull needs `skopeo` on the node (part of PVE's OCI support) and the package to be public (or a `docker login ghcr.io` for a private
one). `pct create` then extracts the `tar+zstd` layer and reads the OCI config; the service role's `server` entry point afterwards
refuses a guest whose template marker does not say `name=<service>` at the role's template release and service version, so the binaries
come from the image, never from an install into a live guest.

> **Migration note.** The deploy playbooks still drive the node through `lxc_guest`, whose `template` step currently `get_url`s a release
> tarball by a pinned `sha256:`. Moving that step to the GHCR import above (so `deploy-<service>.yml` pulls the OCI image) is the
> consume-side follow-up to the GHCR publish; until it lands, the commands here are the manual import path.

## 5. Verifying a published image by hand

```sh
cosign verify ghcr.io/<owner>/lxc/<name>:v<version> \
  --certificate-identity-regexp '^https://github.com/get-sybers/lxc/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/<owner>/lxc/<name>:v<version> -R get-sybers/lxc
```

Both resolve the image by digest; the cosign signature and the build-provenance attestation prove it was published by this workflow.

## 6. Raising a base template

The base is pinned by file name and Proxmox's published `sha512`. To move to a newer stock template, print the new pin on a Proxmox node (the script reads
the index `pveam` verified there) and paste it into every manifest that uses it:

```sh
python3 scripts/base_template_checksum.py debian-13-standard_13.7-1_amd64.tar.zst
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
