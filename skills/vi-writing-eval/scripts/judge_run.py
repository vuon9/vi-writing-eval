#!/usr/bin/env python3
"""Blind evaluation, scoring, and leaderboard management for Vietnamese writing benchmarks."""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

FORBIDDEN_WORDS_TEST_2 = ["máy bay", "mây", "bầu trời", "sợ", "thích"]


def load_json_file(file_path: Path) -> dict:
    try:
        content = file_path.read_text(encoding="utf-8")
        return json.loads(content)
    except OSError as exc:
        print(f"Error reading {file_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error parsing JSON in {file_path}: {exc}", file=sys.stderr)
        sys.exit(1)


def split_words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def split_sentences(text: str) -> list[str]:
    raw = re.split(r"[.!?…]+(?:\s+|\Z)", text.strip())
    return [s.strip() for s in raw if s.strip()]


def split_poem_title(lines: list[str]) -> tuple[bool, list[str]]:
    """Split a leading markdown title from the poem body.

    A model often labels a poem with a heading (`## Cà phê sáng`) or a bold line
    (`**Cà Phê Sáng**`). That label is not a verse line, and counting it as one
    shifts every line index, which turns a correct poem into a false failure on
    the 4-line and line-4 checks. Returns (title_detected, verse_lines) so a
    semantic judge can still rule on whether the title breaks the constraint.
    """
    if len(lines) < 2:
        return False, lines
    first = lines[0]
    is_heading = bool(re.match(r"^#{1,6}\s+\S", first))
    is_bold_only = bool(re.fullmatch(r"\*\*[^*]+\*\*", first))
    if is_heading or is_bold_only:
        return True, lines[1:]
    return False, lines


def coerce_float(value: object, default: float = 0.0) -> float:
    """Scores files are often hand-written or model-written; never trust the type.

    Handles the common `"85.5%"` shape. On a genuine parse failure it warns rather
    than silently contributing a zero to the leaderboard.
    """
    if isinstance(value, str):
        value = value.strip().rstrip("%").strip()
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        print(f"Warning: could not parse numeric score {value!r}; using {default}", file=sys.stderr)
        return default


def coerce_int(value: object, default: int = 0) -> int:
    """Same contract as coerce_float, for whole-number fields."""
    if isinstance(value, str):
        value = value.strip()
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        print(f"Warning: could not parse integer score {value!r}; using {default}", file=sys.stderr)
        return default


def check_hard_constraints(outputs: list[dict]) -> dict[str, dict]:
    """Deterministically check mechanical constraints across all tests."""
    results = {}

    for item in outputs:
        test_id = item.get("test_id", "")
        completion = item.get("completion", "").strip()
        lines = [line.strip() for line in completion.splitlines() if line.strip()]
        words = split_words(completion)
        sentences = split_sentences(completion)

        checks: dict[str, object] = {
            "non_empty": bool(completion),
        }
        if item.get("truncated"):
            checks["truncated_by_token_cap"] = True

        if test_id == "test_1_poetry":
            title_detected, verse_lines = split_poem_title(lines)
            # A count, not a flag: "0" and "1" read correctly, while a boolean
            # named title_detected reads as a failure when printed as PASS/FAIL.
            checks["lines_before_verse"] = 1 if title_detected else 0
            checks["line_count_4"] = len(verse_lines) == 4
            checks["seven_words_per_line"] = (
                len(verse_lines) == 4
                and all(len(split_words(line)) == 7 for line in verse_lines)
            )
            line_4_words = split_words(verse_lines[3]) if len(verse_lines) >= 4 else []
            checks["line_4_starts_with_t"] = (
                len(line_4_words) > 0
                and all(w.lower().startswith("t") for w in line_4_words)
            )

        elif test_id == "test_2_prose":
            checks["max_3_sentences"] = len(sentences) <= 3 and len(sentences) > 0
            lower = completion.lower()
            found_forbidden = [w for w in FORBIDDEN_WORDS_TEST_2 if w in lower]
            checks["no_forbidden_words"] = len(found_forbidden) == 0
            checks["forbidden_words_found"] = found_forbidden

        elif test_id == "test_3_persona":
            checks["max_15_words"] = len(words) <= 15 and len(words) > 0

        elif test_id == "test_4_marketing":
            checks["under_50_words"] = len(words) < 50
            checks["exactly_4_sentences"] = len(sentences) == 4

        elif test_id == "test_5_email":
            has_subject = any(
                re.match(r"^(tiêu đề|subject):", line, re.IGNORECASE) for line in lines
            ) or len(lines) >= 3
            checks["has_subject_and_salutation"] = has_subject and len(lines) >= 2
            body_text = "\n".join(lines[2:]) if len(lines) > 2 else completion
            body_sentences = split_sentences(body_text)
            checks["body_exactly_2_sentences"] = len(body_sentences) == 2

        elif test_id == "test_6_rewrite":
            checks["exactly_1_sentence"] = len(sentences) == 1
            checks["contains_keyword_he_thong"] = "hệ thống" in completion.lower()

        results[test_id] = checks

    return results


