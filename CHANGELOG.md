# Changelog

All notable changes to `get_sybers.lxc` are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`0.y.z`
until the interface is stable).

`antsibull-changelog` generates this file from `changelogs/fragments/` at
release time; until the first release, the unreleased notes live in the
fragments.

## [Unreleased]

### Added

- The `get_sybers.lxc` collection: `lxc_guest`, `lxc_preflight`,
  `lxc_onepassword_connect`, `lxc_onepassword_item`, the two plays, the
  hardened-LXC premise (`doc/reference/hardened-lxc-premise.md`) and its detector
  (`scripts/check_lxc_boundary.py`). The 1Password content moved here from
  `get-sybers/proxmox` (`get_sybers.cluster`); see
  `changelogs/fragments/initial-import.yml`.
- Templates built in GitHub Actions and published as GitHub Releases
  (`templates/`, `playbooks/bake-template.yml`, the `Templates` workflow,
  `doc/howto/build-a-template.md`); `lxc_guest` fetches a release by its
  pinned checksum; `lxc_onepassword_connect` splits into `bake` and `server`. See
  `changelogs/fragments/template-build.yml`.

[Unreleased]: https://github.com/get-sybers/lxc/compare/a481839...HEAD
