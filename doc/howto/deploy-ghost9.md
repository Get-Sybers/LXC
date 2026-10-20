# 06 — GHOSTS (ghost9) server

Run the [GHOSTS](https://github.com/cmu-sei/GHOSTS) server — CERT/SEI's framework for realistic NPC and user simulation — in a hardened Debian
LXC, so a range has a GHOSTS server to orchestrate simulated users and activity from a browser and an API.

GHOSTS runs **natively in a hardened Debian LXC under `systemd`** — no Docker, no OCI runtime, no SSH. The template bake builds the full
v9.3.0 server stack from the checksum-pinned source and installs it as regular services: PostgreSQL, the .NET 10 API, the Angular UI behind
nginx, n8n and Grafana. The result is the released `ghost9` template ([`templates/ghost9`](../../templates/ghost9/README.md)); the node
creates the CT from it and does only the site-specific rest.

## Moving parts

| Piece | What it is |
| --- | --- |
| `templates/ghost9` + `.github/workflows/templates.yml` | The released template: Debian 13 with the GHOSTS stack built and installed as native services, published as the `ghost9/v<version>` GitHub Release ([build-a-template.md](build-a-template.md)). |
| `lxc_guest` role | Fetches the released template into the node's cache by its pinned checksum, creates the CT (unprivileged, nesting, ownership-marked), reaches it over `pct exec`, re-asserts the baseline. |
| `lxc_ghost9` role + `deploy-ghost9.yml` | `bake` is what the template carries; `container` hands the placement to `lxc_guest`; `server` creates the Postgres role/db, writes the site config, starts all five services, provisions n8n and verifies. |
| `inventory/group_vars/all/ghost9.yml` | The placement: node, CT id, `net0`, the public hostname, the released template's checksum. |
| `inventory/secrets/ghost9.yml` (vaulted) | The PostgreSQL password and the n8n owner account password. |

## Prerequisites (node side)

- `make config`, then replace every `CHANGE-ME` in `inventory/hosts.yml`, `inventory/group_vars/all/lxc.yml` and
  `inventory/group_vars/all/ghost9.yml` (node names, rootfs storage, the CT id, the public hostname).
- The released template's checksum pinned in your `inventory/group_vars/all/ghost9.yml` (`lxc_ghost9_template_checksum`, from the `.sha256`
  asset of the `ghost9/v<version>` release). The play fetches the template into the node's cache itself; nothing is downloaded without the pin.
- The node can reach `github.com` to fetch the release asset once.
- An admin PVE API credential in the environment (`PROXMOX_TOKEN_ID` + `PROXMOX_TOKEN_SECRET`, or `PROXMOX_PASSWORD`).
- The collection installed where the play runs: `ansible-galaxy collection install -r requirements.yml` (the play runs **on the node**, as root).

## Step 1 — Fill in the vaulted secrets file

```bash
cd inventory/secrets
cat > ghost9.yml <<'YAML'
---
lxc_ghost9_db_password: "<a strong PostgreSQL password>"
lxc_ghost9_n8n_owner_email: "admin@ghosts.local"
lxc_ghost9_n8n_owner_password: "<the n8n owner's initial password>"
YAML
ansible-vault encrypt ghost9.yml
```

The DB password backs the API connection string and the Grafana datasource; the n8n owner is created once and managed in n8n afterwards.

## Step 2 — Deploy the GHOSTS LXC

Run it **on the node** that will host the CT:

```bash
export PROXMOX_TOKEN_ID='root@pam!ansible' PROXMOX_TOKEN_SECRET='…'
ansible-playbook playbooks/deploy-ghost9.yml -e @inventory/secrets/ghost9.yml --ask-vault-pass
```

The play fetches the released template if needed, creates the LXC, re-asserts the baseline, opens the in-guest firewall, creates the
PostgreSQL role and database, writes the API environment, the UI runtime config and the Grafana datasource, starts PostgreSQL, n8n, Grafana
and nginx, provisions n8n (owner account, GHOSTS workflows, an API key for the GHOSTS API), starts the API, and verifies the stack. The API's
first start seeds the database (~15-30s). Re-running is idempotent (`changed=0`).

## Step 3 — Sign in

Open `http://<lxc-ip>:4200` for the GHOSTS UI. The API and its Swagger are at `http://<lxc-ip>:5000` (`/swagger`), n8n at
`http://<lxc-ip>:5678` (sign in with the owner account), and Grafana at `http://<lxc-ip>:3000` (anonymous admin). Build client packages and
timelines from the UI; GHOSTS' own [documentation](https://github.com/cmu-sei/GHOSTS) takes over from there.

## Verify

- From the node: `pct exec <vmid> -- systemctl is-system-running` is `running`, and
  `pct exec <vmid> -- curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/test` returns `200` (the API's `/test` does a DB
  round-trip, so it proves the API and PostgreSQL together).
- The in-guest firewall is default-deny inbound: `pct exec <vmid> -- nft list chain inet filter input` shows the UI (`4200`), API (`5000`),
  Grafana (`3000`) and n8n (`5678`) accepted and nothing else; PostgreSQL (`5432`) answers only on loopback.
- Re-running the deploy play is idempotent (`changed=0`).

## Tear down

```bash
ansible-playbook playbooks/deploy-ghost9.yml --tags destroy -e lxc_guest_confirm_destroy=true
```

`lxc_guest` refuses without the confirmation, refuses a CT that does not carry its marker, and refuses one whose hostname is not `ghost9`.
The database, the n8n workflows and the Grafana state go with the container; back them up first if you need them.

## How it works and what to know

- **Native, not containerised.** GHOSTS upstream ships a Docker Compose stack; this template reimplements it as native systemd services so it
  fits the hardened-LXC premise (no container runtime inside a guest). The API runs `dotnet ghosts.api.dll`; the UI is static files on nginx;
  n8n is `n8n start`; PostgreSQL and Grafana are their distro packages.
- **The API builds its own schema.** On first start the API runs `EnsureCreated` and seeds the GHOSTS data (~15-30s); no external migration
  step is needed. The home page shows a DB error until seeding finishes.
- **Reachability is the firewall.** The services bind their ports on all interfaces inside the CT; the in-guest `nftables` firewall is what
  limits inbound to the four service ports. PostgreSQL binds loopback only. Nothing on the Proxmox host or cluster firewall is touched.
- **Secrets hygiene.** The API environment file and the Grafana datasource carry the DB password (`0640`, root/service-group); the tasks that
  write them, and the n8n owner creation, are `no_log`. The passwords live only in the vaulted `ghost9.yml`.
- **Upgrade.** Raise `lxc_ghost9_version` and `lxc_ghost9_source_sha256` in `templates/ghost9/template.yml` and `lxc_template_version`,
  publish it with the Templates workflow (`ghost9/v<new>`), pin the new template checksum, and recreate the CT from the new release.