def make_blind_payload(run_data: dict) -> dict:
    """Strip all model and provider metadata so the judge cannot identify the model."""
    return {
        "run_id": run_data.get("run_id"),
        "suite": run_data.get("suite"),
        "outputs": [
            {
                "test_id": item.get("test_id"),
                "title": item.get("title"),
                "prompt": item.get("prompt"),
                "completion": item.get("completion"),
            }
            for item in run_data.get("outputs", [])
        ],
    }


def compute_pareto_badges(leaderboard: list[dict]) -> list[dict]:
    """Calculate Pareto badges: Quality Crown, Sweet Spot, and Speed Demon."""
    if not leaderboard:
        return leaderboard

    max_nuance = max(entry["nuance_score"] for entry in leaderboard)
    qualifying = [entry for entry in leaderboard if entry["nuance_score"] >= 70.0]

    min_latency = min((entry["elapsed_seconds"] for entry in qualifying), default=None)

    for entry in leaderboard:
        badges = []
        if entry["nuance_score"] == max_nuance:
            badges.append("Quality Crown")

        if entry in qualifying:
            cost = entry.get("cost_usd", 0.0)
            if cost == 0.0:
                badges.append("Free Champion")
            if min_latency is not None and entry["elapsed_seconds"] == min_latency:
                badges.append("Speed Demon")

        entry["badges"] = badges

    return leaderboard


