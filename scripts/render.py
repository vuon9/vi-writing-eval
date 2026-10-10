#!/usr/bin/env python3
"""Render the leaderboard tables in README.md from leaderboard.json.

The README keeps its hand-written prose. Only the region between the
LEADERBOARD markers is generated, so editing prose by hand is safe.

Usage:
    python3 scripts/render.py            # rewrite README.md in place
    python3 scripts/render.py --check    # exit 1 if README.md is out of date
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "leaderboard.json"
README = ROOT / "README.md"

START = "<!-- LEADERBOARD:START -->"
END = "<!-- LEADERBOARD:END -->"

REQUIRED_FIELDS = (
    "model",
    "provider",
    "strict_pass_count",
    "nuance_score",
    "elapsed_seconds",
    "cost_usd",
    "test_scores",
)

FREE_NUANCE_FLOOR = 70.0


class DataError(Exception):
    """leaderboard.json is malformed or incomplete."""


def load_entries() -> list[dict]:
    if not DATA.is_file():
        raise DataError(f"missing {DATA.name}")
    try:
        raw = json.loads(DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"{DATA.name} is not valid JSON: {exc}") from exc

    entries = raw.get("entries") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise DataError(f"{DATA.name} must be a list or an object with an 'entries' list")

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DataError(f"entry {i} is not an object")
        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            label = entry.get("model", f"entry {i}")
            raise DataError(f"{label} is missing required fields: {', '.join(missing)}")
        if not isinstance(entry["test_scores"], dict) or not entry["test_scores"]:
            raise DataError(f"{entry['model']} has empty or invalid test_scores")
    return entries


def total_tests(entry: dict) -> int:
    return len(entry["test_scores"])


def compute_badges(entries: list[dict]) -> None:
    """Award badges in place. Rewritten each render, never trusted from the file."""
    for entry in entries:
        entry["badges"] = []
    if not entries:
        return

    best = max(e["nuance_score"] for e in entries)
    for entry in entries:
        if entry["nuance_score"] == best:
            entry["badges"].append("Quality Crown")

    qualifying = [e for e in entries if e["nuance_score"] >= FREE_NUANCE_FLOOR]
    if qualifying:
        fastest = min(e["elapsed_seconds"] for e in qualifying)
        for entry in qualifying:
            if entry["cost_usd"] == 0:
                entry["badges"].append("Free Champion")
            if entry["elapsed_seconds"] == fastest:
                entry["badges"].append("Speed Demon")


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").strip()


def fmt_money(entry: dict) -> str:
    return "Free" if entry["cost_usd"] == 0 else f"${entry['cost_usd']:.4f}"


def summary_table(entries: list[dict]) -> str:
    ranked = sorted(
        entries,
        key=lambda e: (e["nuance_score"], e["strict_pass_count"], -e["elapsed_seconds"]),
        reverse=True,
    )
    lines = [
        "| Rank | Model | Provider | Strict pass | Nuance | Latency | Cost | Judge | Badges |",
        "|:--:|:--|:--|:--:|:--:|--:|--:|:--|:--|",
    ]
    for i, e in enumerate(ranked, 1):
        judge = e.get("judge", {}).get("model", "n/a")
        badges = ", ".join(f"`[{b}]`" for b in e["badges"]) or "none"
        lines.append(
            f"| {i} | **{cell(e['model'])}** | {cell(e['provider'])} "
            f"| {e['strict_pass_count']}/{total_tests(e)} | {e['nuance_score']:.1f}% "
            f"| {e['elapsed_seconds']:.1f}s | {fmt_money(e)} | {cell(judge)} | {badges} |"
        )
    return "\n".join(lines)


def per_test_table(entries: list[dict]) -> str:
    test_ids: list[str] = []
    for entry in entries:
        for tid in entry["test_scores"]:
            if tid not in test_ids:
                test_ids.append(tid)
    test_ids.sort()

    header = "| Model | " + " | ".join(cell(t) for t in test_ids) + " |"
    sep = "|:--|" + ":--:|" * len(test_ids)
    lines = [header, sep]
    for e in sorted(entries, key=lambda x: -x["nuance_score"]):
        marks = []
        for tid in test_ids:
            score = e["test_scores"].get(tid)
            if not score:
                marks.append("n/a")
            elif score.get("strict_pass"):
                marks.append("pass")
            else:
                marks.append(f"fail ({score.get('passed_checks', '?')}/{score.get('total_checks', '?')})")
        lines.append(f"| **{cell(e['model'])}** | " + " | ".join(marks) + " |")
    return "\n".join(lines)


def failure_table(entries: list[dict]) -> str:
    rows = []
    for e in sorted(entries, key=lambda x: -x["nuance_score"]):
        for tid, score in sorted(e["test_scores"].items()):
            if score.get("strict_pass"):
                continue
            for check in score.get("checks", []):
                if check.get("pass"):
                    continue
                rows.append(
                    f"| **{cell(e['model'])}** | {cell(tid)} | {cell(check.get('item', ''))} "
                    f"| {cell(check.get('reason', ''))} |"
                )
    if not rows:
        return "_No failed checkpoints._"
    header = [
        "| Model | Test | Failed checkpoint | Judge reason |",
        "|:--|:--|:--|:--|",
    ]
    return "\n".join(header + rows)


def render(entries: list[dict]) -> str:
    compute_badges(entries)
    return "\n".join(
        [
            START,
            "",
            "## Leaderboard",
            "",
            f"{len(entries)} model runs, judged blind against the 20-point rubric.",
            "",
            summary_table(entries),
            "",
            "## Per-test result",
            "",
            per_test_table(entries),
            "",
            "## Failed checkpoints",
            "",
            failure_table(entries),
            "",
            "## Badge legend",
            "",
            "- `[Quality Crown]` highest Nuance score on the board.",
            "- `[Free Champion]` zero cost and Nuance at or above "
            f"{FREE_NUANCE_FLOOR:.0f}%.",
            "- `[Speed Demon]` lowest latency among runs at or above "
            f"{FREE_NUANCE_FLOOR:.0f}% Nuance.",
            "",
            END,
        ]
    )


def splice(readme_text: str, block: str) -> str:
    if START not in readme_text or END not in readme_text:
        raise DataError(f"README.md must contain both {START} and {END}")
    before = readme_text.split(START, 1)[0]
    after = readme_text.split(END, 1)[1]
    return f"{before}{block}{after}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if README.md is stale")
    args = parser.parse_args()

    try:
        entries = load_entries()
        if not README.is_file():
            raise DataError("missing README.md")
        current = README.read_text(encoding="utf-8")
        updated = splice(current, render(entries))
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        if current != updated:
            print(
                "error: README.md is out of date. Run: python3 scripts/render.py",
                file=sys.stderr,
            )
            return 1
        print(f"README.md is up to date ({len(entries)} entries).")
        return 0

    if current == updated:
        print(f"README.md already up to date ({len(entries)} entries).")
        return 0
    README.write_text(updated, encoding="utf-8")
    print(f"Rendered README.md from {len(entries)} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
