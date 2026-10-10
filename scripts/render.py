#!/usr/bin/env python3
"""Render the leaderboard tables in README.md from leaderboard.json.

Only the region between the LEADERBOARD markers is generated, so the prose in
README.md is safe to edit by hand.

Usage:
    python3 scripts/render.py            # rewrite README.md in place
    python3 scripts/render.py --check    # exit 1 if README.md is out of date
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from leaderboard import (  # noqa: E402
    FREE_NUANCE_FLOOR,
    DataError,
    badge_text,
    cell,
    compute_badges,
    fmt_money,
    latest_per_model,
    load_entries,
    ranked,
    slugify,
    total_tests,
)

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

START = "<!-- LEADERBOARD:START -->"
END = "<!-- LEADERBOARD:END -->"


def model_cell(entry: dict) -> str:
    """Link the model name to its report, so the table is a way in, not a dead end."""
    return f"**[{cell(entry['model'])}](reports/{slugify(entry['model'])}.md)**"


def summary_table(entries: list[dict]) -> str:
    lines = [
        "| Rank | Model | Provider | Strict pass | Nuance | Latency | Cost | Judge | Protocol | Badges |",
        "|:--:|:--|:--|:--:|:--:|--:|--:|:--|:--|:--|",
    ]
    for i, e in enumerate(ranked(entries), 1):
        judge = e.get("judge", {}).get("model", "n/a")
        protocol = e.get("judge", {}).get("protocol", "n/a")
        lines.append(
            f"| {i} | {model_cell(e)} | {cell(e['provider'])} "
            f"| {e['strict_pass_count']}/{total_tests(e)} | {e['nuance_score']:.1f}% "
            f"| {e['elapsed_seconds']:.1f}s | {fmt_money(e)} | {cell(judge)} "
            f"| {cell(protocol)} | {badge_text(e)} |"
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
    for e in ranked(entries):
        marks = []
        for tid in test_ids:
            score = e["test_scores"].get(tid)
            if not score:
                marks.append("n/a")
            elif score.get("strict_pass"):
                marks.append("pass")
            else:
                marks.append(
                    f"fail ({score.get('passed_checks', '?')}/{score.get('total_checks', '?')})"
                )
        lines.append(f"| {model_cell(e)} | " + " | ".join(marks) + " |")
    return "\n".join(lines)


def failure_table(entries: list[dict]) -> str:
    rows = []
    for e in ranked(entries):
        for tid, score in sorted(e["test_scores"].items()):
            if score.get("strict_pass"):
                continue
            for check in score.get("checks", []):
                if check.get("pass"):
                    continue
                rows.append(
                    f"| {model_cell(e)} | {cell(tid)} | {cell(check.get('item', ''))} "
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
            f"{len(entries)} models, latest run each, judged blind against the "
            "20-point rubric. The model name links to a full report with the "
            "prompts, the completions, and every judge verdict.",
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
            "Scores are only comparable between rows that share a judge and protocol.",
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


def build() -> tuple[str, int]:
    """Return (rendered README, number of models). Raises DataError."""
    entries = latest_per_model(load_entries())
    if not README.is_file():
        raise DataError("missing README.md")
    return splice(README.read_text(encoding="utf-8"), render(entries)), len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if README.md is stale")
    args = parser.parse_args()

    try:
        updated, count = build()
        current = README.read_text(encoding="utf-8")
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
        print(f"README.md is up to date ({count} models).")
        return 0

    if current == updated:
        print(f"README.md already up to date ({count} models).")
        return 0
    README.write_text(updated, encoding="utf-8")
    print(f"Rendered README.md from {count} models.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
