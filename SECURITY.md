# Security

Use **Security → Report a vulnerability** on this repository (GitHub private
vulnerability reporting). Do not open a public issue for a security problem.

You will get an acknowledgement within 5 working days. Fixes ship as a patch
release with a `CHANGELOG.md` entry under *Security*.

Only the latest minor release line receives security fixes.

## What is in place

- Secret scanning (`gitleaks`) on every commit locally and on every pull request.
- Dependency updates with a 7-day cooldown (Dependabot) and SHA-pinned actions.
- The hardened-LXC premise (`doc/reference/hardened-lxc-premise.md`) is enforced by
  `scripts/check_lxc_boundary.py` on every pull request: no SSH into a guest,
  no privileged container, no container runtime inside a guest, node-side
  mechanics in one role only.
