# 05 — Velociraptor DFIR server

Run [Velociraptor](https://docs.velociraptor.app/) — the endpoint-visibility and digital-forensics collection platform — in a hardened Debian
LXC, so the lab has a DFIR server to enrol clients against, hunt across them and collect artifacts, reached from a browser and the client
frontend instead of a shell on the node.

Velociraptor runs **natively in a hardened Debian LXC under `systemd`** — no Docker, no OCI runtime, no SSH. The template bake unpacks the
official release binary (verified against the sha256 of its release asset) to `/usr/local/bin/velociraptor`, as the unprivileged
`velociraptor` user, with its datastore under `/var/lib/velociraptor`. The result is the released `velociraptor` template
([`templates/velociraptor`](../../templates/velociraptor/README.md)); the node creates the CT from it and does nothing but open the service
ports in the in-guest firewall, generate the configuration, create the administrator and start the unit.

## Moving parts

| Piece | What it is |
| --- | --- |
| `templates/velociraptor` + `.github/workflows/templates.yml` | The released template: Debian 13 with the binary, the service user, the unit and the baseline baked in; published as the `velociraptor/v<version>` GitHub Release ([build-a-template.md](build-a-template.md)). |
| `lxc_guest` role | Fetches the released template into the node's cache by its pinned checksum, creates the CT from it (unprivileged, ownership-marked), reaches it over `pct exec`, re-asserts the baseline inside it. |
| `lxc_velociraptor` role + `deploy-velociraptor.yml` | `bake` is what the template carries; `container` hands the placement to `lxc_guest`; `server` opens the firewall, generates `server.config.yaml`, creates the administrator and starts the baked `velociraptor` unit inside the CT. |
| `inventory/group_vars/all/velociraptor.yml` | The placement: node, CT id, `net0`, the public hostname, the released template's checksum. |
| `inventory/secrets/velociraptor.yml` (vaulted) | The GUI administrator's initial password. |

## Prerequisites (node side)

- The site configuration in place: `make config`, then replace every `CHANGE-ME` in `inventory/hosts.yml`,
  `inventory/group_vars/all/lxc.yml` and `inventory/group_vars/all/velociraptor.yml` (node names, rootfs storage, the CT id, the public
  hostname). The repository carries only the template, `inventory/example/`; your copies are untracked.
- The released template's checksum pinned in your `inventory/group_vars/all/velociraptor.yml` (`lxc_velociraptor_template_checksum`, from the
  `.sha256` asset of the `velociraptor/v<version>` release). The play fetches the template into the node's cache itself; nothing is
  downloaded without the pin. Verify the release first if you want to: [build-a-template.md §5](build-a-template.md#5-verifying-a-release-by-hand).
- The node can reach `github.com` to fetch the release asset once (or place the file in `/var/lib/vz/template/cache/` yourself).
- An admin PVE API credential in the environment (`PROXMOX_TOKEN_ID` + `PROXMOX_TOKEN_SECRET`, or `PROXMOX_PASSWORD`).
- The collection installed where the play runs: `ansible-galaxy collection install -r requirements.yml` (the play runs **on the node**, as
  root).

## Step 1 — Fill in the vaulted secrets file

The file is not in the repository: write it yourself with the administrator's login and initial password, and encrypt it.

```bash
cd inventory/secrets
cat > velociraptor.yml <<'YAML'
---
lxc_velociraptor_admin_user: admin
lxc_velociraptor_admin_password: "<the administrator's initial password>"
YAML
ansible-vault encrypt velociraptor.yml
```

The administrator is created once, when absent; its password is managed in the GUI afterwards and never rewritten by the role.

## Step 2 — Deploy the Velociraptor LXC

The placement — node, CT id, `net0`, the public hostname — is your `inventory/group_vars/all/velociraptor.yml`; the secrets file is the only
input left for the command line. The CT lands on the `lxc_hosts` node running Velociraptor `0.77.3` (`amd64`).

Run it **on the node** that will host the CT:

```bash
export PROXMOX_TOKEN_ID='root@pam!ansible' PROXMOX_TOKEN_SECRET='…'
ansible-playbook playbooks/deploy-velociraptor.yml -e @inventory/secrets/velociraptor.yml --ask-vault-pass
```

The play fetches the released template into the cache if it is not there, creates the LXC from it, re-asserts the baseline, writes the
in-guest firewall drop-in, generates `/etc/velociraptor/server.config.yaml` (once — the self-signed CA stays stable across re-runs), creates
the administrator when absent, starts the baked `systemd` unit, and verifies the GUI answers inside the CT. Re-running it is idempotent
(`changed=0`).

## Step 3 — Sign in and enrol clients

Open `https://<lxc-ip>:8889` (the GUI; self-signed, so accept the browser warning) and sign in with the administrator from the secrets file.
From there, Velociraptor's own [documentation](https://docs.velociraptor.app/docs/) takes over: build a client package from
**Server Artifacts → Server.Utils.CreateMSI** (or the Linux/macOS equivalents), point its `server_urls` at
`https://<public-hostname>:8000/`, and deploy it to the endpoints you want to collect from. The client frontend listens on `8000`; the GUI
on `8889`; the gRPC API (`8001`) and the monitoring listener (`8003`) stay on loopback.

## Verify

- From the node: `pct exec <vmid> -- systemctl status velociraptor` is active, and
  `pct exec <vmid> -- curl -sk https://127.0.0.1:8889/app/index.html -o /dev/null -w '%{http_code}\n' -u admin:<password>` returns `200`.
  (There is no SSH into the CT: `pct exec` is the way in.)
- The in-guest firewall is default-deny inbound: `pct exec <vmid> -- nft list chain inet filter input` shows the GUI (`8889`) and the
  frontend (`8000`) accepted and nothing else, and the API (`8001`) and monitoring (`8003`) ports answer only on loopback.
- Re-running the deploy play is idempotent (`changed=0`).

## Tear down

```bash
ansible-playbook playbooks/deploy-velociraptor.yml --tags destroy -e lxc_guest_confirm_destroy=true
```

`lxc_guest` refuses without the confirmation, refuses a CT that does not carry its marker, and refuses one whose hostname is not
`velociraptor`. The datastore — the enrolled clients, the hunts and the collected files — goes with the container; back it up first if you
need it (`pct exec <vmid> -- tar -C /var/lib/velociraptor -czf - . > velociraptor-datastore.tgz`).

## How it works and what to know

- **Native, not containerised.** The release ships one Go binary; the bake unpacks it, adds the service user and a sandboxed `systemd` unit,
  and nothing else. The runtime is what the upstream server binary is, minus the installer.
- **Generated once, kept.** `server` runs `velociraptor config generate` only when `/etc/velociraptor/server.config.yaml` is absent, merging
  the site ports, bind addresses and public URL in at generation time. The self-signed CA that every enrolled client pins is therefore
  stable across re-runs — regenerating it would orphan every client, so the role never does.
- **Reachability is the firewall, not the bind address.** The GUI and frontend bind every interface inside the CT; the in-guest `nftables`
  firewall (the baseline's default-deny plus this role's `/etc/nftables.d/10-velociraptor.nft`) is what limits inbound to `8889` and `8000`.
  The API and monitoring listeners bind loopback as well. Nothing on the Proxmox host or cluster firewall is touched.
- **Least privilege.** The unit drops all capabilities, runs `NoNewPrivileges` with `ProtectSystem=strict` and only the datastore writable,
  and is filtered to `@system-service` (filtered syscalls soft-fail with `EPERM`, so Velociraptor's optional `bpf` probe degrades gracefully instead
  of being killed) — the nesting AppArmor profile the guest needs to boot is offset by the sandbox (premise rule 11).
- **Secrets hygiene.** `server.config.yaml` is `0640` root-owned, readable by the service user; it carries the CA private key, so the tasks
  that generate and write it, and the one that creates the administrator, are `no_log`. The initial password lives only in the vaulted
  `velociraptor.yml`.
- **Upgrade.** Raise `lxc_velociraptor_version` and `lxc_velociraptor_binary_checksum` in `templates/velociraptor/template.yml` (the sha256
  of the new release's `velociraptor-v<new>-linux-amd64.gz`) and raise `lxc_template_version`, publish it with the Templates workflow
  (`velociraptor/v<new>`), pin the new template checksum, and recreate the CT from the new release
  (`--tags destroy -e lxc_guest_confirm_destroy=true`, then the play). Back the datastore up first and restore it into the new CT before the
  play if you want the clients and hunts to carry over.
