# `get_sybers.lxc`

`get_sybers.lxc` is the hardened LXC tier of the Get-Sybers lab: an Ansible collection that builds every container the same way and owns
every sanctioned way of interacting with one.

A container is created unprivileged on a Proxmox VE node from a template this repository baked in GitHub Actions and released; it runs
its service natively under `systemd`; it carries no SSH daemon and no container runtime; and it is touched afterwards in exactly two
ways: through the API the service itself serves, and through the roles here over `pct exec` from the node. Each rule has a detector, and
the detector runs on every pull request.

The collection is used from a checkout on the Proxmox node (the node-side plays) or from anywhere that reaches a service's API (the
client plays). It is published to Ansible Galaxy as `get_sybers.lxc`; its templates are published as GitHub Releases of this repository.

---

## In this documentation

| | |
| --- | --- |
| [How-to guides](howto/index.md) | **Step-by-step guides** covering the operations: deploy 1Password Connect, Semaphore UI or distrobuilder, build and release a template, add a service |
| [Reference](reference/index.md) | **Technical information**: the hardened-LXC premise and what enforces each rule, the template manifest, the roles |

The roles document their own contracts: [`lxc_guest`](../roles/lxc_guest/README.md), [`lxc_preflight`](../roles/lxc_preflight/README.md),
[`lxc_onepassword_connect`](../roles/lxc_onepassword_connect/README.md), [`lxc_onepassword_item`](../roles/lxc_onepassword_item/README.md),
[`lxc_semaphore`](../roles/lxc_semaphore/README.md), [`lxc_distrobuilder`](../roles/lxc_distrobuilder/README.md).
The templates document what they carry: [`templates/`](../templates/README.md).

---

## Project and community

`get_sybers.lxc` is free software under the [GNU Affero General Public License v3.0](../LICENSE). It is part of the Get-Sybers lab,
alongside the cluster tier in [get-sybers/proxmox](https://github.com/get-sybers/proxmox) that supplies the node, the storage, the
bridge and the API credential this tier builds on.

- [Contribute to the project](../CONTRIBUTING.md)
- [Report a vulnerability](../SECURITY.md)
- [Code of conduct](../CODE_OF_CONDUCT.md)
- [Maintainers](../MAINTAINERS)
