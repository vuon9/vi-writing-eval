#!/usr/bin/env python3
"""Run Vietnamese writing benchmark tests against a target model or via manual input."""

import argparse
import datetime
import hashlib
import http.client
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

DEFAULT_SUITE_PATH = Path(__file__).resolve().parent.parent / "references" / "canonical_suite.json"

# Reasoning models spend part of the completion budget on hidden reasoning before
# emitting any answer text. A low cap can produce finish_reason="length" with an
# empty completion, which would be scored as a model failure rather than a
# harness limit. This default leaves room for reasoning plus the answer.
DEFAULT_MAX_TOKENS = 8192


def call_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = 120,
) -> dict:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}': only http and https are allowed")

    if not parsed.hostname:
        raise ValueError(f"Missing host in URL: {base_url}")
    host: str = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    path = f"{parsed.path.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tools": [],
        "tool_choice": "none",
    }
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.time()
    conn = (
        http.client.HTTPSConnection(host, port=port, timeout=timeout)
        if parsed.scheme == "https"
        else http.client.HTTPConnection(host, port=port, timeout=timeout)
    )
    try:
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        raw_data = response.read().decode("utf-8")
        elapsed = time.time() - start

        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status} calling {base_url}: {raw_data}")

        res_json = json.loads(raw_data)
        choice = res_json.get("choices", [{}])[0]
        message = choice.get("message", {})
        completion = (message.get("content") or "").strip()
        reasoning = message.get("reasoning_content") or ""
        finish_reason = choice.get("finish_reason")
        usage = res_json.get("usage", {})
        details = usage.get("completion_tokens_details") or {}
        return {
            "completion": completion,
            "elapsed": elapsed,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": details.get("reasoning_tokens", 0),
            "reasoning_chars": len(reasoning),
            "finish_reason": finish_reason,
            # A truncated answer is a harness limit, not a model failure. Empty
            # content is always unusable, whatever the reason.
            "truncated": finish_reason == "length",
            "empty": not completion,
        }
    finally:
        conn.close()


def run_automated(args, suite_tests: list[dict]) -> dict:
    base_url = args.base_url or os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    api_key = args.api_key or os.getenv("OPENAI_API_KEY", "")
    model = args.model

    print(f"Running automated benchmark for model: {model}")
    print(f"Endpoint: {base_url}")
    print("Pure model generation: tools disabled (tools: [], tool_choice: 'none')")
    print(f"Tests in suite: {len(suite_tests)}\n")

    outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_time = 0.0
    unusable = 0

    for idx, test in enumerate(suite_tests, 1):
        test_id = test.get("id", f"test_{idx}")
        title = test.get("title", f"Test {idx}")
        prompt = test.get("prompt", "")

        print(f"[{idx}/{len(suite_tests)}] {title}...")
        res = call_chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=model,
            prompt=prompt,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )

        outputs.append({
            "test_id": test_id,
            "title": title,
            "prompt": prompt,
            "completion": res["completion"],
            "elapsed_seconds": round(res["elapsed"], 2),
            "prompt_tokens": res["prompt_tokens"],
            "completion_tokens": res["completion_tokens"],
            "reasoning_tokens": res["reasoning_tokens"],
            "finish_reason": res["finish_reason"],
            "truncated": res["truncated"],
        })

        total_prompt_tokens += res["prompt_tokens"]
        total_completion_tokens += res["completion_tokens"]
        total_time += res["elapsed"]
        print(f"    Done in {res['elapsed']:.2f}s ({res['completion_tokens']} tokens)")

        if res["truncated"] or res["empty"]:
            unusable += 1
            reason = "truncated" if res["truncated"] else "empty"
            print(
                f"    WARNING: {reason} completion ({res['reasoning_tokens']} reasoning tokens, "
                f"finish_reason={res['finish_reason']}). Raise --max-tokens and re-run this model."
            )

    cost_in = (total_prompt_tokens / 1_000_000) * args.cost_per_1m_in
    cost_out = (total_completion_tokens / 1_000_000) * args.cost_per_1m_out
    total_cost = round(cost_in + cost_out, 6)

    if unusable:
        print(
            f"\n{unusable} of {len(suite_tests)} completions were truncated or empty. "
            "Those are harness limits, not model quality. Re-run with a higher --max-tokens "
            "before judging this run."
        )

    return {
        "metadata": {
            "model": model,
            "provider": args.provider or "openai-compatible",
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "elapsed_seconds": round(total_time, 2),
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "cost_usd": total_cost,
            "unusable_completions": unusable,
        },
        "outputs": outputs,
    }


