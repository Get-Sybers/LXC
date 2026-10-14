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
