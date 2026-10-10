#!/usr/bin/env python3
"""Shared reading, ranking, and formatting for the leaderboard.

Imported by render.py (README tables) and reports.py (per-model reports) so the
two views can never disagree about what the data says.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "leaderboard.json"
REPORTS_DIR = ROOT / "reports"

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
_EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)


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


def _run_time(entry: dict) -> datetime:
    raw = entry.get("timestamp") or ""
    if not raw:
        return _EPOCH
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def latest_per_model(entries: list[dict]) -> list[dict]:
    """One entry per model: the most recent run.

    Re-testing a model must replace its row rather than add a duplicate, so the
    table, the reports, and the badges all describe the same current state.
    The run history stays in leaderboard.json and in git.
    """
    newest: dict[str, dict] = {}
    for entry in entries:
        model = entry["model"]
        current = newest.get(model)
        if current is None or (_run_time(entry), str(entry.get("run_id", ""))) > (
            _run_time(current),
            str(current.get("run_id", "")),
        ):
            newest[model] = entry
    return list(newest.values())


def slugify(model: str) -> str:
    """Filesystem-safe, stable name for a model's report file."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(model).lower()).strip("-")
    return slug or "model"


def compute_badges(entries: list[dict]) -> None:
    """Award badges in place. Recomputed on every render, never trusted from the file."""
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


def total_tests(entry: dict) -> int:
    return len(entry["test_scores"])


def cell(value: object) -> str:
    """Escape a value for a markdown table cell, collapsing newlines."""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text.replace("|", "\\|")


def truncate(value: object, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def fmt_money(entry: dict) -> str:
    return "Free" if entry["cost_usd"] == 0 else f"${entry['cost_usd']:.4f}"


def badge_text(entry: dict) -> str:
    return ", ".join(f"`[{b}]`" for b in entry.get("badges", [])) or "none"


def ranked(entries: list[dict]) -> list[dict]:
    return sorted(
        entries,
        key=lambda e: (e["nuance_score"], e["strict_pass_count"], -e["elapsed_seconds"]),
        reverse=True,
    )


def fence(text: str, language: str = "text") -> str:
    """Fence arbitrary text, using a longer fence than any backtick run inside it."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{language}\n{text.rstrip()}\n{ticks}"
