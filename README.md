# vi-writing-leaderboard

Benchmark results for Vietnamese text generation, measured with the `vi-writing-eval` skill.

Models are run against six constraint-heavy Vietnamese writing tests: a 7-word-per-line poem with a letter constraint, prose under a forbidden-word list, a 15-word customer support reply, an AIDA ad under 50 words, a two-sentence business email, and a register rewrite.

Every number here comes from a real run. Raw evidence lives in `runs/` and `scores/`.

## What is measured

Each test carries a checklist of 3 to 4 items, 20 in total. Two scores are reported:

- **Strict pass** counts tests where every checklist item passed.
- **Nuance** is the share of individual checklist items that passed.

A model that misses one letter is not the same as a model that ignores the rules, so both numbers are shown.

## How runs are made

1. The candidate model is called with **no tools**. Every request sends `tools: []` and `tool_choice: "none"`. Web search, code execution, and plugins are off for manual runs. A run that used a tool is disqualified.
2. The candidate's identity is stripped before judging. The judge sees only the prompt and the completion.
3. A judge model grades each checklist item and must quote the exact text that satisfies it. A pass with no quote, or with a quote that is not present in the completion, is downgraded to a fail in code. This guard exists because an agreeable judge awarded 20 out of 20 items to every model on the first attempt, including to itself.

The judge model and protocol are recorded on every entry. A score is not comparable across different judges or different judging protocols.

## Reproduce a run

```bash
python3 /path/to/vstack/skills/vi-writing-eval/scripts/benchmark.py test \
  --base-url https://api.deepseek.com \
  --provider deepseek \
  --model deepseek-flash \
  --cost-per-1m-in 0.30 --cost-per-1m-out 1.20 \
  --out-dir runs
```

Then judge the run blind and ingest the verdicts:

```bash
python3 scripts/ingest.py \
  --run runs/run_example.json \
  --scores scores/run_example.json \
  --judge-model <judge> \
  --judge-protocol evidence-quoted-v1
python3 scripts/render.py
```

## Scoring caveats

- The current suite has a low ceiling. Strong models pass nearly every item, so the board separates them only on one or two checkpoints.
- Latency is wall clock for all six tests, including hidden reasoning tokens. Reasoning-heavy models look slower and cost more, because reasoning tokens are billed and timed.
- Cost uses list prices supplied at run time, not a live price feed.

<!-- LEADERBOARD:START -->

## Leaderboard

2 model runs, judged blind against the 20-point rubric.

| Rank | Model | Provider | Strict pass | Nuance | Latency | Cost | Judge | Badges |
|:--:|:--|:--|:--:|:--:|--:|--:|:--|:--|
| 1 | **deepseek-flash** | deepseek | 6/6 | 100.0% | 29.2s | $0.0074 | deepseek-v4-pro | `[Quality Crown]`, `[Speed Demon]` |
| 2 | **deepseek-v4-pro** | deepseek | 5/6 | 95.0% | 137.2s | $0.0508 | deepseek-v4-pro | none |

## Per-test result

| Model | test_1_poetry | test_2_prose | test_3_persona | test_4_marketing | test_5_email | test_6_rewrite |
|:--|:--:|:--:|:--:|:--:|:--:|:--:|
| **deepseek-flash** | pass | pass | pass | pass | pass | pass |
| **deepseek-v4-pro** | pass | pass | fail (2/3) | pass | pass | pass |

## Failed checkpoints

| Model | Test | Failed checkpoint | Judge reason |
|:--|:--|:--|:--|
| **deepseek-v4-pro** | test_3_persona | Trả lời đúng trọng tâm câu hỏi của khách hàng. | Không nêu lý do thực tế; chỉ bảo đang kiểm tra. |

## Badge legend

- `[Quality Crown]` highest Nuance score on the board.
- `[Free Champion]` zero cost and Nuance at or above 70%.
- `[Speed Demon]` lowest latency among runs at or above 70% Nuance.

<!-- LEADERBOARD:END -->
