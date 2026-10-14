# Add a service

A service that lives in a hardened container is a template, a role, a play, a placement file and a Molecule scenario. Nothing else:
the container mechanics are `lxc_guest`'s, and the rules in [`hardened-lxc-premise.md`](../reference/hardened-lxc-premise.md) apply
to the new service the moment its role exists, because `scripts/check_lxc_boundary.py` scans every role.

1. **A template `templates/<service>/`** — the manifest (`template.yml`: base, version, bake steps, output) and a README. See
   [`templates/README.md`](../../templates/README.md).
2. **A role `lxc_<service>`** with four entry points: `bake` (inside the build rootfs — install, users, units, wants links; chroot-safe,
   no credentials, no start), `container` (node side — include `lxc_guest` with the placement, template URL and checksum), `server`
   (guest side — assert the baseline marker and the template marker first, then configure and start), `remove` (node side — include
   `lxc_guest` `tasks_from: remove`). Its defaults point at the collection variables in `inventory/group_vars/all/lxc.yml` and name its
   released template.
3. **An API-client role `lxc_<service>_item`** (or similar) if operators need to put data into the running service.
4. **A play `deploy-<service>.yml`** sequencing: `lxc_preflight` → `container` → `lxc_guest` `baseline` → `server`, plus the opt-in destroy play
   under `--tags destroy`.
5. **A placement template** `inventory/example/group_vars/all/<service>.yml` with `CHANGE-ME` placeholders for the CT id and the released
   template's checksum (never a real value) and, if it needs secrets, a `inventory/secrets/<service>.yml.example`.
6. **Molecule**: a negative scenario proving `server` refuses a guest without the marker; `make conform` runs the boundary check. Open the
   PR. Once merged, run the Templates workflow for the template with *publish* on (the environment's reviewer approves it); the run
   creates the `<service>/v<version>` release. Then pin the checksum.
