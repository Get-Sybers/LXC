The template below is for bug reports and support questions. Remove what does
not apply and add what helps. Never paste a credential, a token, a
`1password-credentials.json` or a vaulted file.

# Required information

- Proxmox VE version (`pveversion`):
- `get_sybers.lxc` version (`ansible-galaxy collection list get_sybers.lxc`), or the branch and commit:
- `ansible-core` version (`ansible --version`):
- The play and the `-e` inputs you ran it with (values redacted where secret):
- For a container problem, `pct config <vmid>` and the template marker:
  `pct exec <vmid> -- cat /etc/get-sybers-lxc-template /etc/get-sybers-lxc-baseline`

# Issue description

A brief description of what failed or what could be improved.

# Steps to reproduce

1. Step one
2. Step two
3. Step three

# Information to attach

- [ ] the play output with `-vv` (secret-bearing tasks are `no_log` and print nothing)
- [ ] the service's journal inside the container (`pct exec <vmid> -- journalctl -u <unit> -n 200`)
- [ ] for a template build, the `Templates` workflow run or the local bake output
