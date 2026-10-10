#!/usr/bin/env python3
"""Contract checks for skills in this repo.

The skill moved here from vuon9/vstack, where verify.py enforced these rules.
Without an equivalent check here, the skill would silently drift.

Rules:
  - frontmatter `name` equals the folder name
  - frontmatter `description` starts with "Use when"
  - a README.md sits beside SKILL.md
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def check() -> list[str]:
    errors: list[str] = []
    if not SKILLS.is_dir():
        return []

    skill_dirs = sorted(d for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())
    if not skill_dirs:
        errors.append("skills/ contains no skill folders with a SKILL.md")

    for skill_dir in skill_dirs:
        name = skill_dir.name
        meta = frontmatter(skill_dir / "SKILL.md")

        if not meta.get("name"):
            errors.append(f"{name}: SKILL.md frontmatter is missing 'name'")
        elif meta["name"] != name:
            errors.append(f"{name}: frontmatter name '{meta['name']}' does not match folder name")

        desc = meta.get("description", "")
        if not desc:
            errors.append(f"{name}: SKILL.md frontmatter is missing 'description'")
        elif not desc.startswith("Use when"):
            errors.append(f"{name}: description must start with 'Use when'")

        readme = skill_dir / "README.md"
        if not readme.is_file():
            errors.append(f"{name}: missing README.md")
        elif len(re.sub(r"\s+", " ", readme.read_text(encoding="utf-8")).strip()) < 200:
            errors.append(f"{name}: README.md looks too thin to document the skill")

    return errors


def main() -> int:
    errors = check()
    if errors:
        print("Skill contract check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    count = len([d for d in SKILLS.iterdir() if (d / "SKILL.md").is_file()])
    print(f"Skill contract check passed ({count} skill(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