def run_manual(args, suite_tests: list[dict]) -> dict:
    model = args.model or input("Enter candidate model name: ").strip()
    print(f"\nManual test mode for model: {model}")
    print("Ensure all tools, plugins, and browsing are switched OFF in the model's UI.")
    print("For each test, paste the prompt into the target model and paste the response back here.")
    print("Terminate each response input by entering an empty line followed by EOF (Ctrl+D) or '---END---'.\n")

    outputs = []
    start_total = time.time()

    for idx, test in enumerate(suite_tests, 1):
        test_id = test.get("id", f"test_{idx}")
        title = test.get("title", f"Test {idx}")
        prompt = test.get("prompt", "")

        print("=" * 60)
        print(f"[{idx}/{len(suite_tests)}] {title}")
        print("Prompt:")
        print(prompt)
        print("-" * 60)
        print("Paste the model's completion (type '---END---' on a newline when done):")

        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "---END---":
                break
            lines.append(line)

        completion = "\n".join(lines).strip()
        outputs.append({
            "test_id": test_id,
            "title": title,
            "prompt": prompt,
            "completion": completion,
            "elapsed_seconds": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "finish_reason": "manual",
            "truncated": False,
        })

    elapsed = round(time.time() - start_total, 2)
    return {
        "metadata": {
            "model": model,
            "provider": args.provider or "manual-web",
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "elapsed_seconds": elapsed,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "unusable_completions": 0,
        },
        "outputs": outputs,
    }


def save_run(run_data: dict, out_dir: Path, suite_name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    hash_suffix = hashlib.sha256(f"{ts_str}_{run_data['metadata']['model']}".encode()).hexdigest()[:6]
    run_id = f"run_{ts_str}_{hash_suffix}"

    full_payload = {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "suite": suite_name,
        "metadata": run_data["metadata"],
        "outputs": run_data["outputs"],
    }

    file_path = out_dir / f"{run_id}.json"
    file_path.write_text(json.dumps(full_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return file_path


def main():
    parser = argparse.ArgumentParser(description="Run Vietnamese writing benchmark tests.")
    parser.add_argument("--model", help="Model name (e.g. qwen2.5:7b, gpt-4o-mini)")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--provider", help="Provider label (e.g. ollama, vllm, openrouter)")
    parser.add_argument("--suite", default=str(DEFAULT_SUITE_PATH), help="Path to suite JSON")
    parser.add_argument("--out-dir", default="./evals/runs", help="Output directory for run files")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS, help="Maximum completion tokens (must cover hidden reasoning for reasoning models)")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout in seconds")
    parser.add_argument("--cost-per-1m-in", type=float, default=0.0, help="USD cost per 1M input tokens")
    parser.add_argument("--cost-per-1m-out", type=float, default=0.0, help="USD cost per 1M output tokens")
    parser.add_argument("--manual", action="store_true", help="Manual copy-paste interactive mode")

    args = parser.parse_args()

    suite_path = Path(args.suite)
    if not suite_path.is_file():
        print(f"Error: Suite file not found at {suite_path}", file=sys.stderr)
        sys.exit(1)

    try:
        suite_tests = json.loads(suite_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error reading suite file: {exc}", file=sys.stderr)
        sys.exit(1)

    if not args.manual and not args.model:
        print("Error: --model is required for automated test runs. Use --manual for manual input.", file=sys.stderr)
        sys.exit(1)

    if args.manual:
        run_data = run_manual(args, suite_tests)
    else:
        run_data = run_automated(args, suite_tests)

    out_dir = Path(args.out_dir)
    suite_name = suite_path.stem
    saved_path = save_run(run_data, out_dir, suite_name)
    print(f"\nSaved run file to: {saved_path}")
    print(f"Run ID: {saved_path.stem}")
    print("Pass this file to judge_run.py for evaluation.")


if __name__ == "__main__":
    main()
