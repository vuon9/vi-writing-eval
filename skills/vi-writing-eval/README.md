# vi-writing-eval

A unified skill to benchmark, evaluate, and rank AI language models on Vietnamese text generation tasks.

---

## The golden rule: pure model generation (no tools)

This benchmark evaluates pure autoregressive language generation.

**Candidate models must run with zero tool calls.**
- Turn off code execution, Python sandboxes, function calling schemas, and tool calling bindings.
- Turn off web browsing, web search, and retrieval augmentation.
- Measure only what the neural network generates from its parameters.
- If a candidate output relies on external tools or execution steps, the run is disqualified.

---

## Reasoning models and the token budget

Reasoning models (DeepSeek V4, R1-style models) spend part of the completion budget on hidden reasoning before writing any answer. The visible answer lands in `content`; the thinking lands in `reasoning_content` and never reaches the judge.

If `--max-tokens` is too small, the model can consume the whole budget thinking and return an empty `content` with `finish_reason: "length"`. That looks like model failure but is a harness limit. The default cap is 8192 for this reason.

`run_test.py` records `finish_reason`, `reasoning_tokens`, and `truncated` per test, warns on truncated or empty completions, and counts them in `metadata.unusable_completions`. `verify` reports `non_empty` and `truncated_by_token_cap` per test.

If a run reports truncated or empty completions, raise `--max-tokens` and re-run the model before judging. Never score a truncated run: the empty answer is yours, not the model's.

---

## User prompt cheat sheet

Here are ready-to-use prompts you can give your AI agent:

### 1. Run automated test via local or remote API
```text
Benchmark the model "qwen2.5:7b-instruct" on local Ollama using vi-writing-eval.
```
```text
Run the Vietnamese writing benchmark on "meta-llama/Llama-3.3-70B-Instruct" using my Together API key.
```

### 2. Run manual test on web UI
```text
I want to test Claude 3.7 Web on the Vietnamese writing benchmark. Present the prompts to me one by one and collect my pasted answers.
```

### 3. Check mechanical rules for an existing run
```text
Verify mechanical constraints on the run file "evals/runs/run_latest.json".
```

### 4. Evaluate a run blindly and update leaderboard
```text
Grade the outputs in "evals/runs/run_latest.json" blindly against the 20-point rubric, calculate the score, and update the leaderboard.
```

### 5. Check rankings and trade-offs
```text
Show me the current Vietnamese writing benchmark leaderboard and explain the trade-offs between quality, cost, and speed.
```

---

## Detailed benchmark test cases

All tests use the canonical prompts stored in `references/canonical_suite.json`.

### 1. Poetry and alliteration (`test_1_poetry`)
- **Prompt:**
  > "Hãy viết một bài thơ 4 câu (thể 7 chữ) về chủ đề 'cà phê sáng'.  
  > **Ràng buộc:** Tất cả các từ trong câu thứ 4 đều phải bắt đầu bằng chữ cái **T**."
- **Checkpoints (4 points):**
  1. *Line count:* Exactly 4 lines of poetry. No extra preamble or trailing stanzas.
  2. *Meter:* Exactly 7 words (syllables) per line. Each space-separated unit in Vietnamese is one syllable.
  3. *Theme:* The content adheres directly to the topic of morning coffee ("cà phê sáng").
  4. *Alliteration:* Every word in line 4 starts with the letter **T** (e.g. *"Tách trà thơm tách tách tình"*).

### 2. Prose and negative constraints (`test_2_prose`)
- **Prompt:**
  > "Hãy viết một đoạn văn ngắn (tối đa 3 câu) miêu tả cảm giác của một người lần đầu đi máy bay.  
  > **Ràng buộc:** Không được sử dụng các từ: *máy bay, mây, bầu trời, sợ, thích*."
- **Checkpoints (3 points):**
  1. *Sentence limit:* Maximum 3 sentences total.
  2. *Negative constraint:* Zero occurrences of the forbidden words (*máy bay, mây, bầu trời, sợ, thích*).
  3. *Sensory fidelity:* Accurately evokes the physical feeling and atmosphere of a first flight without relying on the forbidden words.

### 3. Persona and length constraint (`test_3_persona`)
- **Prompt:**
  > "Bạn là một nhân viên hỗ trợ khách hàng cực kỳ lịch sự nhưng chỉ được trả lời bằng **tối đa 15 từ**.  
  > Khách hàng hỏi: 'Tại sao đơn hàng của tôi chưa giao?'. Hãy viết câu phản hồi."
- **Checkpoints (3 points):**
  1. *Word limit:* Maximum 15 words total.
  2. *Persona:* Polite, professional customer service demeanor.
  3. *Relevance:* Directly addresses the order status question rather than deflecting or giving a bare greeting.

