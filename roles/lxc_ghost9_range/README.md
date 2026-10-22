The GHOSTS ("ghost9") server of one Ludus range: `lxc_ghost9`'s `container`, `baseline` and `server` entry points placed on the
range's VNet. The CT attaches to `r<N>` with the range's VLAN tag, takes `10.<N>.<vlan>.<octet>/24` with the range router (`.254`)
as gateway and nameserver, carries the bridge's MTU (SDN VXLAN at 1450 on a cluster, 1500 on a single node), is numbered
`<vmid base> + N`, named `r<N>-<suffix>` and placed in the `GHOST9` pool. Before `lxc_ghost9` runs, the role checks what `lxc_guest`
does not: the VNet is declared in `/etc/pve/sdn/vnets.cfg`, its bridge exists on this node, its MTU is readable, and no
Ludus-managed `*-ghosts` VM competes for the address; afterwards it reads the CT config back through the PVE API and asserts
bridge, tag, address, gateway and MTU. The node is reached only through the PVE API and `lxc_guest` (the premise's rule 4).

## Entry points

| `tasks_from` | Runs on | Does |
| --- | --- | --- |
| `container` | the node (`localhost`, root) | the range checks → `lxc_preflight` → `lxc_ghost9` `container` (the OCI image into `local:vztmpl/ghost9.tar`, the CT created and started, added to the range group) → the placement postcheck |
| `baseline` | the CT (the range group) | `lxc_guest` `baseline` with this role's marker path |
| `server` | the CT | the rule-5 baseline assertion, then `lxc_ghost9` `server` with the range address as public hostname, the API port and the template release |
| `remove` | the node | `lxc_ghost9` `remove` on this role's CT; needs `-e lxc_guest_confirm_destroy=true` |

A bare include fails. [`playbooks/deploy_ghost9_range.yml`](../../playbooks/deploy_ghost9_range.yml) drives the four in order; a
consumer runs it by its collection-qualified name with every input in one vars file:

```sh
ansible-playbook get_sybers.lxc.deploy_ghost9_range -e @/root/.ghost9-range.yml
```

## Inputs

Every input is in [`defaults/main.yml`](defaults/main.yml) and typed in [`meta/argument_specs.yml`](meta/argument_specs.yml).
`lxc_ghost9_range_number` (the range's second octet) is required and has no safe default; everything addressable derives from it.

| Input | Default | Meaning |
| --- | --- | --- |
| `lxc_ghost9_range_number` | *(required)* | the range's second octet, from `ludus range list` |
| `lxc_ghost9_range_vlan` | `99` | the VLAN tag and third octet |
| `lxc_ghost9_range_last_octet` | `51` | the CT's last octet (the clients' `ApiRootUrl` carries it) |
| `lxc_ghost9_range_hostname_suffix` | `ghost9` | the CT is `r<N>-<suffix>` |
| `lxc_ghost9_range_vmid_base` | `9000` | CT id = base + N |
| `lxc_ghost9_range_pool` | `GHOST9` | the PVE pool |
| `lxc_ghost9_range_cores` / `_memory_mb` / `_swap_mb` / `_rootfs_gb` | `4` / `6144` / `2048` / `20` | sizing |
| `lxc_ghost9_range_storage` | `local-zfs` | the rootfs storage |
| `lxc_ghost9_range_api_port` | `5000` | the GHOSTS API port the clients report to |
| `lxc_ghost9_range_template_version` | `0.1.1` | this repository's release of the ghost9 template |
| `lxc_ghost9_range_template_registry_base` | `ghcr.io/get-sybers/lxc` | the registry prefix |
| `lxc_ghost9_range_template_image` | `<base>/ghost9:v<version>` | the OCI image; pin `@sha256:<digest>` for an exact image |
| `lxc_ghost9_range_template_release_base` | the GitHub releases URL | `lxc_guest`'s URL fetch base (unused when the image pulls) |
| `lxc_ghost9_range_template_cache_dir` | `/var/lib/vz/template/cache` | the node's template cache |
| `lxc_ghost9_range_baseline_marker_path` / `_template_marker_path` | the two `/etc/get-sybers-lxc-*` markers | the in-guest markers |
| `lxc_ghost9_range_allow_ghosts_vm` | `false` | allow a Ludus `*-ghosts` VM to coexist |
| `lxc_ghost9_range_group` | `ghost9` | the play group the CT joins |
| `lxc_ghost9_range_cluster_group` | `proxmox_nodes` | the group `lxc_preflight` admits a single node from |

The PVE API credential is the collection's `pve_api_*` set (`pve_api_host`, `pve_api_user`, `pve_api_token_id` + `pve_api_token_secret`
or `pve_api_password`, `pve_validate_certs`), and the service secrets are `lxc_ghost9`'s own (`lxc_ghost9_db_password`,
`lxc_ghost9_n8n_owner_email`, `lxc_ghost9_n8n_owner_password`).

## Outcome

A running, unprivileged CT on the range VNet carrying the released ghost9 template, baselined and configured, whose GHOSTS API the
range's clients reach at `http://10.<N>.<vlan>.<octet>:<api port>/api`. Idempotent: `lxc_guest` reconciles the CT config on every run
and `lxc_ghost9`'s server step converges the service configuration. Rollback is the `remove` entry point. The CT is not a Ludus
range object: `ludus range rm` does not remove it and `ludus testing` neither snapshots nor seals it.

## Privilege

Root on the Proxmox node that hosts the Ludus server (`pct`, `/etc/pve` and the OCI pull are node-local), plus a PVE API credential
scoped to the pool, the storage and the SDN zone.
