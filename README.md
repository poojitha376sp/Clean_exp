# Clean_exp — SRS → 3-gate test generation → execution against real code

A clean rebuild of the test-generation experiment. The original pipeline in
`../pipeline_automated/` is left untouched as a reference; the gate logic
(RSS m1–m10 tables, SFV validators, FSA weights, groundedness) is ported from it.

Full step-by-step rationale (what / why / pros / cons / what to observe):
**[docs/PIPELINE.md](docs/PIPELINE.md)**.

## Setup
```bash
cd Clean_exp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
Pinned to the exact versions (`requirements.txt`) and Python version (`.python-version`,
3.10.16) the reported benchmark actually ran on.
API keys go in `../.env` (never in code). Providers and models: `config.yaml`.

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

- **12 open-weight generators were planned; 10 completed.** Phi-4-14B failed Gate 1 on every attempted unit (server errors mid-generation; `runs/*/ollama_hf.co_bartowski_phi-4-GGUF_Q4_K_M/` and `ollama_phi4_14b/` hold no suites). Llama-3.3-70B was never executed (no `runs/` directory). Both are still listed in `config.yaml` so a full re-run will attempt them. Phi-4 uses bartowski's GGUF because Ollama's own `phi4:14b` crashes on this llama.cpp build.
- **Gemma-3-27B and DeepSeek-Coder-V2-Lite are partial** (7 and 6 suites against 58 to 61 for the other eight), because they were too slow. Their aggregates are low-confidence.
- **The two closed-source controls (GPT-4o, Claude 3.5 Sonnet) were not run** (no paid API access); the paper's 14-model funnel ends in 12 open-weight models plus these two.
- **Model comparisons use doorstop only** (every model saw the same 4 units there, n = 4 suites per model: descriptive, not a ranking).
- **Runs were resumed after interruptions** (a network outage on 2026-09-27, and earlier crashes); finished suites and cached LLM calls were reused. The scripts that did this are archived in `tools/legacy/`; `tools/run_experiment.sh` is the cleaned-up equivalent and has not been used for the reported results.
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
