#!/usr/bin/env python3
"""Unified benchmark CLI for Vietnamese writing evaluation."""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(
        description="Unified CLI for testing and judging Vietnamese writing benchmarks."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # test
    test_parser = subparsers.add_parser("test", help="Run benchmark tests against a model")
    test_parser.add_argument("--model", help="Model name")
    test_parser.add_argument("--base-url", help="OpenAI-compatible base URL")
    test_parser.add_argument("--api-key", help="API key")
    test_parser.add_argument("--provider", help="Provider label (e.g. ollama, vllm, openrouter)")
    test_parser.add_argument("--suite", help="Path to a custom suite JSON")
    test_parser.add_argument("--temperature", type=float, help="Sampling temperature")
    test_parser.add_argument("--max-tokens", type=int, help="Maximum completion tokens")
    test_parser.add_argument("--timeout", type=int, help="HTTP timeout in seconds")
    test_parser.add_argument("--cost-per-1m-in", type=float, help="USD cost per 1M input tokens")
    test_parser.add_argument("--cost-per-1m-out", type=float, help="USD cost per 1M output tokens")
    test_parser.add_argument("--manual", action="store_true", help="Manual copy-paste mode")
    test_parser.add_argument("--out-dir", default="./evals/runs", help="Output directory")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Check mechanical constraints deterministically")
    verify_parser.add_argument("run_file", help="Path to run JSON file")

    # blind
    blind_parser = subparsers.add_parser("blind", help="Produce blinded run payload for LLM judge")
    blind_parser.add_argument("run_file", help="Path to run JSON file")
    blind_parser.add_argument("--output", "-o", help="Optional output path")

    # record
    record_parser = subparsers.add_parser("record", help="Record judge scores into leaderboard")
    record_parser.add_argument("run_file", help="Path to run JSON file")
    record_parser.add_argument("scores_file", help="Path to judge scores JSON file")
    record_parser.add_argument("--evals-dir", default="./evals", help="Leaderboard directory")

    args = parser.parse_args()

    if args.command == "test":
        cmd = [sys.executable, str(SCRIPTS_DIR / "run_test.py")]
        passthrough = (
            ("--model", args.model),
            ("--base-url", args.base_url),
            ("--api-key", args.api_key),
            ("--provider", args.provider),
            ("--suite", args.suite),
            ("--temperature", args.temperature),
            ("--max-tokens", args.max_tokens),
            ("--timeout", args.timeout),
            ("--cost-per-1m-in", args.cost_per_1m_in),
            ("--cost-per-1m-out", args.cost_per_1m_out),
        )
        for flag, value in passthrough:
            if value is not None:
                cmd.extend([flag, str(value)])
        if args.manual:
            cmd.append("--manual")
        if args.out_dir:
            cmd.extend(["--out-dir", args.out_dir])
        subprocess.run(cmd, check=True)

    elif args.command == "verify":
        cmd = [sys.executable, str(SCRIPTS_DIR / "judge_run.py"), "verify", args.run_file]
        subprocess.run(cmd, check=True)

    elif args.command == "blind":
        cmd = [sys.executable, str(SCRIPTS_DIR / "judge_run.py"), "blind", args.run_file]
        if args.output:
            cmd.extend(["--output", args.output])
        subprocess.run(cmd, check=True)

    elif args.command == "record":
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "judge_run.py"),
            "record",
            args.run_file,
            args.scores_file,
            "--evals-dir",
            args.evals_dir,
        ]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
