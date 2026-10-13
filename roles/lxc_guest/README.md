# lxc_guest

The one lifecycle every container in this collection goes through, and the single place the hardened premise
([`docs/01-Hardened-LXC-Premise.md`](../../docs/01-Hardened-LXC-Premise.md)) is enforced. A service role never calls `pct`, `pvesh` or
`community.proxmox.proxmox` itself: it hands its placement to this role (host side), runs its own tasks inside the guest after this role's
`baseline` (guest side), and the boundary check (`scripts/check_lxc_boundary.py`) refuses anything else.

- **Privilege:** host-side entry points run as root on the Proxmox node (`pct`/`pvesh` are node-local); `baseline` runs as root inside the
  guest over `community.proxmox.proxmox_pct_remote` (`pct exec`).
- **Collections:** `community.proxmox` (`proxmox` for create/destroy, the `proxmox_pct_remote` connection) and `ansible.builtin`.
- **Idempotent:** yes. The CT is `state: present` with `update: true` (community.proxmox ≥ 1.0 semantics, pinned explicitly): an absent CT
  is created, an existing one has its config (description, cores, memory, features, net0, onboot, …) reconciled, and a settled one is
  `changed=0`; `baseline` is `changed=0` on a settled guest. `unprivileged` cannot change on an existing CT, so `postcheck` asserts it.
- **Platforms:** Debian (bookworm, trixie) CT on **Proxmox VE**. **Min ansible:** 2.19.

## Entry points

| `tasks_from` | Where it runs | Writes? | What it does |
| --- | --- | --- | --- |
| `main` | node | yes | facts → preflight → create (+ start, connect) → postcheck: the ensure path |
| `facts` | node | no | node name, `pct`, the template on its storage, the bridge, the CT id's status/config/ownership, the id elsewhere in the cluster |
| `preflight` | node | no | every precondition below; refuses a privileged request outright |
| `create` | node | **yes** | `community.proxmox.proxmox` create-or-reconcile (`update: true`), `pct start`, then `connect` |
| `connect` | node | no | asserts the CT is running, waits for its init and boot, `add_host`s it into `lxc_guest_group` over `proxmox_pct_remote` |
| `postcheck` | node | no | re-reads the config through `pvesh` and asserts ownership, hostname, unprivileged, bridge, features, onboot |
| `baseline` | **guest** | yes | purges `openssh-server`, refuses an SSH daemon or container runtime, writes the baseline marker |
| `remove` | node | **yes** | opt-in destroy: refuses without `lxc_guest_confirm_destroy`, refuses a CT without our marker or with another hostname |

## What preflight refuses

- a missing node, a zero CT id, an empty hostname, a template that is not `storage:vztmpl/<file>`, a `net0` without `bridge=`;
- `lxc_guest_unprivileged` overridden to `false` (it is a `vars/` constant; an extra-var can still override it, which is exactly the override
  this assertion exists to catch);
- no `pct` on this host, or a play executing on a node other than `lxc_guest_node` (`pct` is node-local, so every other check would have been
  made against the wrong node);
- a template storage that cannot be listed, or a template that is not on it (nothing here downloads one);
- a bridge that has no interface on this node (a CT on a nonexistent bridge boots looking healthy with no network);
- a CT id that exists without this collection's ownership marker, or that is held by a guest on another node.

Ownership is read through `pvesh --output-format json`, never `pct config`, which URL-encodes the description so a marker containing `:` can
never match. A container this collection inherited (the 1Password Connect CT created by `get_sybers.cluster` before the move) is adopted once
with the `pct set … --description` command the refusal prints.

## Inputs (selected — full list in `meta/argument_specs.yml`)

| Variable | Default | Description |
| --- | --- | --- |
| `lxc_guest_node` | `{{ lxc_node }}` | Proxmox node the CT is created on; the play must run on it. |
| `lxc_guest_vmid` | `0` (refused) | CT id. |
| `lxc_guest_hostname` | `""` (refused) | Hostname of the CT; also its name in the play inventory. |
| `lxc_guest_purpose` | `""` | Free text appended to the description after the marker. |
| `lxc_guest_template` | `{{ lxc_template }}` | `storage:vztmpl/<file>`. |
| `lxc_guest_storage` | `{{ lxc_storage }}` | Rootfs storage (the shared Ceph pool for HA). |
| `lxc_guest_net0` | DHCP on `{{ lxc_bridge }}` | Full Proxmox `net0`; must carry `bridge=`. |
| `lxc_guest_features` | `[]` | e.g. `["nesting=1"]` — Debian 13's systemd 257 needs it; the CT stays unprivileged. |
| `lxc_guest_group` | `lxc_guests` | Play-inventory group `connect` adds the CT to. |
| `lxc_guest_baseline_marker` | `{{ lxc_baseline_marker_path }}` | Marker path inside the guest; service roles assert it. |
| `lxc_guest_confirm_destroy` | `false` | `remove` refuses without it. |

The collection variables (`lxc_node`, `lxc_template`, `lxc_storage`, `lxc_bridge`, `lxc_baseline_marker_path`) are defined once in
[`inventory/group_vars/all/lxc.yml`](../../inventory/group_vars/all/lxc.yml). The constants of the premise — the marker text, `unprivileged`,
the purge list and the forbidden binaries — live in `vars/main.yml` and are not inputs.

## Dependencies

None declared. PVE API auth for the `community.proxmox.proxmox` tasks is supplied by the playbook through the
`group/community.proxmox.proxmox` module-defaults group reading the documented `PROXMOX_*` environment variables
([`inventory/group_vars/all/proxmox_api.yml`](../../inventory/group_vars/all/proxmox_api.yml)).

## Usage

A service role wraps the host-side entry points with its own placement (see `lxc_onepassword_connect`'s `container.yml` and `remove.yml`);
the play sequences node side, baseline, service:

```yaml
- name: Create the guest on the node
  hosts: localhost
  connection: local
  gather_facts: false
  module_defaults:
    group/community.proxmox.proxmox:
      api_host: "{{ pve_api_host }}"
      # … PROXMOX_* as in inventory/group_vars/all/proxmox_api.yml …
  tasks:
    - ansible.builtin.include_role:
        name: get_sybers.lxc.lxc_preflight
    - ansible.builtin.include_role:
        name: get_sybers.lxc.lxc_onepassword_connect
        tasks_from: container        # -> lxc_guest with the Connect placement

- name: Harden the guest baseline
  hosts: onepassword_connect
  gather_facts: false
  tasks:
    - ansible.builtin.include_role:
        name: get_sybers.lxc.lxc_guest
        tasks_from: baseline

- name: Configure the service
  hosts: onepassword_connect
  gather_facts: false
  tasks:
    - ansible.builtin.include_role:
        name: get_sybers.lxc.lxc_onepassword_connect
        tasks_from: server           # asserts the baseline marker first
```

## Testing

- `default` (positive, hermetic): `prepare` installs `openssh-server` into the Debian substrate, `converge` runs `baseline`, `verify` asserts
  `sshd` is gone and the marker says `baseline=1`; the idempotence step proves a second run is `changed=0`.
- `guest_negative`: the ensure path off a Proxmox node stops at the `pct` preflight assertion, never in the `proxmox` module.

Everything that needs a real node (`create`, `connect`, `postcheck`, `remove`) is exercised by the plays against a live node, not faked.
