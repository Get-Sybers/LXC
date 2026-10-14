# semaphore

The [Semaphore UI](https://semaphoreui.com/) template: Debian 13 with the official `semaphore` Debian package (verified against the
checksum the release publishes), the tools its tasks shell out to (`git`, `openssh-client`, `sshpass`, `rsync`, `ansible-core`), an
unprivileged `semaphore` service user with its data directory, a native `systemd` unit enabled for `multi-user.target`, no SSH server, and
the `lxc_guest` baseline marker. Nothing site-specific is in it: the configuration (SQLite database path, port, cookie and encryption
keys), the database migrations, the administrator account and the unit's first start happen on the node, in `lxc_semaphore`'s `server`
entry point.

| | |
| --- | --- |
| Release tag | `semaphore/v<semaphore version>` (`semaphore/v2.19.16`) |
| Artifact | `debian-13-semaphore_<version>_<arch>.tar.zst` + `.sha256`, cosign bundle, provenance attestation |
| Base | `debian-13-standard_13.1-2_amd64.tar.zst` from `download.proxmox.com` |
| Bake steps | `lxc_guest` `baseline`, then `lxc_semaphore` `bake` |
| Consumed by | `inventory/group_vars/all/semaphore.yml` (`lxc_semaphore_template_checksum`), `inventory/secrets/semaphore.yml`, `playbooks/deploy-semaphore.yml` |

To raise the Semaphore version: change `lxc_semaphore_version` and `lxc_semaphore_package_checksum` here (the `.deb`'s line in the
release's `semaphore_<version>_checksums.txt`), open a PR (the workflow bakes it), tag `semaphore/v<new>`, then pin the new release's
URL and `sha256:` in the inventory.
