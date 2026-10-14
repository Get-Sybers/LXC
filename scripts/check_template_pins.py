#!/usr/bin/env python3
"""A changed template ships as a new version: the pull-request gate.

Mirrors the Version Gate of get-sybers/godfir-toolz for LXC templates. For
every ``templates/<name>/template.yml`` at the head commit, the files that
decide what the baked image contains are:

  templates/<name>/**                      the manifest and its README
  roles/<bake role>/tasks/bake.yml         each service role the manifest bakes
  roles/<bake role>/templates/**           (everything but lxc_guest, whose
  roles/<bake role>/files/**               baseline is listed below)
  roles/lxc_guest/tasks/baseline.yml       the baseline every template runs

When any of them differs between the base and the head commit, the manifest's
``lxc_template_version`` must be a literal ``X.Y.Z`` at the head and must have
moved forward from the base (a new manifest releases as whatever it says).
The Templates workflow's refusal to overwrite an existing release is the
backstop; this is the gate, so a changed image never reaches ``main`` under a
version that is already published.

Usage: python3 scripts/check_template_pins.py --base <sha> --head <sha>
       python3 scripts/check_template_pins.py --self-test
Needs: python3 and git only (no PyYAML: the two keys are read by pattern).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION_LINE = re.compile(r"^lxc_template_version:\s*['\"]?([^'\"\s#]+)['\"]?\s*(#.*)?$", re.M)
BAKE_ROLE = re.compile(r"^\s*-\s*role:\s*get_sybers\.lxc\.([a-z][a-z0-9_]*)\s*$", re.M)
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
BASELINE = "roles/lxc_guest/tasks/baseline.yml"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout


def show(ref: str, path: str) -> str | None:
    """The file's content at ref, or None when it does not exist there."""
    proc = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=REPO, capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def manifest_version(text: str) -> str | None:
    m = VERSION_LINE.search(text)
    return m.group(1) if m else None


def watched_paths(name: str, manifest: str) -> list[str]:
    """Path prefixes (a trailing slash means a tree) that decide the image."""
    paths = [f"templates/{name}/", BASELINE]
    for role in BAKE_ROLE.findall(manifest):
        if role == "lxc_guest":
            continue
        paths += [f"roles/{role}/tasks/bake.yml", f"roles/{role}/templates/", f"roles/{role}/files/"]
    return paths


def touched(changed: list[str], watched: list[str]) -> list[str]:
    return sorted(f for f in changed if any(f == w or (w.endswith("/") and f.startswith(w)) for w in watched))


def semver(v: str) -> tuple[int, int, int] | None:
    m = SEMVER.match(v)
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def judge(name: str, old_manifest: str | None, new_manifest: str, hits: list[str]) -> tuple[bool, str]:
    """(ok, message) for one template whose watched files changed."""
    new = manifest_version(new_manifest)
    if new is None or semver(new) is None:
        return False, (f"templates/{name}/template.yml: lxc_template_version must be a literal X.Y.Z "
                       f"(got {new!r}); it is this repository's release of the template, not the service's version")
    if old_manifest is None:
        return True, f"templates/{name}: new template, releases as {name}/v{new}"
    old = manifest_version(old_manifest)
    if old is None or semver(old) is None:
        return True, f"templates/{name}: {old!r} -> {new} (the base carried no pinned release)"
    if new == old:
        return False, (f"templates/{name}/template.yml: the image changed ({', '.join(hits)}) but "
                       f"lxc_template_version stayed {old} — raise it in this PR; {name}/v{old} is immutable")
    if semver(new) < semver(old):  # type: ignore[operator]
        return False, f"templates/{name}/template.yml: lxc_template_version went backwards: {old} -> {new}"
    return True, f"templates/{name}: {old} -> {new}"


def check(base: str, head: str) -> int:
    changed = [line for line in git("diff", "--name-only", base, head).splitlines() if line]
    manifests = [line for line in git("ls-tree", "-r", "--name-only", head, "templates/").splitlines()
                 if re.fullmatch(r"templates/[^/]+/template\.yml", line)]
    fail = 0
    for path in sorted(manifests):
        name = path.split("/")[1]
        new_manifest = show(head, path) or ""
        hits = touched(changed, watched_paths(name, new_manifest))
        if not hits:
            print(f"templates/{name}: unchanged")
            continue
        ok, msg = judge(name, show(base, path), new_manifest, hits)
        print(("" if ok else "::error file=" + path + "::") + msg)
        fail |= not ok
    return int(fail)


def self_test() -> int:
    base = 'lxc_template_name: x\nlxc_template_version: "1.0.0"\nlxc_template_bake:\n  - role: get_sybers.lxc.lxc_guest\n  - role: get_sybers.lxc.lxc_x\n'
    cases = [
        (None, base, ["templates/x/template.yml"], True),                       # new template
        (base, base, ["templates/x/README.md"], False),                         # changed, not raised
        (base, base.replace("1.0.0", "1.0.1"), ["roles/lxc_x/tasks/bake.yml"], True),
        (base, base.replace("1.0.0", "0.9.0"), ["templates/x/template.yml"], False),  # backwards
        (base, base.replace('"1.0.0"', '"{{ lxc_x_version }}"'), ["templates/x/template.yml"], False),  # not literal
        (base.replace('"1.0.0"', '"{{ lxc_x_version }}"'), base, ["templates/x/template.yml"], True),  # base unpinned
    ]
    bad = 0
    for old, new, hits, expect in cases:
        ok, msg = judge("x", old, new, hits)
        print(("ok  " if ok == expect else "BAD ") + msg)
        bad |= ok != expect
    watched = watched_paths("x", base)
    expect_watched = ["templates/x/", BASELINE, "roles/lxc_x/tasks/bake.yml", "roles/lxc_x/templates/", "roles/lxc_x/files/"]
    if watched != expect_watched:
        print(f"BAD watched paths: {watched}")
        bad = 1
    hits = touched(["roles/lxc_x/tasks/bake.yml", "roles/lxc_x/tasks/server.yml", "templates/x/README.md", "README.md"], watched)
    if hits != ["roles/lxc_x/tasks/bake.yml", "templates/x/README.md"]:
        print(f"BAD touched: {hits}")
        bad = 1
    print("self-test " + ("FAILED" if bad else "passed"))
    return int(bad)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.base:
        ap.error("--base is required (or --self-test)")
    return check(args.base, args.head)


if __name__ == "__main__":
    sys.exit(main())
