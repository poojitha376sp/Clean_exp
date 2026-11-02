# Clean_exp — SRS → 3-gate test generation → execution against real code

A clean rebuild of the test-generation experiment. The original pipeline in
`../pipeline_automated/` is left untouched as a reference; the gate logic
(RSS m1–m10 tables, SFV validators, FSA weights, groundedness) is ported from it.

Full step-by-step rationale (what / why / pros / cons / what to observe):
**[docs/PIPELINE.md](docs/PIPELINE.md)**.

## Setup
```bash
cd Clean_exp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt     # Python 3.12 recommended, see "Python versions"
cp .env.example ../.env     # the .env goes in the folder ABOVE the repo; fill in only what you need
```
`../.env` holds optional secrets (SSH details for a remote GPU server, API keys for the hosted-provider smoke tests). It is read from one level above the repo so it can never be committed by accident. **Prefer SSH-key authentication** (`GPU_SSH_KEY`); `GPU_PASS` is an optional fallback. With a local GPU you need no secrets at all. Providers and models: `config.yaml`.

## Inputs
```
inputs/<project>/
    srs/            the SRS (PDF / DOCX / MD / TXT; several files are fine)
    code/           the implementation
    project.yaml    optional: language, framework, setup, test_cmd (see tcgen/execute.py)
```

### Case-study SRS and code sources (reproducibility)
The original SRS source files AND the exact implementation code executed against
in S6 are archived in this repo under `inputs/<project>/`, pinned to the commit
each benchmark run actually used, so results can be independently re-verified
(not just re-analyzed from the saved JSON):

