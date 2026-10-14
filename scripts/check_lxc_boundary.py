"""check_lxc_boundary.py — the detector for the hardened LXC premise (docs/01).

A rule with no detector is a suggestion. This scan fails the gate when any
play or role in this collection breaks one of the mechanically checkable rules:

  rule 2  No SSH into a guest, and no `raw`. No playbook or role may set
          ansible_connection to ssh/paramiko/smart, and `ansible.builtin.raw`
          (or bare `raw:`) never appears.
  rule 4  Node-side mechanics live in one role. Only roles/lxc_guest/ may use
          the community.proxmox.proxmox module, and only it and the read-only
          gate roles/lxc_preflight/ may call pct, pvesh, pvesm or pveam in a
          task. Every other role and every playbook reaches a node only through
          lxc_guest, and a guest only through proxmox_pct_remote. A playbook's
          `group/community.proxmox.proxmox` module_defaults block is how the
          PVE credential reaches lxc_guest, not a call, and is allowed.
  rule 5  A service role refuses a guest that skipped the baseline. Every
          roles/lxc_<service>/tasks/server.yml must stat and assert the
          baseline marker before anything else — concretely, it must reference
          the marker variable (<role>_baseline_marker) in its first two tasks.

Scanning is line-based over YAML, Jinja, Python and shell under playbooks/ and
roles/ (Markdown is not scanned: documentation may quote what it forbids), so
every hit is reported file:line. Whole-line comments are skipped. Scanning
zero files, or an unreadable file, is a FAILURE, not a pass: a gate that could
not look must say so.

Exit 0: the premise holds.  Exit 1: at least one hit, or the scan could not scan.
Needs: python3 and PyYAML.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCAN_TREES = ("playbooks", "roles")
SCAN_SUFFIXES = {".yml", ".yaml", ".j2", ".py", ".sh"}
TRAILING_COMMENT = re.compile(r"\s#.*$")
NODE_ROLE = "lxc_guest"
# The read-only admission gate may look for pct; it may not create anything.
NODE_TOOL_ROLES = {NODE_ROLE, "lxc_preflight"}

SSH_CONNECTION = re.compile(r"ansible_connection\s*[:=]\s*['\"]?(ssh|paramiko|paramiko_ssh|smart|ansible\.builtin\.ssh)\b")
RAW_MODULE = re.compile(r"^\s*-?\s*(ansible\.builtin\.)?raw\s*:")
NODE_TOOL = re.compile(r"(^|[\s\[,'\"/])(pct|pvesh|pvesm|pveam)([\s\],'\"]|$)")
NODE_MODULE = re.compile(r"(?<!group/)\bcommunity\.proxmox\.proxmox\s*:")


def scannable(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SCAN_SUFFIXES


def strip_comment(line: str) -> str:
    if line.lstrip().startswith("#"):
        return ""
    return TRAILING_COMMENT.sub("", line)


def role_of(rel: Path) -> str | None:
    parts = rel.parts
    return parts[1] if len(parts) > 2 and parts[0] == "roles" else None


def is_task_file(rel: Path) -> bool:
    """Task files and playbooks: where a tool could actually be invoked (meta and
    defaults are prose and inputs, and may name pct in a description)."""
    return rel.suffix in (".yml", ".yaml") and (rel.parts[0] == "playbooks" or (len(rel.parts) > 2 and rel.parts[2] in ("tasks", "handlers")))


def scan_lines(rel: Path, text: str, hits: list[tuple[str, int, str, str]]) -> None:
    role = role_of(rel)
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw)
        if not line.strip():
            continue
        if SSH_CONNECTION.search(line):
            hits.append((str(rel), lineno, "rule 2", "a guest reached over SSH — only proxmox_pct_remote (pct exec) is allowed"))
        if RAW_MODULE.search(line):
            hits.append((str(rel), lineno, "rule 2", "`raw` is never used (it bypasses the connection plugin's quoting on pct exec)"))
        if role not in NODE_TOOL_ROLES and (is_task_file(rel) or rel.suffix in (".sh", ".py")) and NODE_TOOL.search(line):
            hits.append((str(rel), lineno, "rule 4", "pct/pvesh/pvesm/pveam called outside roles/lxc_guest (or the lxc_preflight gate)"))
        if role != NODE_ROLE and NODE_MODULE.search(line):
            hits.append((str(rel), lineno, "rule 4", "community.proxmox.proxmox used outside roles/lxc_guest"))


def check_server_entry(path: Path, hits: list[tuple[str, int, str, str]]) -> None:
    """rule 5: the first two tasks of a service role's server.yml stat and assert the marker."""
    role = path.parent.parent.name
    marker_var = f"{role}_baseline_marker"
    try:
        tasks = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as exc:
        hits.append((str(path.relative_to(ROOT)), 1, "rule 5", f"unparseable: {exc}"))
        return
    head = yaml.safe_dump(tasks[:2]) if isinstance(tasks, list) else ""
    names = [t.get("name", "") for t in tasks[:2] if isinstance(t, dict)]
    has_stat = any("ansible.builtin.stat" in t for t in tasks[:2] if isinstance(t, dict))
    has_assert = any("ansible.builtin.assert" in t for t in tasks[:2] if isinstance(t, dict))
    if not (has_stat and has_assert and marker_var in head):
        hits.append((
            str(path.relative_to(ROOT)), 1, "rule 5",
            f"server.yml must open with a stat of {marker_var} and an assert on it (first tasks: {names or 'none'})",
        ))


def main() -> int:
    hits: list[tuple[str, int, str, str]] = []
    unreadable: list[str] = []
    scanned = 0
    for tree in SCAN_TREES:
        root = ROOT / tree
        if not root.is_dir():
            print(f"FAIL: scan tree missing: {tree}/")
            return 1
        for path in sorted(p for p in root.rglob("*") if scannable(p)):
            rel = path.relative_to(ROOT)
            try:
                text = path.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeDecodeError) as exc:
                unreadable.append(f"{rel}: {exc}")
                continue
            scanned += 1
            scan_lines(rel, text, hits)
    service_entries = sorted((ROOT / "roles").glob("lxc_*/tasks/server.yml"))
    for entry in service_entries:
        if entry.parent.parent.name != NODE_ROLE:
            check_server_entry(entry, hits)
    print(f"lxc boundary: scanned {scanned} file(s) under {', '.join(t + '/' for t in SCAN_TREES)}; "
          f"{len(service_entries)} service entry point(s) checked for the baseline assertion")
    if scanned == 0:
        print("FAIL: scanned nothing — a gate that could not look must not pass")
        return 1
    if unreadable:
        print(f"\nFAIL: {len(unreadable)} file(s) could not be read — not checked is not passed:")
        for u in unreadable:
            print(f"  {u}")
        return 1
    if hits:
        print(f"\nFAIL: {len(hits)} breach(es) of the hardened LXC premise (docs/01-Hardened-LXC-Premise.md):\n")
        for rel, lineno, rule, why in hits:
            print(f"  {rel}:{lineno}   [{rule}] {why}")
        return 1
    print("OK: the premise holds — no SSH or raw into a guest, node mechanics only in lxc_guest, "
          "every service entry point asserts the baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
