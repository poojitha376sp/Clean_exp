# Clean_exp — SRS → 3-gate test generation → execution against real code

A clean rebuild of the test-generation experiment. The original pipeline in
`../pipeline_automated/` is left untouched as a reference; the gate logic
(RSS m1–m10 tables, SFV validators, FSA weights, groundedness) is ported from it.

Full step-by-step rationale (what / why / pros / cons / what to observe):
**[docs/PIPELINE.md](docs/PIPELINE.md)**.

## Setup
```bash
cd Clean_exp
python3 -m venv .venv && .venv/bin/pip install pypdf python-docx gherkin-official coverage jsonschema pyyaml requests python-dotenv pytest pandas
```
API keys go in `../.env` (never in code). Providers and models: `config.yaml`.

## Inputs
```
../inputs/<project>/
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
