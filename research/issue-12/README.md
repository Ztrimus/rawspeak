# Issue #12 — Dictation accuracy research

Research-only branch (`research/#12/noisy-speech-accuracy-experiments`). No
production code under `rawspeak/` is changed here.

See [`../../.cursor/plans/issue_12_dictation_accuracy_research_*.plan.md`](../..)
for the full plan. This README is the operational guide.

## What lives here

```
research/issue-12/
  README.md          this file
  bench.py           runs (transcriber, vad, cleanup) configs over samples/
  references.json    per-sample ground truth + ideal AI-prompt cleaned form
  samples/           short WAV files (you record / seed via macOS `say`)
  results/           per-run JSON + markdown summaries (gitignored output)
  report.md          running log of experiments + final recommendations
  seed_samples.sh    bootstrap synthetic samples via macOS `say`
  glossary.example.txt example hotwords list for Experiment 3
```

## Setup

```bash
# from repo root
.venv/bin/pip install -r research/issue-12/requirements.txt
```

`requirements.txt` deliberately separates research deps from the runtime app
deps so we don't bloat the shipped binary.

## Building a test set

You need 8–15 short WAVs (5–60s, mono, 16 kHz) covering the failure modes
listed in issue #12. Two ways to seed:

1. **Real recordings (preferred for final numbers).** Record yourself with
   `rawspeak`'s mic at the conditions below. Save as
   `samples/<id>.wav` (mono, 16 kHz). Add an entry to `references.json`.

2. **Synthetic bootstrap via macOS `say` (good enough to wire the harness).**
   Run `bash research/issue-12/seed_samples.sh`. This produces a small set of
   synthetic samples so `bench.py` runs end-to-end before you record. They are
   *not* representative of real noisy speech — replace with recordings for
   final decisions.

### Coverage targets for the recorded set

| tag         | what to capture                              |
| ----------- | -------------------------------------------- |
| `clean`     | quiet room, normal pace                      |
| `slow`      | deliberately slow speech                     |
| `fillers`   | "um", "uh", "you know", "I mean", false starts |
| `lists`     | "first ... second ... third ..."             |
| `jargon`    | proper nouns / internal terms / brand names  |
| `noisy-bg`  | typing / music / café noise underneath       |
| `silence`   | long silent gaps between phrases             |

## Running an experiment

```bash
# Baseline: current pipeline (HF transformers + whisper-base + current cleanup)
.venv/bin/python research/issue-12/bench.py \
    --transcriber hf-base \
    --cleanup current \
    --label baseline

# Experiment 1: ASR engine swap
.venv/bin/python research/issue-12/bench.py \
    --transcriber faster-distil-large-v3 \
    --cleanup current \
    --label exp1-distil-large-v3

# Experiment 4: constrained cleanup
.venv/bin/python research/issue-12/bench.py \
    --transcriber hf-base \
    --cleanup light-edit \
    --label exp4-light-edit

# Experiment 2: VAD silence-trim policy
.venv/bin/python research/issue-12/bench.py \
    --transcriber faster-distil-large-v3 \
    --vad silero-trim \
    --cleanup light-edit \
    --label exp2-vad

# Experiment 3: hotwords
.venv/bin/python research/issue-12/bench.py \
    --transcriber faster-distil-large-v3 \
    --hotwords research/issue-12/glossary.example.txt \
    --label exp3-hotwords

# Experiment 5: speech enhancement (expected to lose)
.venv/bin/python research/issue-12/bench.py \
    --transcriber faster-distil-large-v3 \
    --enhance deepfilternet \
    --label exp5-enhance

# Experiment 6: rule-based-only cleanup
.venv/bin/python research/issue-12/bench.py \
    --transcriber faster-distil-large-v3 \
    --cleanup rule-based \
    --label exp6-rule-only
```

Each run writes `results/<label>.json` and appends a row to `report.md`.

## Metrics

- **WER (raw)** — raw transcript vs `ground_truth`. Measures ASR quality.
- **WER (cleaned)** — cleaned text vs `ideal`. Measures end-to-end output quality.
- **Drift** — `1 - (content_words(raw) ∩ content_words(cleaned)) / content_words(raw)`.
  High drift = LLM is paraphrasing / inventing — bad for "send to AI" use case.
- **Latency** — per-stage seconds (record-to-paste budget is ~700ms in Wispr Flow).

## Decision rule

A change ships only if, vs the immediately prior winner on the same harness:

- `WER cleaned` improves OR is within +0.5pp **and**
- `Drift` does not regress **and**
- `Latency` stays within budget (define per stage in `report.md`).
