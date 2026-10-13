# 02 — 1Password Connect

Mirror the lab's authentication credentials (API keys and passwords) into a self-hosted
[1Password Connect](https://developer.1password.com/docs/connect/) server. 1Password is a **mirror only**: the authoritative stores in the
cluster tier (PocketBase and the ZFS file vault, `get-sybers/proxmox`) are left exactly as they are.

The Connect server runs **natively in a hardened Debian LXC under `systemd`** — no Docker, no OCI runtime, no SSH. The `connect-api` and
`connect-sync` images are single Go binaries; the automation extracts those binaries straight from the pinned official images (via the Docker
registry HTTP API — nothing is installed and nothing runs as a container) and runs each as an `opuser` service, exactly as the image would.

## Moving parts

| Piece | What it is |
| --- | --- |
| `lxc_guest` role | Creates the CT (unprivileged, ownership-marked), reaches it over `pct exec`, runs the baseline inside it (no `sshd`, no container runtime). |
| `lxc_onepassword_connect` role + `deploy-onepassword-connect.yml` | Hands the Connect placement to `lxc_guest`, then runs `op-connect-api` / `op-connect-sync` as `systemd` services inside the CT. |
| `lxc_onepassword_item` role + `reflect-onepassword-credentials.yml` | Upsert one credential per entry into 1Password via the Connect API (`onepassword.connect.generic_item`). |
| `inventory/secrets/onepassword.yml` (vaulted) | The single source: Connect host/vault-id/token plus the list of items to mirror. |

## Prerequisites (1Password side)

Create a Connect server and an access token — through the 1Password dashboard
(**Developer → Infrastructure Secrets Management → 1Password Connect**) or the `op` CLI:

```bash
op connect server create "Get-Sybers Cluster" --vaults "Infrastructure"
op connect token create reflect --server "Get-Sybers Cluster" --vault "Infrastructure"
```

This gives you three things:

- **`1password-credentials.json`** — the server's credentials file. Copy it to the PVE node that will host the LXC (e.g.
  `/root/1password-credentials.json`, mode `0400`).
- **An access token** — a long string the reflect play uses to write items. Goes into the vaulted secrets file.
- **The vault's ID** — `op vault get "Infrastructure" --format json | jq -r .id`. Goes into the vaulted secrets file.

> A Connect server cannot see your Personal/Private/Employee vault or the default Shared vault — create a dedicated vault for the mirror.

## Prerequisites (node side)

- The Debian template on the node: `pveam list local | grep debian-13` (fetch with `pveam update && pveam download local <file>`; the
  file name is `lxc_template` in `inventory/group_vars/all/lxc.yml`).
- An admin PVE API credential in the environment (`PROXMOX_TOKEN_ID` + `PROXMOX_TOKEN_SECRET`, or `PROXMOX_PASSWORD`).
- The collection installed where the play runs: `ansible-galaxy collection install -r requirements.yml` (the play runs **on the node**, as
  root).

## Step 1 — Deploy the Connect server LXC

Set the placement inputs for `lxc_onepassword_connect` (in `inventory/group_vars/all/onepassword.yml`, or with `-e`) — at minimum the
`lxc_onepassword_connect_credentials_src` path and, for a fixed address, `lxc_onepassword_connect_net0`. The defaults put the CT on the
`lxc_hosts` node, `vmid` 950, DHCP on `vmbr0`, Connect `1.8.3` (`amd64`).

Run it **on the node** that will host the CT:

```bash
export PROXMOX_TOKEN_ID='root@pam!ansible' PROXMOX_TOKEN_SECRET='…'
ansible-playbook playbooks/deploy-onepassword-connect.yml \
  -e lxc_onepassword_connect_credentials_src=/root/1password-credentials.json \
  -e lxc_onepassword_connect_net0='name=eth0,bridge=vmbr0,ip=192.168.4.150/24,gw=192.168.4.1'
```

The play creates the LXC, strips its SSH server, extracts the binaries, writes the two `systemd` units, starts them, and verifies
`http://127.0.0.1:8080/health` inside the CT.

### Adopting the container the cluster collection created

If CT 950 already exists from `get_sybers.cluster`'s `cluster-onepassword-connect.yml` (before the move to this repository), `lxc_guest`'s
preflight refuses it: its description carries the old marker, not this collection's. Adopt it once, deliberately, on the node:

```bash
pct set 950 --description "Ansible-managed: get_sybers.lxc.lxc_guest | 1Password Connect server (op-connect-api + op-connect-sync)"
```

Then run the play as above: the create is a no-op, the baseline removes the SSH server the standard template shipped with, and `server` is
`changed=0` on an already-settled host.

## Step 2 — Fill in the vaulted secrets file

```bash
cd inventory/secrets
cp onepassword.yml.example onepassword.yml
# edit: set onepassword_host (http://<lxc-ip>:8080), onepassword_vault_id,
#       onepassword_token, and the onepassword_mirror_items list
ansible-vault encrypt onepassword.yml
```

Each entry in `onepassword_mirror_items` becomes one 1Password item, reconciled by `title`. Use `field_type: concealed` for secret values.

## Step 3 — Reflect the credentials

```bash
ansible-playbook playbooks/reflect-onepassword-credentials.yml \
  -e @inventory/secrets/onepassword.yml --ask-vault-pass
```

Re-run any time the credentials change — `generic_item` reconciles by title, so a run with nothing new reports `changed=0`. This play is a
pure API client: it runs wherever it can reach the Connect LXC over HTTP and never touches the node or the container.

## Verify

- From the node: `pct exec 950 -- systemctl status op-connect-api op-connect-sync` are active, and `curl -s http://<lxc-ip>:8080/health`
  returns HTTP 200. (There is no SSH into the CT: `pct exec` is the way in.)
- In 1Password: the items appear in the target vault with the expected fields.
- Re-running the reflect play is idempotent (`changed=0`).

## Tear down

```bash
ansible-playbook playbooks/deploy-onepassword-connect.yml --tags destroy -e lxc_guest_confirm_destroy=true
```

`lxc_guest` refuses without the confirmation, refuses a CT that does not carry its marker, and refuses one whose hostname is not `op-connect`.

## How it works and what to know

- **Native, not containerised.** The role reads each image's config, pulls its layers from the registry, unpacks them, and installs
  `/usr/local/bin/connect-api` and `connect-sync`. Each runs under `systemd` as the unprivileged `opuser`, with `SSL_CERT_FILE` pointing at
  the system CA bundle and the credentials/data under `~/.op` — the same contract the image declares. Extraction is gated by a version
  marker, so a settled host is idempotent; bump `lxc_onepassword_connect_version` to upgrade.
- **Secrets hygiene.** The `1password-credentials.json` is installed `0600` owned by `opuser`; the Connect token lives only in the vaulted
  `onepassword.yml`. Every secret-bearing task is `no_log`, and the roles report shape only (sizes, counts), never values.
- **Unofficial topology.** 1Password officially supports Docker-Compose and Kubernetes. Running the binaries bare is equivalent (same
  entrypoint, env, user and paths) but self-supported — if a future image stops being a standalone binary, the premise
  (`docs/01-Hardened-LXC-Premise.md`, rule 3) means a new build approach, not a container runtime inside the LXC.
- **Architecture / version.** Default is `amd64` at tag `1.8.3`; set `lxc_onepassword_connect_arch: arm64` on a Pi host, and confirm the
  current tag on Docker Hub before pinning.
