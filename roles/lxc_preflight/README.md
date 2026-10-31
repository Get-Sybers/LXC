# lxc_preflight

The admission gate every node-side play in this collection includes **first**, and the node's fact-finder. The gate (`main`) proves three
things before any container work runs: the play is executing as root, the host is a Proxmox VE node (`/etc/pve` present, and the host appears
in `pvecm nodes` or in the `lxc_preflight_cluster_group` inventory group), and `/usr/sbin/pct` exists. The fact-finder (`facts`, then
`record`) reads what the desired-state files need to know about the node and writes it to the inventory's As-Is record,
`group_vars/all/default.yml`, which `lxc.yml` and the placement files point at. Nothing here reads a credential; the only write is that
inventory file on the controller.

- **Privilege:** runs as **root** — the first check asserts effective uid 0. `pct` and `pvesh` are root-only; there is no sudo/become path.
- **Host:** a Proxmox VE node.
- **Collections:** `ansible.builtin` only.
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.

## Entry points

| `tasks_from` | Where it runs | Writes? | What it does |
| --- | --- | --- | --- |
| `main` | node | no | the admission gate: root, `/etc/pve`, `pct`, the host is a known node |
| `facts` | node | no | after `main`: the node's name and cluster, the management network, the bridges, the storages that hold container rootfs and templates, the cached templates, the guest ids in use and the next free one; sets `lxc_preflight_facts` |
| `record` | controller | **yes** | renders `lxc_preflight_facts` to `<inventory>/group_vars/all/default.yml` (in place, the default) or to `<inventory>/discovered/group_vars/all/default.yml` (a proposal Ansible never loads) |

[`playbooks/preflight.yml`](../../playbooks/preflight.yml) runs the three in order and then lists every `CHANGE-ME` still left in the
desired-state files, which is the whole remaining to-do before a deploy play.

## The record

`group_vars/all/default.yml` holds one mapping, `lxc_site`, and nothing else is written there:

| Key | Source | Read by |
| --- | --- | --- |
| `node` | the gate's platform facts | `lxc_node` (lxc.yml): the node every container lands on |
| `pve_version` | `pvesh get /version` | the report |
| `cluster.name`, `cluster.nodes[]` | `pvesh get /cluster/status` | the report (a standalone node has `name: null`) |
| `management.interface`, `.address`, `.prefix`, `.cidr`, `.gateway`, `.nameservers[]`, `.search[]` | the `network` and `dns` facts (the interface carrying the default route) | `lxc_bridge` (lxc.yml); a static guest address is chosen from this LAN |
| `bridges[]` | `ip -j link show type bridge` | the report |
| `storage.rootdir[]` (`name`, `type`, `shared`; by name, free space left out so the record settles), `storage.rootdir_default` | `pvesh get /nodes/<node>/storage --content rootdir --enabled 1`, `lxc_preflight_storage_preference` | `lxc_storage` (lxc.yml) |
| `storage.vztmpl[]`, `storage.templates_cached[]` | `--content vztmpl`, each storage's content | the report |
| `vmids.in_use[]`, `vmids.next_free` | `pvesh get /cluster/resources --type vm`, `/cluster/nextid` | choosing a placement file's CT id |

The record is As-Is: a fact about the node, re-read by every run of the play, never edited by hand. A choice (another storage, another
bridge) is made in `lxc.yml`, the desired state, which overrides the record's default. `make config` copies the committed skeleton
([`inventory/example/group_vars/all/default.yml`](../../inventory/example/group_vars/all/default.yml)) into place so the keys exist before the
first preflight run; the live record is untracked like the rest of the site configuration.

## Inputs

| Variable | Entry point | Default | Description |
| --- | --- | --- | --- |
| `lxc_preflight_delegate_to` | all | `{{ inventory_hostname }}` | The host every check and read executes on; a caller that delegates its own work passes the same value. |
| `lxc_preflight_cluster_group` | `main` | `proxmox_nodes` | Inventory group of the Proxmox nodes; membership admits a host `pvecm nodes` does not list (a standalone node). |
| `lxc_preflight_storage_preference` | `facts` | `[local-zfs, local-lvm, local]` | Storage names preferred, in order, as the default rootfs storage when the node holds more than one that takes containers; else the first local one, else the first. |
| `lxc_preflight_inventory_dir` | `record` | `{{ inventory_dir }}` | Inventory directory the record is written under. |
| `lxc_preflight_write` | `record` | `in_place` | `in_place` writes `group_vars/all/default.yml`; `additional` writes the proposal under `discovered/`. |
| `lxc_preflight_record_delegate_to` | `record` | `localhost` | The host holding the inventory checkout. |
| `lxc_preflight_record_owner`, `_group` | `record` | `""` | Identity the record carries; empty means the user running Ansible on the delegate. |
| `lxc_preflight_record_backup` | `record` | `false` | Timestamped backup beside a record rewritten in place. |

## Dependencies

None. Composition is explicit at the point of need.

## Usage

```yaml
- name: Create a container on the node
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Admission gate — root, PVE node, pct
      ansible.builtin.include_role:
        name: get_sybers.lxc.lxc_preflight
```

```sh
ansible-playbook playbooks/preflight.yml                                    # gate, facts, the record in place, the CHANGE-ME list
ansible-playbook playbooks/preflight.yml --check --diff                     # what the record would change, nothing written
ansible-playbook playbooks/preflight.yml -e lxc_preflight_write=additional  # a proposal under inventory/discovered/
```

## Behaviour

`main` and `facts` are read-only: every step is a `stat`, a `setup` subset, a `command` with `changed_when: false`, or an assertion, so they
are `changed=0` on every run and safe under `--check` (the checks still run, so a dry run gates meaningfully). `record` writes one file
with `template`, so it is `changed=0` once the record matches the node and honours `--check --diff`. Molecule: `preflight_negative`
proves the gate stops at the PVE-node assertion on a host that is not a node; `preflight_facts_negative` proves `facts` refuses to run
before the gate; `preflight_record` renders the record from a committed fixture, proves the keys and the idempotence of a second run.
