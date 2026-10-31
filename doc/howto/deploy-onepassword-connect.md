# 02 — 1Password Connect

Mirror the lab's authentication credentials (API keys and passwords) into a self-hosted
[1Password Connect](https://developer.1password.com/docs/connect/) server. 1Password is a **mirror only**: the authoritative stores in the
cluster tier (PocketBase and the ZFS file vault, `get-sybers/proxmox`) are left exactly as they are.

The Connect server runs **natively in a hardened Debian LXC under `systemd`** — no Docker, no OCI runtime, no SSH. The `connect-api` and
`connect-sync` images are single Go binaries; the template bake extracts those binaries straight from the pinned official images (via the
Docker registry HTTP API — nothing is installed and nothing runs as a container) and installs each as an `opuser` service, exactly as the
image would. The result is the released `op-connect` template ([`templates/op-connect`](../../templates/op-connect/README.md)); the node
creates the CT from it and does nothing but drop in the credentials and start the units.

## Moving parts

| Piece | What it is |
| --- | --- |
| `templates/op-connect` + `.github/workflows/templates.yml` | The released template: Debian 13 with the Connect binaries, units, service user and the baseline baked in; published as the `op-connect/v<version>` GitHub Release ([build-a-template.md](build-a-template.md)). |
| `lxc_guest` role | Fetches the released template into the node's cache by its pinned checksum, creates the CT from it (unprivileged, ownership-marked), reaches it over `pct exec`, re-asserts the baseline inside it. |
| `lxc_onepassword_connect` role + `deploy-onepassword-connect.yml` | `bake` is what the template carries; `container` hands the placement to `lxc_guest`; `server` installs the credentials and starts the baked `op-connect-api` / `op-connect-sync` units inside the CT. |
| `lxc_onepassword_item` role + `reflect-onepassword-credentials.yml` | Upsert one credential per entry into 1Password via the Connect API (`onepassword.connect.generic_item`). |
| `inventory/secrets/onepassword.yml` (vaulted) | The single source: Connect host/vault-id/token plus the list of items to mirror. |

## Prerequisites (1Password side)

Create a Connect server and an access token — through the 1Password dashboard
(**Developer → Infrastructure Secrets Management → 1Password Connect**) or the `op` CLI:

```bash
op connect server create "<server name>" --vaults "<vault>"
op connect token create reflect --server "<server name>" --vault "<vault>"
```

This gives you three things:

- **`1password-credentials.json`** — the server's credentials file. Copy it to the PVE node that will host the LXC (e.g.
  `/root/1password-credentials.json`, mode `0400`).
- **An access token** — a long string the reflect play uses to write items. Goes into the vaulted secrets file.
- **The vault's ID** — `op vault get "<vault>" --format json | jq -r .id`. Goes into the vaulted secrets file.

> A Connect server cannot see your Personal/Private/Employee vault or the default Shared vault — create a dedicated vault for the mirror.

## Prerequisites (node side)

- The site configuration in place: `make config`, then `ansible-playbook playbooks/preflight.yml` on the node (it gates the node,
  records its storages, bridges, LAN and guest ids in `inventory/group_vars/all/default.yml`, and lists what is left), then the CT id in
  `inventory/group_vars/all/onepassword.yml`. The repository carries only the template, `inventory/example/`; your copies are untracked.

