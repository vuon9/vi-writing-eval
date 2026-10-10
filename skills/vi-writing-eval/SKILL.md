---
name: vi-writing-eval
description: Use when testing or evaluating AI models on Vietnamese writing benchmarks, scoring text generation quality without tools, or updating leaderboard rankings.
---

# Vietnamese Writing Evaluation

A unified benchmark skill to test and judge AI language models on Vietnamese text generation tasks across strict formatting, meter, negative constraints, and tone.

## Golden rule: pure model generation (no tools)

This benchmark evaluates raw autoregressive language capability.

**Candidate models must run with zero tool calls.**
- Do not provide tools, function calling schemas, or code interpreters.
- Turn off web browsing and search plugins.
- Test only what the model generates from its internal weights.
- If a candidate output relies on tools, that run is disqualified.

## User prompt cheat sheet

When the user asks for benchmark tasks, identify which step they want and execute accordingly:

### 1. Test an automated API model (Ollama, vLLM, OpenRouter)
> *"Benchmark the model `qwen2.5:7b-instruct` running on my local Ollama."*
> *"Run the Vietnamese writing test on `meta-llama/Llama-3.3-70B` using Together API."*

Execute:
```bash
python3 skills/vi-writing-eval/scripts/benchmark.py test --model <model-name>
```

### 2. Test a web UI model interactively
> *"I want to test Claude 3.7 in the web browser on the Vietnamese writing test. Give me the prompts one by one."*

Execute:
```bash
python3 skills/vi-writing-eval/scripts/benchmark.py test --manual --model <model-name>
```
Or present each of the 6 prompts from `references/canonical_suite.json` in chat, remind the user to disable web search/plugins, collect raw completions, and save to `./evals/runs/run_<timestamp>_<hash>.json`.

### 3. Verify mechanical constraints
> *"Check if this run passed the hard rules: `evals/runs/run_example.json`."*

Execute:
```bash
python3 skills/vi-writing-eval/scripts/benchmark.py verify evals/runs/run_example.json
```

### 4. Grade a run blindly and update leaderboard
> *"Evaluate the latest benchmark run in `evals/runs/` and update the leaderboard."*

Execute:
1. Strip metadata to keep evaluation double-blind:
   ```bash
   python3 skills/vi-writing-eval/scripts/benchmark.py blind evals/runs/<run-file>.json -o evals/runs/blinded.json
   ```
2. Grade the completions against the 20-point rubric in `README.md` (via LLM judge or agent review).
3. Save the scores into `evals/runs/scores.json`.
4. Update the leaderboard:
   ```bash
   python3 skills/vi-writing-eval/scripts/benchmark.py record evals/runs/<run-file>.json evals/runs/scores.json
   ```

### 5. Check rankings and trade-offs
> *"Show me the current Vietnamese writing leaderboard."*

Read and present `./evals/LEADERBOARD.md`, highlighting:
- Top Nuance Score (`[Quality Crown]`)
- Best zero-cost option (`[Free Champion]`)
- Fastest model (`[Speed Demon]`)

---

## Canonical benchmark tests

All tests come from `references/canonical_suite.json`:

1. **Poetry and alliteration (`test_1_poetry`):** 4 lines, exactly 7 words per line, theme "cà phê sáng", all words in line 4 start with letter T.
2. **Prose and negative constraints (`test_2_prose`):** Up to 3 sentences describing a first flight, forbidden words: *máy bay, mây, bầu trời, sợ, thích*.
3. **Persona and length limit (`test_3_persona`):** Polite customer service representative, max 15 words, answering why an order is delayed.
4. **Marketing copywriting (`test_4_marketing`):** Under 50 words, exactly 4 sentences matching AIDA structure, on-demand coffee delivery.
5. **Business email (`test_5_email`):** Subject, Salutation, exactly 2 body sentences (apology/conflict, then new proposed time).
6. **Tone rewrite (`test_6_rewrite`):** Exactly 1 sentence, formal administrative tone, must include keyword "hệ thống".

## Scoring formula

- **Strict Pass (0 to 6):** 1 point per test only when 100% of checklist items are satisfied.
- **Nuance Score (0% to 100%):** $\frac{\text{Passed Checkpoints}}{20} \times 100\%$.
- **Pareto badges:**
  - `[Quality Crown]`: Highest overall Nuance Score.
  - `[Free Champion]`: Score $\ge 70\%$ at $0 cost.
  - `[Speed Demon]`: Lowest latency with score $\ge 70\%$.
