# templates/ — one directory per LXC template

Every container this collection creates is built from a template that was baked here, in a GitHub Actions workflow, and published as a
GitHub Release. A directory under `templates/` is the complete definition of one template; nothing about a template lives anywhere else.

```text
templates/
├── README.md                  # this file
└── <name>/                    # one directory per template, named as the release tag prefix (<name>/v<version>)
    ├── template.yml           # the manifest: base rootfs + its checksum, the template release and the service version, the bake steps, the output name
    └── README.md              # what the template carries and how it is used
```

The manifest's keys are documented in [`doc/reference/template-manifest.md`](../doc/reference/template-manifest.md).

## How a template becomes a container

1. **Bake** — `playbooks/bake-template.yml` downloads the base rootfs, verifies it against the pinned checksum, unpacks it, runs the bake
   steps inside it over `community.general.chroot`, writes `/etc/get-sybers-lxc-template` (name, version, base), seals the result as a
   `.tar.zst`, and writes its `.sha256`. [`.github/workflows/templates.yml`](../.github/workflows/templates.yml) runs this on demand only:
   a run is started by hand for one template, waits for the `templates` environment's required reviewer, and, when asked to publish,
   creates the `<name>/v<version>` tag and GitHub Release with a cosign signature and a build provenance attestation.
2. **Pin** — the inventory records the released artifact's URL and `sha256:` (`lxc_<service>_template_url` /
   `lxc_<service>_template_checksum`).
3. **Fetch** — on the node, `lxc_guest` downloads the artifact into the template cache with that checksum when it is not already there.
   A missing or empty checksum is refused; nothing unverified reaches the cache.
4. **Create** — `pct create` from the cached template, exactly as for any Proxmox template. The service role's `server` entry point then
   asserts the template marker and the baseline marker before it configures anything.

## Adding a template

1. `mkdir templates/<name>`, write `template.yml` (copy `op-connect/template.yml`), pin the base checksum with
   `python3 scripts/base_template_checksum.py <base file name>`.
2. Give the service role a chroot-safe `bake` entry point (install, users, units, `multi-user.target.wants` symlinks; no credentials, no
   `systemctl start`) and keep `server` to run-time work.
3. Open a PR; the Version Gate requires `lxc_template_version` to move forward whenever the image changes. Once merged, run the
   Templates workflow for the template with *publish* on; the environment's reviewer approves it and the run creates the
   `<name>/v<version>` release. (A run with *publish* off bakes from any branch and only keeps the artifact.)
4. Pin the release in `inventory/group_vars/all/<service>.yml`.