### 4. Marketing copywriting (`test_4_marketing`)
- **Prompt:**
  > "Hãy viết 1 đoạn quảng cáo ngắn (dưới 50 từ) giới thiệu dịch vụ giao cà phê tận nơi.  
  > **Ràng buộc:** Phải viết theo cấu trúc AIDA (Attention - Interest - Desire - Action) và mỗi phần chỉ được gói gọn trong đúng **1 câu**."
- **Checkpoints (3 points):**
  1. *Word limit:* Under 50 words total.
  2. *AIDA structure:* Exactly 4 sentences corresponding to the four stages: Attention, Interest, Desire, Action.
  3. *Service message:* Accurately delivers the value proposition of on-demand coffee delivery.

### 5. Business email (`test_5_email`)
- **Prompt:**
  > "Hãy viết một email ngắn từ chối lời mời họp vào 15h chiều nay do trùng lịch.  
  > **Ràng buộc:** Email gồm đúng 3 phần: Tiêu đề, Lời chào, và 2 câu nội dung (câu 1: lý do từ chối + xin lỗi; câu 2: đề xuất khung giờ mới)."
- **Checkpoints (4 points):**
  1. *Layout:* Has both a clear Subject line and a formal Salutation.
  2. *Body length:* Body contains exactly 2 sentences.
  3. *Content allocation:* Sentence 1 contains the apology and schedule conflict. Sentence 2 proposes an alternative time.
  4. *Register:* Polite, standard workplace Vietnamese tone.

### 6. Tone rewrite and keyword (`test_6_rewrite`)
- **Prompt:**
  > "Hãy chuyển câu sau đây sang văn phong **trang trọng/hành chính**: *'Cái ứng dụng này bị lỗi liên tục, làm ơn sửa nhanh lên giùm cái!'*.  
  > **Ràng buộc:** Câu phản hồi chỉ được dài đúng **1 câu** và chứa từ *'hệ thống'*."
- **Checkpoints (3 points):**
  1. *Sentence limit:* Exactly 1 sentence.
  2. *Mandatory keyword:* Contains the word *"hệ thống"*.
  3. *Register transformation:* Shifts the angry, colloquial tone into professional administrative language.

---

## Detailed evaluation and scoring mechanics

### Double-blind evaluation
Model names cause cognitive bias in evaluators. Flagship models often receive lenient scoring, while smaller models are penalized for minor imperfections.

To ensure impartiality:
1. When a test completes, model metadata is recorded inside the run JSON (`metadata` object).
2. The `blind` command produces a stripped payload containing only test IDs, prompts, and completions.
3. The judge evaluates only the blinded payload against the 20 checklist checkpoints.
4. The `record` command recombines the judge scores with the run metadata to update the leaderboard.

### Scoring metrics
- **Strict Pass (0 to 6):** A test only passes if 100% of its checklist checkpoints pass. Failing one word count fails the entire test.
- **Nuance Score (0% to 100%):** Measures partial credit across all 20 individual checkpoints:
  $$\text{Nuance Score} = \left(\frac{\text{Passed Checkpoints}}{20}\right) \times 100\%$$

### Pareto frontier and badges
The leaderboard evaluates quality against cost and latency:
- **`[Quality Crown]`:** Awarded to the model with the highest Nuance Score.
- **`[Free Champion]`:** Awarded to zero-cost models (local or free tier) scoring $\ge 70\%$.
- **`[Speed Demon]`:** Awarded to the fastest model (lowest latency) scoring $\ge 70\%$.

---

## CLI tools

The bundled scripts in `scripts/` require only standard Python 3.

```bash
# 1. Run tests against an OpenAI-compatible endpoint
python3 skills/vi-writing-eval/scripts/benchmark.py test \
  --model qwen2.5:7b-instruct

# 2. Run manual interactive test
python3 skills/vi-writing-eval/scripts/benchmark.py test \
  --manual \
  --model claude-3-7-sonnet-web

# 3. Deterministically verify mechanical constraints
python3 skills/vi-writing-eval/scripts/benchmark.py verify \
  evals/runs/run_example.json

# 4. Extract blinded payload for LLM judge
python3 skills/vi-writing-eval/scripts/benchmark.py blind \
  evals/runs/run_example.json \
  -o evals/runs/blinded.json

# 5. Record judge scores and re-render LEADERBOARD.md
python3 skills/vi-writing-eval/scripts/benchmark.py record \
  evals/runs/run_example.json \
  evals/runs/scores.json \
  --evals-dir ./evals
```
