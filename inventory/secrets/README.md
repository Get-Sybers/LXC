# inventory/secrets/

Gitignored, `ansible-vault`-encrypted `-e` files. Nothing here is committed except this README, the `.gitignore`, and `*.example` templates
(standards §7, the split vars/vault pattern). `ansible.cfg` excludes this directory from inventory parsing.

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
access-key encryption). Create it from the template, generate one fresh value per key, and encrypt it:

```bash
cp semaphore.yml.example semaphore.yml
head -c32 /dev/urandom | base64   # once per key
ansible-vault encrypt semaphore.yml
```

Run the deploy with `-e @inventory/secrets/semaphore.yml --ask-vault-pass`. Keep the file: `lxc_semaphore_access_key_encryption` is
what every stored access key is encrypted with. See `doc/howto/deploy-semaphore.md`.
