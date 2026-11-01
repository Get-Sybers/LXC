# inventory/secrets/

Gitignored, `ansible-vault`-encrypted `-e` files. Nothing here is committed except this README, the `.gitignore`, and `*.example` templates
(standards §7, the split vars/vault pattern). `ansible.cfg` excludes this directory from inventory parsing.

## `1password-credentials.json`

The credentials file 1Password issues when you create the Connect server (Developer -> Infrastructure Secrets Management -> 1Password
Connect). Drop it in this directory as `1password-credentials.json` (see `1password-credentials.json.example` for its shape); it is gitignored, and `playbooks/deploy-onepassword-connect.yml`
reads it from here by default (`lxc_onepassword_connect_credentials_src`) and `server` copies it into the guest. No cleartext credential
is placed anywhere else on the node.

## `onepassword.yml`

Drives `playbooks/reflect-onepassword-credentials.yml` — the connection to the 1Password Connect server plus the list of credentials to mirror.
Create it from the template and encrypt it:

```bash
cp onepassword.yml.example onepassword.yml
# edit onepassword.yml with your real host / vault id / token / item values
ansible-vault encrypt onepassword.yml
```

Run the mirror with `-e @inventory/secrets/onepassword.yml --ask-vault-pass` (or a `--vault-password-file`). See
`doc/howto/deploy-onepassword-connect.md` for the full setup.

## `semaphore.yml`

Gives `playbooks/deploy-semaphore.yml` the administrator's initial password and the three keys (cookie signing, cookie encryption,
access-key encryption). There is no template for it in the repository: write it with these seven variables, one fresh value per
key, and encrypt it:

```bash
cat > semaphore.yml <<EOF
---
lxc_semaphore_admin_login: admin
lxc_semaphore_admin_name: "Semaphore Admin"
lxc_semaphore_admin_email: "<the administrator's email>"
lxc_semaphore_admin_password: "<the administrator's initial password>"
lxc_semaphore_cookie_hash: "$(head -c32 /dev/urandom | base64)"
lxc_semaphore_cookie_encryption: "$(head -c32 /dev/urandom | base64)"
lxc_semaphore_access_key_encryption: "$(head -c32 /dev/urandom | base64)"
EOF
ansible-vault encrypt semaphore.yml
```

Run the deploy with `-e @inventory/secrets/semaphore.yml --ask-vault-pass`. Keep the file: `lxc_semaphore_access_key_encryption` is
what every stored access key is encrypted with. See `doc/howto/deploy-semaphore.md`.

## `velociraptor.yml`

Gives `playbooks/deploy-velociraptor.yml` the GUI administrator's initial password. There is no template for it in the repository: write it
with these two variables and encrypt it:

```bash
cat > velociraptor.yml <<'YAML'
---
lxc_velociraptor_admin_user: admin
lxc_velociraptor_admin_password: "<the administrator's initial password>"
YAML
ansible-vault encrypt velociraptor.yml
```

Run the deploy with `-e @inventory/secrets/velociraptor.yml --ask-vault-pass`. The administrator is created once, when absent; change its
password in the GUI afterwards (the role never rewrites it). See `doc/howto/deploy-velociraptor.md`.

## `ghost9.yml`

Gives `playbooks/deploy-ghost9.yml` the PostgreSQL password (it backs the GHOSTS API connection string and the Grafana datasource) and the
n8n owner account's password. Write it with these variables and encrypt it:

```bash
cat > ghost9.yml <<'YAML'
---
lxc_ghost9_db_password: "<a strong PostgreSQL password>"
lxc_ghost9_n8n_owner_email: "admin@ghosts.local"
lxc_ghost9_n8n_owner_password: "<the n8n owner's initial password>"
YAML
ansible-vault encrypt ghost9.yml
```

Run the deploy with `-e @inventory/secrets/ghost9.yml --ask-vault-pass`. The n8n owner is created once, when absent, and managed in n8n
afterwards. See `doc/howto/deploy-ghost9.md`.
