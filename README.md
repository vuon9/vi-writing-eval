# vi-writing-eval

A Vietnamese writing benchmark for language models, plus the leaderboard of results it produces.

Two things live here:

- **`skills/vi-writing-eval/`** the skill. It runs six constraint-heavy Vietnamese writing tests, verifies the mechanical rules, and judges the output blind.
- **`leaderboard.json`, `runs/`, `scores/`** the results. Every number in the tables below comes from a real run, with the raw completions kept as evidence.

## What is measured

Models are run against six tests: a 7-word-per-line poem with a leading-letter constraint, prose under a forbidden-word list, a 15-word customer support reply, an AIDA ad under 50 words, a two-sentence business email, and a register rewrite.

Each test carries a checklist of 3 to 4 items, 20 in total. Two scores are reported:

- **Strict pass** counts tests where every checklist item passed.
- **Nuance** is the share of individual checklist items that passed.

A model that misses one letter is not the same as a model that ignores the rules, so both numbers are shown.

## How runs are made

1. The candidate model is called with **no tools**. Every request sends `tools: []` and `tool_choice: "none"`. Web search, code execution, and plugins are off for manual runs. A run that used a tool is disqualified.
2. The candidate's identity is stripped before judging. The judge sees only the prompt and the completion.
3. The judge must quote the exact text that satisfies each checklist item. A pass with no quote, or with a quote that is not present in the completion, is downgraded to a fail in code. This guard exists because an agreeable judge awarded 20 out of 20 items to every model on the first attempt, including to its own output.

The judge model and protocol are recorded on every entry. A score is not comparable across different judges or different judging protocols.

## Reproduce a run

```bash
python3 skills/vi-writing-eval/scripts/benchmark.py test \
  --base-url https://api.deepseek.com \
  --provider deepseek \
  --model deepseek-flash \
  --cost-per-1m-in 0.30 --cost-per-1m-out 1.20 \
  --out-dir runs
```

Then judge the run blind, ingest the verdicts, and re-render the tables:

```bash
python3 skills/vi-writing-eval/scripts/benchmark.py blind runs/run_example.json -o /tmp/blinded.json
python3 scripts/ingest.py \
  --run runs/run_example.json \
  --scores scores/run_example.json \
  --judge-model <judge> \
  --judge-protocol evidence-quoted-v1
python3 scripts/render.py
```

`scripts/render.py` only rewrites the region between the `LEADERBOARD` markers, so the prose in this file is safe to edit by hand. CI regenerates that region on every data change, and fails a pull request whose tables are stale.

## Scoring caveats

- The current suite has a low ceiling. Strong models pass nearly every item, so the board separates them only on one or two checkpoints.
- Latency is wall clock for all six tests, including hidden reasoning tokens. Reasoning-heavy models look slower and cost more, because reasoning tokens are billed and timed.
- Cost uses list prices supplied at run time, not a live price feed.

## Author and license

Author: [vuon9](https://github.com/vuon9). MIT licensed, see [LICENSE](LICENSE).

<!-- LEADERBOARD:START -->

## Leaderboard

2 model runs, judged blind against the 20-point rubric.

| Rank | Model | Provider | Strict pass | Nuance | Latency | Cost | Judge | Protocol | Badges |
|:--:|:--|:--|:--:|:--:|--:|--:|:--|:--|:--|
| 1 | **deepseek-flash** | deepseek | 6/6 | 100.0% | 29.2s | $0.0074 | deepseek-v4-pro | evidence-quoted-v1 | `[Quality Crown]`, `[Speed Demon]` |
| 2 | **deepseek-v4-pro** | deepseek | 5/6 | 95.0% | 137.2s | $0.0508 | deepseek-v4-pro | evidence-quoted-v1 | none |

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

Scores are only comparable between rows that share a judge and protocol.

<!-- LEADERBOARD:END -->
