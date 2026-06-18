# Project Report

This file tracks the project versions, what changed in each version, benchmark status, and follow-up work.

## Version Timeline

| Version | Status | Summary | Main Output |
|---|---|---|---|
| V0 | Done | Scaffold with deterministic mock runtime and initial benchmark flow. | `outputs/sample_run/` |
| V1 | Done | Added OpenAI runtime, runtime abstraction, real token/latency tracking, prompts, and CLI mode selection. | `outputs/llm_smoke_1/` |
| V2 | Planned | Improve evaluator robustness, failure-mode analysis, and full 100-sample LLM benchmark. | TBD |

## Current Score Snapshot

| Run | Dataset | Mode | Records | Autograde |
|---|---|---|---:|---:|
| Mock mini | `data/hotpot_mini.json` | `mock` | 16 | 72/100 |
| Mock 100 seed 42 | `data/hotpot_sample_100_seed42.json` | `mock` | 200 | 92/100 |
| LLM smoke | `data/hotpot_mini.json --limit 1` | `llm` | 2 | 72/100 |

## Version Notes

### V0

Implemented baseline scaffold fixes:
- Completed `JudgeResult` and `ReflectionEntry` schemas.
- Completed Reflexion loop with reflection memory.
- Verified mock benchmark and autograde.
- Added deterministic HotpotQA sampler for 100 examples with seed 42.

### V1

Implemented first API-backed version:
- Added runtime interface.
- Added `MockRuntime` and `OpenAIRuntime`.
- Added OpenAI Responses API calls for Actor, Evaluator, and Reflector.
- Added system prompts.
- Added CLI options: `--mode`, `--model`, `--limit`.
- Added real token and latency tracking for LLM mode.
- Verified LLM smoke test with OpenAI API.

## Next Work

Potential V2 tasks:
- Run full LLM benchmark on 100 examples.
- Improve structured evaluator reliability.
- Improve `failure_modes` report shape so analysis score can reach full points.
- Add retries/backoff around API calls.
- Add cached LLM responses to avoid paying twice for identical runs.
- Add better report discussion generated from actual run statistics.
- Add cost estimation from token usage.

## Commands

Create 100-sample dataset:

```bash
.venv/bin/python scripts/create_hotpot_sample.py \
  --input hotpotqa.json \
  --output data/hotpot_sample_100_seed42.json \
  --sample-size 100 \
  --seed 42
```

Run mock benchmark:

```bash
.venv/bin/python run_benchmark.py \
  --dataset data/hotpot_sample_100_seed42.json \
  --out-dir outputs/sample_100_seed42_v1_mock \
  --mode mock
```

Run LLM smoke test:

```bash
.venv/bin/python run_benchmark.py \
  --dataset data/hotpot_mini.json \
  --out-dir outputs/llm_smoke_1 \
  --mode llm \
  --limit 1
```

Run full LLM benchmark:

```bash
.venv/bin/python run_benchmark.py \
  --dataset data/hotpot_sample_100_seed42.json \
  --out-dir outputs/llm_run_100 \
  --mode llm
```