| project | SRS source | code source | pinned commit | license |
|---|---|---|---|---|
| doorstop | `inputs/doorstop/srs/raw/*.yml` (doorstop's own native requirement format) | [doorstop-dev/doorstop](https://github.com/doorstop-dev/doorstop) | `36fc0fd` | LGPL-3.0 |
| ventilator | `inputs/ventilator/srs/SRS.rst` | [RespiraWorks/Ventilator](https://github.com/RespiraWorks/Ventilator) (only `software/`, the subtree the pipeline was ever pointed at) | `6165c82` | Apache-2.0 |
| virtual_clinic | `inputs/virtual_clinic/srs/Software Requirements Specification.pdf` | [mishal23/virtual-clinic](https://github.com/mishal23/virtual-clinic) | `b8241e5` | MIT |

`inputs/<project>/code/` is a snapshot of each repo's working tree at that commit
(no `.git` history), kept with its original LICENSE for attribution.

## Run
```bash
.venv/bin/python -m tcgen.run --project <project>                         # all stages, all generators
.venv/bin/python -m tcgen.run --project <project> --stages S0,S1           # extract, then check S1 by hand
.venv/bin/python -m tcgen.run --project <project> --stages S2,S3 --gen groq:openai/gpt-oss-20b
.venv/bin/python -m tcgen.run --project <project> --stages S6,S7
```
Everything lands in `runs/<project>/` (results are committed; only the S6 scratch workspaces are git-excluded). The final table is `runs/<project>/S7_report.md`.
LLM calls are cached by prompt hash in `.cache/llm`, so re-runs are free and identical.
This cache (3,570 raw `{prompt spec, response text}` pairs) is committed, so a rerun
replays the exact responses actually returned during the benchmark without calling
any model — the one part of the pipeline that is genuinely bit-for-bit reproducible,
independent of model/runtime drift (see Threats to Validity for what still isn't).

To run the whole experiment (all models x all projects) on the GPU server, see **[tools/README.md](tools/README.md)** (`tools/run_experiment.sh`). Gate weights, thresholds and their sensitivity analysis: [docs/PIPELINE.md](docs/PIPELINE.md#gate-weights-thresholds-and-sensitivity).

## Environment (what produced the paper's results)

All generation and judging ran on **one Ollama 0.34.4 server process**, started 2026-09-27 15:56:30 and running continuously through the experiment window (September-October 2026). The binary was installed 2026-09-24 and never replaced.

| | |
|---|---|
| GPU | 1x NVIDIA RTX PRO 4500 Blackwell, 32 GB VRAM, driver 580.126.09, CUDA 13.0 (the driver libraries were loaded from a user-space copy; `nvidia-smi` itself reports 580.178.04, which is harmless) |
| CPU / RAM | AMD Ryzen Threadripper PRO 7955WX (16 cores) / 125 GB |
| OS | Ubuntu 24.04 LTS; system Python on the server 3.12.3 (not used by the pipeline; Ollama is a standalone binary) |
| Ollama | 0.34.4, bound to 127.0.0.1:11434, started with [`tools/server/start_ollama.sh`](tools/server/start_ollama.sh) |

Server settings (`start_ollama.sh`): `OLLAMA_CONTEXT_LENGTH=12288`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=3`, `OLLAMA_MAX_LOADED_MODELS=3`, `OLLAMA_KEEP_ALIVE=30m`, Vulkan enabled.

**Quantisation.** Every model ran quantised (mostly Q4_K_M; the exact level of each is `details.quantization_level` in [`ollama_tags.json`](ollama_tags.json)) and with a **q8_0 KV cache**. Results are therefore not those of the full-precision checkpoints.

### Paper model name -> Ollama tag
Digests are the short IDs from `ollama list`; the full digests are in `ollama_tags.json` (the output of `curl localhost:11434/api/tags` on the server).

| paper name | Ollama tag | digest |
|---|---|---|
| Llama-3.1-8B | `llama3.1:8b` | 46e0c10c039e |
| Qwen2.5-Coder-7B | `qwen2.5-coder:7b` | dae161e27b0e |
| Qwen2.5-Coder-32B | `qwen2.5-coder:32b` | b92d6a0bd47e |
| Qwen3-30B-A3B | `qwen3:30b-a3b` | ad815644918f |
| Gemma-3-27B | `gemma3:27b` | a418f5838eaf |
| CodeGemma-7B | `codegemma:7b` | 0c96700aaada |
| DeepSeek-Coder-V2-Lite | `deepseek-coder-v2:16b` | 63fb193b3a9b |
| Granite-4.1-8B | `granite4.1:8b` | 444af1c4b2fe |
| Phi-3.5-mini | `phi3.5:3.8b` | 61819fb370a3 |
| Phi-3.5-MoE | `hf.co/bartowski/Phi-3.5-MoE-instruct-GGUF:Q4_K_M` | ef823174ed24 |
| Phi-4-14B (**failed**, see below) | `hf.co/bartowski/phi-4-GGUF:Q4_K_M` (also tried: `phi4:14b`, ac896e5b8b34) | 0096717e7dc4 |
| Llama-3.3-70B (**not executed**) | `llama3.3:70b` (42 GB, does not fit in 32 GB VRAM) | a6eb4748fd29 |
| judge, extractor, executor (not a subject) | `gpt-oss:20b` | 17052f91a42e |

**Which Phi-4 tag.** `config.yaml` (generators and plan) uses `hf.co/bartowski/phi-4-GGUF:Q4_K_M`, and that is the tag behind the paper's "Phi-4-14B" row (23 unit attempts, all failed): `runs/*/ollama_hf.co_bartowski_phi-4-GGUF_Q4_K_M/S2_representations.json`. Ollama's own `phi4:14b` was tried earlier in a superseded plan (2 doorstop units, `runs/doorstop/ollama_phi4_14b/`); it failed the same way and is not in the plan or the analysis. Every attempt on both tags ended with `gave up after 6 attempts (HTTP 500)`, so Phi-4 produced no suites.

## Sampling, context and reasoning settings (as implemented)

Read from the code (`tcgen/llm.py`, `config.yaml`), not from the paper. They agree with the paper's "temperature 0, seed 42" for the generators and the judge.

| stage | model | temperature | seed | `num_predict` | `num_ctx` | reasoning (`think`) |
|---|---|---|---|---|---|---|
| S1 extraction | `gpt-oss:20b` | 0 | 42 | 8192 | 12288 | not set (Ollama default) |
| S2 representation choice, S3 generation (all generators) | the 12 subjects | 0 | 42 | 8192 | 12288 | not set; `false` for `qwen3:30b-a3b` (`model_params`) |
| S5 FSA judge (also the baseline arm) | `gpt-oss:20b` | 0 | 42 | 8192 | 12288 | not set (Ollama default) |
| S6 executor, S6 triage, S6A audit | `gpt-oss:20b` | 0 | 42 | 8192 | 12288 | `low` (`models.executor_think`) |

- Every Ollama request sends `options.num_ctx = llm.ollama_num_ctx` (12288, equal to the server default) and `options.num_predict = llm.max_tokens` (8192); no stage overrides either.
- Prompts longer than `num_ctx` are truncated by Ollama, not by the pipeline.
- The cache key is a hash of (model spec, system prompt, prompt, temperature, seed, max tokens, think), so changing any of these misses the cache.
- With `OLLAMA_NUM_PARALLEL=3` (3 concurrent requests, `pipeline.workers`) GPU batch composition can still change outputs slightly even at temperature 0. Cached answers are what make a re-run identical.

## Python versions

- **Pipeline client** (`tcgen`, the code that calls Ollama): the previously recorded environment was Python 3.10.16 with the versions in `requirements.txt`. Pure-Python and network code, so any 3.10-3.12 works. The server's Python 3.12.3 plays no part (Ollama is a Go binary).
- **Analysis** (`tcgen.analyze`, `tools/sensitivity.py`, figures): **use Python 3.12.** With Python 3.12.9 and the pinned `requirements.txt` (`numpy==1.26.4`, `scipy==1.16.1`), `tools/reproduce.sh` reproduces every file in `runs/ANALYSIS/` byte for byte (checked in a clean environment). On Python 3.10.18 (`scipy==1.15.3`, the last release for 3.10) everything is identical except `sensitivity.json`, where a few borderline counts differ (e.g. `rep_pass_fail_flips` 948 instead of 940; probably Python 3.12's more accurate float `sum()` tipping scores that sit exactly on a threshold). Every sensitivity number quoted in the paper is the same in both.
- `.python-version` is therefore `3.12`.

## Running on your own GPU (no SSH tunnel)

Nothing in `tcgen/` or `tools/run_experiment.sh` needs the tunnel or `tools/server/`; those are only for a remote server. With Ollama on the same machine:
```bash
tools/server/start_ollama.sh &                       # or simply `ollama serve`; use the settings above for identical behaviour
export OLLAMA_BASE_URL=http://localhost:11434        # overrides providers.ollama.base_url (default http://localhost:11435 = the tunnel)
for t in gpt-oss:20b qwen2.5-coder:7b llama3.1:8b; do ollama pull $t; done   # tags from the table; hf.co/... tags pull from Hugging Face
tools/run_experiment.sh --models "qwen2.5-coder:7b" --projects doorstop
```
Memory needed: gpt-oss:20b (judge) and the generator are loaded together; the 27B-32B models need most of 32 GB of VRAM. `config.yaml` `models.skip` lists the two models a default run leaves out (Phi-4: HTTP 500 failures; Llama-3.3-70B: 42 GB does not fit in 32 GB); `--gen <spec>` forces any model.

## Exact re-run without a GPU

The prompt cache is **committed in this repository**: `.cache/llm/` holds 3,570 JSON files (one per model call, keyed by a hash of model, prompt and parameters), the raw answers behind the committed results (`gpt-oss:20b` 1,517 calls plus the 10 subject models, and a few Groq smoke-test calls). With it, a re-run replays the exact responses returned during the benchmark: no GPU and no model needed.
```bash
tools/run_experiment.sh --offline        # TCGEN_OFFLINE=1 + TCGEN_STRICT=1: every call must be a cache hit
```
- **It fails loudly, never quietly.** There is no mock fallback anywhere in the client. In offline mode a cache miss raises `LLMFatal` and stops the run before any file is written; in strict mode (`TCGEN_STRICT=1` or `llm.strict: true`) a failed call stops the run instead of being recorded as a failed suite. `tools/reproduce.sh` runs in strict mode.
- `python3 tools/check_mock_responses.py` scans the cache and the saved suites for stand-in answers. On the committed results: 0 of 496 saved suites and 0 of 3,570 cached responses contain mock-response text after reviewing 5 + 8 false positives by hand (judge comments about mocks in xUnit tests, and a test input "Mocked response"; listed in `tools/mock_scan_reviewed.txt`). The cache itself is scanned when you have it.

## Reproduce the derived results (no GPU, no cache)

```bash
tools/reproduce.sh            # installs requirements.txt into .venv, rebuilds runs/ANALYSIS/*, sensitivity, figures,
                              # and prints PASS/FAIL per file against the committed copies (exit 1 on any FAIL)
```

## Anonymised package for review

The review package is a double-blind copy of this repository: no git history (author names and e-mails live in the history), no paper sources, slides, logs, archives, installers or model weights, and no identifying strings (workstation paths and usernames inside the saved pytest output, server name, author names, e-mails). It includes the committed replay cache. The builder script is kept by the authors and is not part of the repository.

## Checks to run yourself after cloning

1. **Clean-environment test.** Fresh clone (or unzip the package), Python 3.12 (3.10.16 also works, see "Python versions"), then follow only this README: `tools/reproduce.sh` (creates `.venv`, installs `requirements.txt`, rebuilds, compares). Expected last line: `ALL PASS`.
2. **Smoke test** (needs the cache, or a GPU server with the models). `tools/run_experiment.sh --phase gen --projects doorstop --models qwen2.5-coder:7b` should finish almost at once, served from the cache, and change no tracked file: `git status` stays clean (the logs under `runs/` are git-ignored). With no cache and no server, add `--offline`: it must stop with `LLMFatal: offline mode: no cached answer ...` and write nothing.

## Gate weights and sensitivity

The weights are design choices (expert judgment), not fitted to data, so we check how much the results depend on them. Full tables: [docs/PIPELINE.md](docs/PIPELINE.md#gate-weights-thresholds-and-sensitivity). Reproduce with `python3 -B tools/sensitivity.py` (reads committed data, writes `runs/ANALYSIS/sensitivity.json`).

**Gate 1 (RSS), weights {M1 0.40, M2 0.30, M3 0.15, M4 0.15}.**
M1 (concern alignment) is largest because choosing the wrong concern class (e.g. a state representation for a pure business rule) is a structural mismatch that the other metrics cannot compensate for; M2 addresses the same issue one level of abstraction up; M3 (Occam) and M4 (LLM feasibility) are secondary correctives.
*Sensitivity:* each weight was varied by +/-0.05 (the others rescaled proportionally) for all 59 units, 754 unit-level perturbations. The top-ranked paradigm changed in 2.7% of cases. The full paradigm ordering changed in 33% of cases, with mean Kendall's tau = 0.94 against the baseline ordering. So the top choice is robust, but the order of lower-ranked paradigms is not.

**Gate 3 (FSA), standard profile {clause coverage 0.30, negative 0.20, oracle 0.15, boundary 0.20, groundedness 0.15}.**
Each component maps to ISO/IEC/IEEE 29119-4:
- *Clause coverage* reflects requirements-based testing, whose coverage items are atomic requirements (section 5.2.12). It gets the highest weight because an uncovered clause is an untested aspect of the requirement.
- *Negative and boundary coverage* get equal secondary weights: requirements-based tests are typically positive, so negative cases need complementary techniques such as boundary value analysis (sections 5.2.12.3, 5.2.3).
- *Oracle assertiveness and groundedness* assess expected results, which the standard requires to be derived from the test basis (section 5.1). A value not traceable to the requirement violates this.

The specific weights, in all profiles, are our design choices. A low groundedness weight lets ungrounded suites pass, which motivates a separate groundedness threshold (see the paper, Section VII).
*Sensitivity:* each FSA weight was varied by +/-0.05 (others rescaled proportionally). Suite-level pass/fail at FSA >= 0.50 changed in 3.6% of decisions (111 of 3,110). Rankings were not fully stable: the paradigm ordering changed in 6 of 10 perturbations, but only through swaps of adjacent paradigms (tau >= 0.867); the best and worst paradigms were never displaced by more than one rank.

Note: the perturbations are applied to each unit's or suite's own inferred system profile (weights that are 0 are skipped), not only to the standard profile.

## Reproducing the paper's numbers

**Without a GPU (minutes).** All results are committed under `runs/`; every aggregate is recomputed from them:
```bash
python -m tcgen.analyze                  # runs/<project>/** -> runs/ANALYSIS/*.csv, analysis.json (verified: identical to the committed files)
python tools/sensitivity.py              # -> runs/ANALYSIS/sensitivity.json (verified: identical)
python tools/verify_threshold_claim.py   # design-doc vs implemented thresholds
python paper/fig/build_figures.py        # -> paper/fig/*.pdf
```

**With the GPU server (days).** Re-generate everything: `tools/run_experiment.sh` (see [tools/README.md](tools/README.md)). Needs the SSH tunnel, the models pulled, and `../.env`.

Where each paper result comes from:

| paper | source file |
|---|---|
| Table `tab:doorstop` (gate outcomes by model, doorstop) | `runs/ANALYSIS/by_model_project.csv` (rows with `project = doorstop`) |
| Figure `fig:fsa-model` (mean FSA per model) | `runs/ANALYSIS/suites.csv` via `paper/fig/build_figures.py` (aggregate: `by_model.csv`) |
| Table `tab:byrepr` (gate outcomes by representation) | `runs/ANALYSIS/by_representation.csv` |
| Figure `fig:fsa-repr` (FSA by paradigm) | `runs/ANALYSIS/suites.csv` via `paper/fig/build_figures.py` (aggregate: `by_rep_group.csv`) |
| Gate 1 statistics, RSS choice vs LLM choice | `gate1_units.csv`, `gate1_by_model.csv`, `gate1_by_project.csv`, `rep_choice_by_project.csv` |
| Closed-loop repair, hallucinated values, execution agreement, correlations | `runs/ANALYSIS/analysis.json`, summarised in `runs/ANALYSIS/REPORT.md` |
| Weight sensitivity (Gates 1 and 3) | `runs/ANALYSIS/sensitivity.json` |
| Execution and audit against the real code | `runs/<project>/<model>/S6_*.json`, `runs/<project>/S7_report.md` |
| Per-suite raw data | `runs/ANALYSIS/suites.csv` (one row per project x model x unit; 496 suites, 311 judged) |

## Known deviations from the planned experiment

Read these before comparing a re-run with the paper.

- **12 open-weight generators were planned; 10 completed.** Phi-4-14B failed Gate 1 on every attempted unit (server errors mid-generation; `runs/*/ollama_hf.co_bartowski_phi-4-GGUF_Q4_K_M/` and `ollama_phi4_14b/` hold no suites). Llama-3.3-70B was never executed (no `runs/` directory). Both stay in `config.yaml` (`generators` and `plan`, so the analysis still reports them) but are listed under `models.skip` with the reason, so a default run skips them. Phi-4 uses bartowski's GGUF because Ollama's own `phi4:14b` crashes on this llama.cpp build.
- **Gemma-3-27B and DeepSeek-Coder-V2-Lite are partial** (7 and 6 suites against 58 to 61 for the other eight), because they were too slow. Their aggregates are low-confidence.
- **The two closed-source controls (GPT-4o, Claude 3.5 Sonnet) were not run** (no paid API access); the paper's 14-model funnel ends in 12 open-weight models plus these two.
- **Model comparisons use doorstop only** (every model saw the same 4 units there, n = 4 suites per model: descriptive, not a ranking).
- **Runs were resumed after interruptions** (a network outage on 2026-09-27, and earlier crashes); finished suites and cached LLM calls were reused. The scripts that did this are archived in `tools/legacy/`; `tools/run_experiment.sh` is the cleaned-up equivalent and has not been used for the reported results.
- **Quantised models, q8_0 KV cache, 12288-token context** (see Environment): not the full-precision checkpoints.
- **Qwen3-30B-A3B runs with `think: false`**: with thinking on, hidden reasoning used the whole output budget and produced 54 empty answers.
- **Executor reasoning is set to `low`** (judge unchanged) because long reasoning filled the context and returned empty answers.
- **Thresholds are the implemented ones** (RSS 0.60, SFV by paradigm 0.60 to 1.00, FSA 0.50), looser than the design document (SFV 0.80, FSA 0.75); absolute pass rates would drop under the stricter values.
- **Exact byte-for-byte regeneration is not guaranteed** on other hardware: temperature is 0 and the seed is 42, but GPU and Ollama builds can still change outputs. The cached LLM calls (`.cache/llm`, now committed rather than git-ignored) make a re-run identical as long as the cache is reused.

## Layout
| path | role |
|---|---|
| `tcgen/llm.py` | one client for Groq / OpenAI / Gemini / Anthropic / OpenRouter / Ollama / vLLM; retries; cache; no mock fallback |
| `tcgen/ingest.py` | S0 SRS files → text |
| `tcgen/extract.py` | S1 requirements + test units |
| `tcgen/represent.py` | S2 Gate 1 (RSS) representation choice |
| `tcgen/suite.py` | S3 generate → S4 Gate 2 (SFV) → S5 Gate 3 (FSA) closed loop |
| `tcgen/execute.py` | S6 tests → runnable tests → run against code → triage |
| `tcgen/report.py` | S7 report |
| `tcgen/gates/` | `rss.py`, `sfv.py` (+ `sfv_repr.py` ported validators), `fsa.py`, `groundedness.py`, `config.py` |
| `prompts/` | every prompt, as plain text |
| `schemas/testcase.schema.json` | canonical test case |
