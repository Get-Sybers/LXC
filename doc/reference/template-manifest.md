# Template manifest

`templates/<name>/template.yml` is the complete definition of one LXC template: a plain vars file that
[`playbooks/bake-template.yml`](../../playbooks/bake-template.yml) loads with `vars_files`. The directory name, `lxc_template_name` and
the release tag prefix (`<name>/v<version>`) are the same string.

## Keys

`template.yml` is a plain vars file loaded by [`playbooks/bake-template.yml`](../../playbooks/bake-template.yml). It declares:

| Key | Meaning |
| --- | --- |
| `lxc_template_name` | the template's name; also the directory name and the release tag prefix |
| `lxc_template_version` | the version baked in (usually the service's release); the release tag is `<name>/v<version>` |
| `lxc_template_arch` | `amd64` or `arm64` |
| `lxc_template_output` | the artifact file name, `<base>-<name>_<version>_<arch>.tar.zst` |
| `lxc_template_base_url` | the stock Proxmox system template the bake starts from |
| `lxc_template_base_checksum` | that template's published `sha512:` from Proxmox's own index — pin it with `scripts/base_template_checksum.py` |
| `lxc_template_bake` | the ordered role entry points run inside the rootfs, over the `chroot` connection |

Any variable a bake step reads (for example `lxc_onepassword_connect_version`) is set in the same file, so the manifest is the single place a
template's inputs are declared.

## Bake steps

Each `lxc_template_bake` entry names a role and a `tasks_from` entry point. They run in order inside the unpacked base rootfs over
`community.general.chroot`, as root, with `/proc`, `/sys`, `/dev` and `/dev/pts` mounted, a resolver present and a `policy-rc.d` that
refuses service starts. A bake entry point is therefore chroot-safe by construction: it installs packages, creates users, writes unit
files and enables them by creating the `multi-user.target.wants` symlinks, and it never starts a service or touches a credential. The
first step of every template is `lxc_guest` `baseline`; the last is the service role's `bake`.

## What the bake adds

| Path | Content |
| --- | --- |
| `/etc/get-sybers-lxc-baseline` | `baseline=<n>` and `role=get_sybers.lxc.lxc_guest`, written by the baseline |
| `/etc/get-sybers-lxc-template` | `name=`, `version=`, `base=`, `collection=get_sybers.lxc`, written by the bake play |
| `/etc/machine-id` | empty, so every container derives its own identity on first boot |

The sealed artifact is named by `lxc_template_output` and is asserted to carry both markers and no `/usr/sbin/sshd`.