def render_leaderboard_markdown(leaderboard: list[dict]) -> str:
    lines = [
        "# Vietnamese Writing Benchmark Leaderboard",
        "",
        "Evaluation results for models tested on the Vietnamese AI text generation benchmark.",
        "",
        "## Summary rankings",
        "",
        "| Rank | Model | Strict Pass | Nuance Score | Latency (s) | Cost ($) | Badges |",
        "|:---:|:---|:---:|:---:|:---:|:---:|:---|",
    ]

    sorted_entries = sorted(
        leaderboard,
        key=lambda x: (x["nuance_score"], x["strict_pass_count"], -x["elapsed_seconds"]),
        reverse=True,
    )

    for idx, entry in enumerate(sorted_entries, 1):
        badges_str = ", ".join(f"`[{b}]`" for b in entry.get("badges", [])) or "none"
        strict = f"{entry['strict_pass_count']}/6"
        nuance = f"{entry['nuance_score']:.1f}%"
        latency = f"{entry['elapsed_seconds']:.2f}"
        cost = f"${entry['cost_usd']:.6f}" if entry["cost_usd"] > 0 else "Free"
        model_name = entry.get("model", "Unknown")
        lines.append(
            f"| {idx} | **{model_name}** | {strict} | {nuance} | {latency} | {cost} | {badges_str} |"
        )

    lines.extend([
        "",
        "## Scoring definitions",
        "",
        "- **Strict Pass:** Number of benchmark tests where 100% of checklist criteria passed.",
        "- **Nuance Score:** Percentage of total checklist points passed across all 6 tests.",
        "- **`[Quality Crown]`:** Highest overall Nuance Score.",
        "- **`[Free Champion]`:** Zero-cost model with a Nuance Score of 70% or higher.",
        "- **`[Speed Demon]`:** Lowest latency among models scoring 70% or higher.",
        "",
        f"Last updated: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ])

    return "\n".join(lines)


def cmd_blind(args):
    run_file = Path(args.run_file)
    if not run_file.is_file():
        print(f"Error: Run file not found at {run_file}", file=sys.stderr)
        sys.exit(1)

    run_data = load_json_file(run_file)
    blinded = make_blind_payload(run_data)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(blinded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved blinded payload to: {out_path}")
    else:
        print(json.dumps(blinded, indent=2, ensure_ascii=False))


def cmd_verify(args):
    run_file = Path(args.run_file)
    if not run_file.is_file():
        print(f"Error: Run file not found at {run_file}", file=sys.stderr)
        sys.exit(1)

    run_data = load_json_file(run_file)
    outputs = run_data.get("outputs", [])
    checks = check_hard_constraints(outputs)

    print(f"Deterministic checks for: {run_data.get('run_id')}\n")
    for test_id, res in checks.items():
        print(f"[{test_id}]")
        for k, v in res.items():
            if isinstance(v, bool):
                symbol = "PASS" if v else "FAIL"
            else:
                symbol = str(v)
            print(f"  - {k}: {symbol}")
        print()


def cmd_record(args):
    run_file = Path(args.run_file)
    scores_file = Path(args.scores_file)

    if not run_file.is_file() or not scores_file.is_file():
        print("Error: run file and scores file must exist", file=sys.stderr)
        sys.exit(1)

    run_data = load_json_file(run_file)
    scores_data = load_json_file(scores_file)

    evals_dir = Path(args.evals_dir)
    evals_dir.mkdir(parents=True, exist_ok=True)
    board_json_path = evals_dir / "leaderboard.json"

    if board_json_path.is_file():
        try:
            leaderboard = json.loads(board_json_path.read_text(encoding="utf-8"))
        except Exception:
            leaderboard = []
    else:
        leaderboard = []

    meta = run_data.get("metadata", {})
    new_entry = {
        "run_id": run_data.get("run_id"),
        "model": meta.get("model", "unknown"),
        "provider": meta.get("provider", "unknown"),
        "timestamp": run_data.get("timestamp"),
        "strict_pass_count": coerce_int(scores_data.get("strict_pass_count", 0)),
        "nuance_score": round(coerce_float(scores_data.get("nuance_score", 0.0)), 1),
        "elapsed_seconds": meta.get("elapsed_seconds", 0.0),
        "cost_usd": meta.get("cost_usd", 0.0),
        "test_scores": scores_data.get("test_scores", {}),
    }

    leaderboard = [e for e in leaderboard if e.get("run_id") != new_entry["run_id"]]
    leaderboard.append(new_entry)
    leaderboard = compute_pareto_badges(leaderboard)

    board_json_path.write_text(json.dumps(leaderboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_content = render_leaderboard_markdown(leaderboard)
    (evals_dir / "LEADERBOARD.md").write_text(md_content, encoding="utf-8")

    print(f"Updated leaderboard at: {board_json_path}")
    print(f"Rendered Markdown table at: {evals_dir / 'LEADERBOARD.md'}")


def main():
    parser = argparse.ArgumentParser(description="Judge and record Vietnamese writing benchmark results.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    blind_parser = subparsers.add_parser("blind", help="Output blinded run payload")
    blind_parser.add_argument("run_file", help="Path to run JSON file")
    blind_parser.add_argument("--output", "-o", help="Optional output path")

    verify_parser = subparsers.add_parser("verify", help="Run deterministic checks on mechanical constraints")
    verify_parser.add_argument("run_file", help="Path to run JSON file")

    record_parser = subparsers.add_parser("record", help="Record judge scores into leaderboard")
    record_parser.add_argument("run_file", help="Path to run JSON file")
    record_parser.add_argument("scores_file", help="Path to judge scores JSON file")
    record_parser.add_argument("--evals-dir", default="./evals", help="Leaderboard directory")

    args = parser.parse_args()

    if args.subcommand == "blind":
        cmd_blind(args)
    elif args.subcommand == "verify":
        cmd_verify(args)
    elif args.subcommand == "record":
        cmd_record(args)


if __name__ == "__main__":
    main()
