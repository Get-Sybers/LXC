# lxc_elastic_repo

Configure the Elastic apt repository inside a build rootfs, with the signing key verified against the fingerprint Elastic publishes. A bake
helper the `elasticsearch` and `kibana` templates share (standards: a task sequence two roles need is one role, not two copies); it installs
nothing itself and is never run in a guest.

- **Where it runs:** inside the build rootfs over `community.general.chroot`, included from a role's `bake` entry point.
- **Collections:** `ansible.builtin` only.
- **Idempotent:** yes; the apt cache refreshes only when the source changed.

| Variable | Default | Description |
| --- | --- | --- |
| `lxc_elastic_repo_major` | `9.x` | Release line. |
| `lxc_elastic_repo_key_fingerprint` | Elastic's published fingerprint | A downloaded key without it is refused. |
| `lxc_elastic_repo_keyring` | `/etc/apt/keyrings/elasticsearch.asc` | Where the key lands; the source's `Signed-By`. |

```yaml
- name: "bake | The Elastic apt repository"
  ansible.builtin.include_role:
    name: get_sybers.lxc.lxc_elastic_repo
```
