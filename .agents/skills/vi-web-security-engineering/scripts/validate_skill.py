#!/usr/bin/env python3
"""Validate a local Agent Skill's layout and internal Markdown references.

No network, package install, script execution or changes to the target folder.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    root = root.resolve()
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["Thiếu SKILL.md ở thư mục gốc"]
    txt = skill.read_text(encoding="utf-8")
    fm = re.match(r"\A---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    if not fm:
        failures.append("SKILL.md: thiếu frontmatter YAML")
    else:
        header = fm.group(1)
        match = re.search(r"^name:\s*['\"]?([a-z0-9-]+)", header, re.M)
        if not match:
            failures.append("SKILL.md: thiếu trường name hợp lệ")
        elif match.group(1) != root.name:
            failures.append(f"name {match.group(1)!r} không khớp thư mục {root.name!r}")
        if not re.search(r"^description:\s*.+$", header, re.M):
            failures.append("SKILL.md: thiếu description")
    for md in root.rglob("*.md"):
        if md.is_symlink():
            failures.append(f"Symlink Markdown cần xem xét: {md.relative_to(root)}")
            continue
        content = md.read_text(encoding="utf-8")
        for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", content):
            target = target.strip().split("#", 1)[0]
            if not target or target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            candidate = (md.parent / unquote(target)).resolve()
            if not candidate.is_relative_to(root):
                failures.append(f"Link ngoài thư mục tại {md.relative_to(root)}: {target}")
            elif not candidate.exists():
                failures.append(f"Link không tồn tại tại {md.relative_to(root)}: {target}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", nargs="?", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args()
    root = Path(args.skill_dir)
    if not root.is_dir():
        print("FAIL: skill directory không tồn tại", file=sys.stderr)
        return 2
    errors = validate(root)
    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1
    print("PASS: Frontmatter, cấu trúc cơ bản và liên kết nội bộ hợp lệ")
    print(f"Markdown files: {len(list(root.rglob('*.md')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
