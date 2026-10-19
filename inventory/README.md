# inventory/ — the single config home

Everything site-specific the `get_sybers.lxc` plays and roles consume lives in this directory and nowhere else: no play carries a `vars:`
block, no role default names a host, a storage, a CT id or an address. `ansible.cfg` points here, so a play needs no `-i`.

The repository keeps only the **template** of that configuration, `inventory/example/`. The real files are created from it by
`make config` and are untracked (`.gitignore`), so a node name, a subnet or a CT id never enters version control:

```text
inventory/
├── README.md
├── example/                       # the template — the only configuration the repository carries
│   ├── hosts.yml                  #   the Proxmox nodes, which of them hosts the containers, the declared localhost
│   └── group_vars/all/
│       ├── lxc.yml                #   the collection variables: lxc_node, lxc_storage, lxc_bridge, templates, markers
│       ├── proxmox_api.yml        #   admin PVE API credential (read from PROXMOX_* env vars, never stored)
│       ├── onepassword.yml        #   1Password Connect LXC placement (secrets stay in secrets/)
│       ├── distrobuilder.yml      #   distrobuilder build-box LXC placement and image definitions
│       ├── semaphore.yml          #   Semaphore UI LXC placement (secrets stay in secrets/)
│       └── velociraptor.yml       #   Velociraptor DFIR server LXC placement (secrets stay in secrets/)
├── hosts.yml                      # untracked — your copy
├── group_vars/all/*.yml           # untracked — your copies
└── secrets/                       # vaulted -e files (see secrets/README.md); never loaded as inventory
```

## First run

```sh
make config                        # copies example/ into place without overwriting what is already there
$EDITOR inventory/hosts.yml inventory/group_vars/all/lxc.yml inventory/group_vars/all/onepassword.yml inventory/group_vars/all/semaphore.yml inventory/group_vars/all/distrobuilder.yml inventory/group_vars/all/velociraptor.yml
```

Replace every `CHANGE-ME`: the node names, the rootfs storage, the CT id, and the released template's checksum. `ansible.cfg` ignores
`example/` and `secrets/` as inventory sources, so the template is never loaded by mistake.

## Groups

| Group | Members | Meaning |
| --- | --- | --- |
| `proxmox_nodes` | every PVE node | `lxc_preflight` admits a host in this group even before `pvecm nodes` lists it |
| `lxc_hosts` | the node that hosts the containers | `lxc_node` is its first member; membership *is* the declaration |
| `controller` | `localhost` | the node-side plays (run on the node) and the API-client plays; declared so they receive `group_vars/all` |

## Adding a container

1. Add its role's placement file to `example/group_vars/all/<service>.yml` (the template, with `CHANGE-ME` placeholders) and copy it
   into your `group_vars/all/`.
2. Nothing else: the node, template, storage and bridge come from `lxc.yml` unless the service overrides them.
