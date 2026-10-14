# lxc_preflight

The admission gate every node-side play in this collection includes **first**. It proves three things before any container work runs: the play
is executing as root, the host is a Proxmox VE node (`/etc/pve` present, and the host appears in `pvecm nodes` or in the
`lxc_preflight_cluster_group` inventory group), and `/usr/sbin/pct` exists. It reads no credential and changes nothing.

- **Privilege:** runs as **root** — the first check asserts effective uid 0. `pct` is root-only; there is no sudo/become path.
- **Host:** a Proxmox VE node declared in the inventory.
- **Collections:** `ansible.builtin` only.
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `lxc_preflight_delegate_to` | No | `{{ inventory_hostname }}` | The host every check executes on; a caller that delegates its own work passes the same value. |
| `lxc_preflight_cluster_group` | No | `proxmox_nodes` | Inventory group of the Proxmox nodes; membership admits a host `pvecm nodes` does not list (a single node, or one still joining). |

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

## Behaviour

Read-only. Every step is a `stat`, a `command` with `changed_when: false`, or an assertion, so the role is `changed=0` on every run and safe
under `--check` (the checks still run, so a dry run gates meaningfully). The `preflight_negative` Molecule scenario proves it stops at the
PVE-node assertion on a host that is not a node.
