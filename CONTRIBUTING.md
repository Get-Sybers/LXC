# Contributing

## Pull requests

Changes to this project are proposed as pull requests on GitHub at
<https://github.com/get-sybers/lxc>. A pull request is reviewed there and, once
approved by a code owner and green on `all_green`, squash-merged into `main`.

The branch ruleset requires signed commits, a linear history, one approving
review from a code owner, every review thread resolved, and the `all_green`
status check. Branches are named `<type>/<description>`
(`feat/gitlab-runner-template`); the pull request title is a Conventional
Commit (`feat(templates): …`, `fix(lxc_guest): …`), because the squash merge
uses it as the commit message.

## Before you open one

```sh
make deps        # the pinned collections and the test tooling
prek install     # the git hooks: lint, secrets, commit-msg
make conform     # the full local gate: lint, pins, boundary, sanity, molecule, changelog, build
```

`make conform` runs the same commands CI runs, with the same configuration
files, so what passes locally passes on the pull request. Every change that
touches a plugin needs a fragment under `changelogs/fragments/`; a change to
behaviour or an interface updates the documentation under `doc/` and the
role's `README.md`.

## Site configuration stays out of the repository

The repository carries only `inventory/example/`, the template of the site configuration; `make config` copies it into `inventory/`,
where the real files are untracked. A pull request never adds a node name, a subnet, a CT id or a storage name: a new input gets a
`CHANGE-ME` placeholder in the template and a sentence in the inventory README. Examples in documentation and role comments use the
RFC 5737 documentation range (`192.0.2.0/24`).

## The premise is law

Every container this collection builds is unprivileged, carries no SSH daemon
and no container runtime, is reached only through `pct exec` from the node,
and is created only from a template this repository released. The rules and
what enforces each are in
[`doc/reference/hardened-lxc-premise.md`](doc/reference/hardened-lxc-premise.md);
`scripts/check_lxc_boundary.py` fails the gate on a breach. A change that
needs an exception to a rule is a change to the premise first, discussed in
the pull request, never a waiver in the code.

Adding a service or a template follows
[`doc/howto/add-a-service.md`](doc/howto/add-a-service.md).

## License and copyright

By default, any contribution to this project is made under the GNU Affero
General Public License v3.0 only (`AGPL-3.0-only`, see `LICENSE`). The author
of a change remains the copyright holder of their contribution; there is no
copyright assignment.

## Security

Do not open a public issue for a security problem. Use
**Security → Report a vulnerability** on the repository; see `SECURITY.md`.
