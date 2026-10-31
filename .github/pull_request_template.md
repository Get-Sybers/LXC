<!-- Title must be a Conventional Commit: feat|fix|docs|chore|ci|test|refactor|build(scope): summary -->
<!-- One or two sentences. Link the issue: Closes
<!-- The reason, not the diff. -->
- [ ] `make conform` passes locally (same checks as CI)
- [ ] Proven on a live node from scratch: the affected container destroyed (`--tags destroy -e lxc_guest_confirm_destroy=true`) and redeployed with this change, then a second run reported `changed=0`
- [ ] Changelog updated (`CHANGELOG.md` *Unreleased*, or a `changelogs/fragments/` file for a collection)
- [ ] Docs updated for any behaviour or interface change
- [ ] No new version literal outside the pin file (`requirements.yml` / `go.mod` / `.pre-commit-config.yaml`)
