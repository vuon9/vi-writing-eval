#!/usr/bin/env python3
"""Add or replace one entry in leaderboard.json from a run and its judge scores.

Usage:
    python3 scripts/ingest.py \
        --run runs/run_20261010_150255_c81ff9.json \
        --scores scores/strict_scores_run_20261010_150255_c81ff9.json \
        --judge-model deepseek-v4-pro \
        --judge-protocol evidence-quoted-v1

The run file supplies model identity, latency, and cost. The scores file supplies
the judged verdicts. Judge model and protocol are recorded on the entry, because a
score is not comparable across different judges or different judging protocols.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "leaderboard.json"

REQUIRED_SCORE_FIELDS = ("strict_pass_count", "nuance_score", "test_scores")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: {path} is not valid JSON: {exc}")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def build_entry(run: dict, scores: dict, args) -> dict:
    meta = run.get("metadata") or {}
    if not meta.get("model"):
        raise SystemExit("error: run file has no metadata.model")
    missing = [f for f in REQUIRED_SCORE_FIELDS if f not in scores]
    if missing:
        raise SystemExit(f"error: scores file is missing: {', '.join(missing)}")

    outputs = run.get("outputs") or []
    return {
        "run_id": run.get("run_id", args.run.stem),
        "model": meta["model"],
        "provider": meta.get("provider", "unknown"),
        "timestamp": run.get("timestamp"),
        "strict_pass_count": scores["strict_pass_count"],
        "nuance_score": round(float(scores["nuance_score"]), 1),
        "elapsed_seconds": meta.get("elapsed_seconds", 0.0),
        "cost_usd": meta.get("cost_usd", 0.0),
        "prompt_tokens": meta.get("prompt_tokens", 0),
        "completion_tokens": meta.get("completion_tokens", 0),
        "reasoning_tokens": sum(o.get("reasoning_tokens", 0) for o in outputs),
        "judge": {
            "model": args.judge_model,
            "protocol": args.judge_protocol,
        },
        "source_run": rel(args.run),
        "source_scores": rel(args.scores),
        "test_scores": scores["test_scores"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="run JSON from vi-writing-eval")
    parser.add_argument("--scores", required=True, type=Path, help="judge scores JSON")
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--judge-protocol", required=True)
    args = parser.parse_args()

    run_path = args.run if args.run.is_absolute() else (ROOT / args.run)
    scores_path = args.scores if args.scores.is_absolute() else (ROOT / args.scores)
    args.run, args.scores = run_path, scores_path

    run = load_json(run_path)
    scores = load_json(scores_path)

    # The scores filename carries the run id in the documented workflow; flag a mismatch
    # so a copy-paste slip cannot silently attach the wrong verdicts to a model.
    run_id = run.get("run_id", run_path.stem)
    if run_id not in scores_path.stem:
        print(
            f"warning: run_id {run_id!r} does not appear in the scores filename "
            f"{scores_path.name!r}; double-check they belong together",
            file=sys.stderr,
        )

    entry = build_entry(run, scores, args)

    if DATA.is_file():
        existing = load_json(DATA)
        entries = existing.get("entries") if isinstance(existing, dict) else existing
    else:
        entries = []

    entries = [e for e in entries if e.get("run_id") != entry["run_id"]]
    entries.append(entry)
    entries.sort(key=lambda e: (-e.get("nuance_score", 0.0), e.get("model", "")))

    DATA.write_text(
        json.dumps({"entries": entries}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Recorded {entry['model']} (strict {entry['strict_pass_count']}, "
        f"nuance {entry['nuance_score']}%, judge {entry['judge']['model']}). "
        f"{len(entries)} entries in {DATA.name}."
    )
    print("Now run: python3 scripts/render.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