- The template is pulled from `ghcr.io/get-sybers/lxc/op-connect` by the play (Proxmox's OCI support). The package must be **public**, or the node logged in to GHCR (`skopeo login ghcr.io`). To pin an exact image instead of the moving `:v<version>` tag, set `lxc_onepassword_connect_template_image` to `…@sha256:<digest>` in your inventory. Verify the release first if you want to: [build-a-template.md §5](build-a-template.md#5-verifying-a-release-by-hand).
- The node can reach `github.com` to fetch the release asset once (or place the file in `/var/lib/vz/template/cache/` yourself).
- An admin PVE API credential in the environment (`PROXMOX_TOKEN_ID` + `PROXMOX_TOKEN_SECRET`, or `PROXMOX_PASSWORD`).
- The collection installed where the play runs: `ansible-galaxy collection install -r requirements.yml` (the play runs **on the node**, as
  root).

## Step 1 — Deploy the Connect server LXC

The node, its storage and bridge come from the As-Is record the preflight play wrote; the CT id and the credentials file are
run-time inputs, given with `-e` (set `lxc_onepassword_connect_vmid` in `inventory/group_vars/all/onepassword.yml` instead to make an
id the default for this site). The CT lands on that node running Connect `1.8.3` (`amd64`).

Run it **on the node** that will host the CT:

```bash
export PROXMOX_TOKEN_ID='root@pam!ansible' PROXMOX_TOKEN_SECRET='…'
ansible-playbook playbooks/deploy-onepassword-connect.yml \
  -e lxc_onepassword_connect_vmid=<a free CT id> \
  -e lxc_onepassword_connect_credentials_src=/root/1password-credentials.json
```

The preflight play reports the ids in use and the next free one. The play fetches the released template into the cache if it is not there, creates the LXC from it, re-asserts the baseline, installs the
credentials file, starts the two baked `systemd` units, and verifies `http://127.0.0.1:8080/health` inside the CT.

### A container the cluster collection created

If the CT already exists from `get_sybers.cluster`'s `cluster-onepassword-connect.yml` (before the move to this repository), it was built
from the stock Debian template with the binaries installed in place, so it carries neither this collection's ownership marker nor the
template marker, and `server` refuses it. Replace it: destroy it on the node (`pct stop <vmid> && pct destroy <vmid> --purge`) and run the play,
which creates it fresh from the released template. The Connect data directory is rebuilt by `connect-sync` from the credentials file.

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

- From the node: `pct exec <vmid> -- systemctl status op-connect-api op-connect-sync` are active, and `curl -s http://<lxc-ip>:8080/health`
  returns HTTP 200. (There is no SSH into the CT: `pct exec` is the way in.)
- In 1Password: the items appear in the target vault with the expected fields.
- Re-running the reflect play is idempotent (`changed=0`).

## Tear down

```bash
ansible-playbook playbooks/deploy-onepassword-connect.yml --tags destroy -e lxc_guest_confirm_destroy=true
```

`lxc_guest` refuses without the confirmation, refuses a CT that does not carry its marker, and refuses one whose hostname is not `op-connect`.

## How it works and what to know

- **Native, not containerised.** At bake time the role reads each image's config, pulls its layers from the registry, unpacks them, and
  installs `/usr/local/bin/connect-api` and `connect-sync` into the template. Each runs under `systemd` as the unprivileged `opuser`, with
  `SSL_CERT_FILE` pointing at the system CA bundle and the credentials/data under `~/.op` — the same contract the image declares. To
  upgrade: raise `lxc_onepassword_connect_version` in `templates/op-connect/template.yml`, publish it with the Templates workflow
  (`op-connect/v<new>`), pin the new
  checksum, and recreate the CT from the new release (`--tags destroy -e lxc_guest_confirm_destroy=true`, then the play).
- **Secrets hygiene.** The `1password-credentials.json` is installed `0600` owned by `opuser`; the Connect token lives only in the vaulted
  `onepassword.yml`. Every secret-bearing task is `no_log`, and the roles report shape only (sizes, counts), never values.
- **Unofficial topology.** 1Password officially supports Docker-Compose and Kubernetes. Running the binaries bare is equivalent (same
  entrypoint, env, user and paths) but self-supported — if a future image stops being a standalone binary, the premise
  ([`hardened-lxc-premise.md`](../reference/hardened-lxc-premise.md), rule 3) means a new build approach, not a container runtime inside the LXC.
- **Architecture / version.** Default is `amd64` at tag `1.8.3`; set `lxc_onepassword_connect_arch: arm64` on a Pi host, and confirm the
  current tag on Docker Hub before pinning.
