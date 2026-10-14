# 04 — Semaphore UI

Run [Semaphore UI](https://semaphoreui.com/) — the web UI and API for Ansible, Terraform and OpenTofu — in a hardened Debian LXC, so the
lab's playbooks are driven from a browser and an API instead of a shell on the node.

Semaphore runs **natively in a hardened Debian LXC under `systemd`** — no Docker, no OCI runtime, no SSH. The template bake installs the
official Debian package (verified against the checksum the release publishes) beside the tools its tasks shell out to, as the unprivileged
`semaphore` user, on SQLite. The result is the released `semaphore` template ([`templates/semaphore`](../../templates/semaphore/README.md));
the node creates the CT from it and does nothing but write the configuration, migrate the database, create the administrator and start
the unit.

## Moving parts

| Piece | What it is |
| --- | --- |
| `templates/semaphore` + `.github/workflows/templates.yml` | The released template: Debian 13 with the package, the tools, the service user, the unit and the baseline baked in; published as the `semaphore/v<version>` GitHub Release ([build-a-template.md](build-a-template.md)). |
| `lxc_guest` role | Fetches the released template into the node's cache by its pinned checksum, creates the CT from it (unprivileged, ownership-marked), reaches it over `pct exec`, re-asserts the baseline inside it. |
| `lxc_semaphore` role + `deploy-semaphore.yml` | `bake` is what the template carries; `container` hands the placement to `lxc_guest`; `server` writes `config.json`, migrates, creates the administrator and starts the baked `semaphore` unit inside the CT. |
| `inventory/group_vars/all/semaphore.yml` | The placement: node, CT id, `net0`, the external URL, the released template's checksum. |
| `inventory/secrets/semaphore.yml` (vaulted) | The administrator's initial password and the three keys (cookie signing, cookie encryption, access-key encryption). |

## Prerequisites (node side)

- The site configuration in place: `make config`, then replace every `CHANGE-ME` in `inventory/hosts.yml`,
  `inventory/group_vars/all/lxc.yml` and `inventory/group_vars/all/semaphore.yml` (node names, rootfs storage, the CT id). The
  repository carries only the template, `inventory/example/`; your copies are untracked.
- The released template's checksum pinned in your `inventory/group_vars/all/semaphore.yml` (`lxc_semaphore_template_checksum`, from the
  `.sha256` asset of the `semaphore/v<version>` release). The play fetches the template into the node's cache itself; nothing is
  downloaded without the pin. Verify the release first if you want to: [build-a-template.md §5](build-a-template.md#5-verifying-a-release-by-hand).
- The node can reach `github.com` to fetch the release asset once (or place the file in `/var/lib/vz/template/cache/` yourself).
- An admin PVE API credential in the environment (`PROXMOX_TOKEN_ID` + `PROXMOX_TOKEN_SECRET`, or `PROXMOX_PASSWORD`).
- The collection installed where the play runs: `ansible-galaxy collection install -r requirements.yml` (the play runs **on the node**, as
  root).

## Step 1 — Fill in the vaulted secrets file

The file is not in the repository, not even as a template: write it yourself with the seven variables below, one fresh key per
`head -c32 /dev/urandom | base64`, and encrypt it.

```bash
cd inventory/secrets
cat > semaphore.yml <<EOF
---
lxc_semaphore_admin_login: admin
lxc_semaphore_admin_name: "Semaphore Admin"
lxc_semaphore_admin_email: "<the administrator's email>"
lxc_semaphore_admin_password: "<the administrator's initial password>"
lxc_semaphore_cookie_hash: "$(head -c32 /dev/urandom | base64)"
lxc_semaphore_cookie_encryption: "$(head -c32 /dev/urandom | base64)"
lxc_semaphore_access_key_encryption: "$(head -c32 /dev/urandom | base64)"
EOF
ansible-vault encrypt semaphore.yml
```

`lxc_semaphore_access_key_encryption` encrypts every access key (SSH keys, passwords, tokens) Semaphore stores: changing it after first use
makes every stored key unreadable, so keep the vaulted file.

## Step 2 — Deploy the Semaphore LXC

The placement — node, CT id, `net0`, the external URL — is your `inventory/group_vars/all/semaphore.yml`; the secrets file is the only
input left for the command line. The CT lands on the `lxc_hosts` node running Semaphore `2.19.16` (`amd64`).

Run it **on the node** that will host the CT:

```bash
export PROXMOX_TOKEN_ID='root@pam!ansible' PROXMOX_TOKEN_SECRET='…'
ansible-playbook playbooks/deploy-semaphore.yml -e @inventory/secrets/semaphore.yml --ask-vault-pass
```

The play fetches the released template into the cache if it is not there, creates the LXC from it, re-asserts the baseline, writes
`/etc/semaphore/config.json`, runs `semaphore migrate`, creates the administrator when absent, starts the baked `systemd` unit, and
verifies `http://127.0.0.1:3000/api/ping` inside the CT. Re-running it is idempotent (`changed=0`).

## Step 3 — Sign in

Open `http://<lxc-ip>:3000` (or the `lxc_semaphore_web_host` URL behind your reverse proxy) and sign in with the administrator from the
secrets file. From there, Semaphore's own [documentation](https://docs.semaphoreui.com/) takes over: a project, a key store entry, a
repository, an inventory, a task template. Change the administrator's password in the UI if you want to; the role never rewrites it.

## Verify

- From the node: `pct exec <vmid> -- systemctl status semaphore` is active, and `curl -s http://<lxc-ip>:3000/api/ping` returns `pong`.
  (There is no SSH into the CT: `pct exec` is the way in.)
- Re-running the deploy play is idempotent (`changed=0`).

## Tear down

```bash
ansible-playbook playbooks/deploy-semaphore.yml --tags destroy -e lxc_guest_confirm_destroy=true
```

`lxc_guest` refuses without the confirmation, refuses a CT that does not carry its marker, and refuses one whose hostname is not
`semaphore`. The database — projects, task logs, stored keys — goes with the container; back it up first if you need it
(`pct exec <vmid> -- cat /var/lib/semaphore/database.sqlite > semaphore.sqlite`).

## How it works and what to know

- **Native, not containerised.** The release's `.deb` carries the `semaphore` binary only (it depends on `git` and suggests `ansible`), with
  no unit, user or configuration; the bake adds all three and the tools a play needs to reach its hosts. The runtime is what the upstream
  server image runs, minus the image.
- **SQLite, not BoltDB.** Semaphore 2.19 dropped BoltDB; the database is `/var/lib/semaphore/database.sqlite`, owned by the service user.
  A larger deployment can point `lxc_semaphore_extra_config` at MySQL or PostgreSQL (`dialect` and the matching block) — the keys are
  deep-merged over the ones the role writes.
- **Reaching the hosts.** A task reaches its inventory over SSH **out** of the CT (the client is baked in); the CT itself still has no SSH
  daemon. Keys go into Semaphore's key store, encrypted with `lxc_semaphore_access_key_encryption`; nothing is placed in the guest by hand.
- **Secrets hygiene.** `config.json` is `0640` root-owned, readable by the service user; the tasks that assemble and write it, and the one
  that creates the administrator, are `no_log`. The initial password lives only in the vaulted `semaphore.yml`.
- **Upgrade.** Raise `lxc_semaphore_version` and `lxc_semaphore_package_checksum` in `templates/semaphore/template.yml` (the `.deb`'s line
  in the release's `checksums.txt`), publish it with the Templates workflow (`semaphore/v<new>`), pin the new template checksum, and recreate the CT from the new release
  (`--tags destroy -e lxc_guest_confirm_destroy=true`, then the play). Back the database up first, or restore it into the new CT before the
  play: `server` migrates whatever database it finds.
