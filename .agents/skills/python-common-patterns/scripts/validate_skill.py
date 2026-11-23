#!/usr/bin/env python3
"""Portable, stdlib-only structural validation for this Agent Skill.

It checks metadata syntax at a conservative level, referenced local files,
and Python source parsing. Run actual example tests separately.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def validate() -> None:
    raw = SKILL.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", raw, flags=re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    fm = match.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, flags=re.MULTILINE)
    description = re.search(r"^description:\s*(.+)$", fm, flags=re.MULTILINE)
    assert name and name.group(1).strip() == ROOT.name, "name != directory name"
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name.group(1).strip())
    assert description and 0 < len(description.group(1).strip()) <= 1024
    assert len(name.group(1).strip()) <= 64

    links = re.findall(r"\]\((references/[^)#]+\.md)\)", raw)
    assert len(links) >= 10, "SKILL.md must reference its topic files"
    for rel in links:
        assert (ROOT / rel).is_file(), f"missing reference: {rel}"

    for path in ROOT.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    print(f"VALID: {ROOT.name}: {len(links)} local ref links, "
          f"{len(list(ROOT.rglob('*.py')))} Python files parse correctly")


if __name__ == "__main__":
    validate()
