# inventory/ — the single config home

Everything site-specific the `get_sybers.lxc` plays and roles consume lives in this directory and nowhere else: no play carries a `vars:`
block, no role default names a host, a storage, a bridge or an address. `ansible.cfg` points here, so a play needs no `-i`.

```text
inventory/
├── hosts.yml                      # the Proxmox nodes, which of them hosts the containers, and the declared localhost
├── group_vars/
│   └── all/                       # values every play reads (node-side plays run on localhost = the node)
│       ├── lxc.yml                #   the collection variables: lxc_node, lxc_template, lxc_storage, lxc_bridge, lxc_baseline_marker_path
│       ├── proxmox_api.yml        #   admin PVE API credential (read from PROXMOX_* env vars, never stored)
│       └── onepassword.yml        #   1Password Connect LXC placement (secrets stay in secrets/)
└── secrets/                       # vaulted -e files (see secrets/README.md); never loaded as inventory
```

## Groups

| Group | Members | Meaning |
| --- | --- | --- |
| `proxmox_nodes` | every PVE node | `lxc_preflight` admits a host in this group even before `pvecm nodes` lists it |
| `lxc_hosts` | the node that hosts the containers | `lxc_node` is its first member; membership *is* the declaration |
| `controller` | `localhost` | the node-side plays (run on the node) and the API-client plays; declared so they receive `group_vars/all` |

## Adding a container

1. Write its role's placement in `group_vars/all/<service>.yml` (`lxc_<service>_vmid`, `_net0`, …).
2. Nothing else: the node, template, storage and bridge come from `lxc.yml` unless the service overrides them.
