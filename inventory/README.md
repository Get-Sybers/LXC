# inventory/ — the single config home

Everything site-specific the `get_sybers.lxc` plays and roles consume lives in this directory and nowhere else: no play carries a `vars:`
block, no role default names a host, a storage, a CT id or an address. `ansible.cfg` points here, so a play needs no `-i`.

The repository keeps only the **template** of that configuration, `inventory/example/`. The real files are created from it by
`make config` and are untracked (`.gitignore`), so a node name, a subnet or a CT id never enters version control:

```text
inventory/
├── README.md
├── example/                       # the template — the only configuration the repository carries
│   ├── hosts.yml                  #   the declared localhost (and a standalone node, if any); no node names to type
│   └── group_vars/all/
│       ├── default.yml            #   As-Is skeleton — FILLED BY playbooks/preflight.yml: the node, its cluster, LAN, bridges, storages, guest ids
│       ├── lxc.yml                #   the collection variables: lxc_node, lxc_storage, lxc_bridge (pointing at default.yml), templates, markers
│       ├── proxmox_api.yml        #   admin PVE API credential (read from PROXMOX_* env vars, never stored)
│       ├── onepassword.yml        #   1Password Connect LXC placement (secrets stay in secrets/)
│       ├── distrobuilder.yml      #   distrobuilder build-box LXC placement and image definitions
│       ├── semaphore.yml          #   Semaphore UI LXC placement (secrets stay in secrets/)
│       ├── velociraptor.yml       #   Velociraptor DFIR server LXC placement (secrets stay in secrets/)
│       └── ghost9.yml             #   GHOSTS (ghost9) server LXC placement (secrets stay in secrets/)
├── hosts.yml                      # untracked — your copy
├── group_vars/all/*.yml           # untracked — your copies; default.yml is rewritten by preflight.yml
├── discovered/                    # untracked — the proposal preflight.yml writes with -e lxc_preflight_write=additional; never loaded
└── secrets/                       # vaulted -e files (see secrets/README.md); never loaded as inventory
```

## First run

```sh
make config                                # copies example/ into place without overwriting what is already there
ansible-playbook playbooks/preflight.yml   # on the node: gate, read its facts, fill group_vars/all/default.yml, list what is left
$EDITOR inventory/group_vars/all/onepassword.yml   # the CT id of each container you deploy (preflight prints the ids in use and the next free one)
```

The preflight play fills the node's own values; what is left is each container's `CHANGE-ME` (its CT id), which the play lists. Run it
again after a node change (a new storage, a new bridge, a new cluster member); a second run is `changed=0`. `ansible.cfg` ignores
`example/`, `discovered/` and `secrets/` as inventory sources, so the template and a proposal are never loaded by mistake.

## Groups

| Group | Members | Meaning |
| --- | --- | --- |
| `proxmox_nodes` | empty by default | a clustered node is admitted by `pvecm nodes`; list a standalone node here so `lxc_preflight` admits it |
| `controller` | `localhost` | the node-side plays (run on the node) and the API-client plays; declared so they receive `group_vars/all` |

## As-Is versus desired state

`group_vars/all/default.yml` is **discovered state**, written by [`playbooks/preflight.yml`](../playbooks/preflight.yml): one mapping,
`lxc_site`, with the node's name and cluster, its management network (the interface carrying the default route, address, prefix,
gateway, resolvers), the bridges, the storages that hold container rootfs (and the one proposed as the default) and templates, the
cached templates, and the guest ids in use cluster-wide with the next free one. The template ships it as a skeleton so the keys exist
before the first run. Every other file is **desired state**, written by hand; `lxc.yml` points `lxc_node`, `lxc_storage` and
`lxc_bridge` at the record by default and is where another storage or bridge is chosen. Never edit the record: re-run the play.

```sh
ansible-playbook playbooks/preflight.yml                                    # fill or refresh the record in place
ansible-playbook playbooks/preflight.yml --check --diff                     # what would change, nothing written
ansible-playbook playbooks/preflight.yml -e lxc_preflight_write=additional  # a proposal under discovered/ — diff, then adopt
```

## Adding a container

1. Add its role's placement file to `example/group_vars/all/<service>.yml` (the template, with `CHANGE-ME` placeholders) and copy it
   into your `group_vars/all/`.
2. Nothing else: the node, template, storage and bridge come from `lxc.yml` unless the service overrides them.
