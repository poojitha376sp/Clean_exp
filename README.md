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

## Run
```bash
.venv/bin/python -m tcgen.run --project <project>                         # all stages, all generators
.venv/bin/python -m tcgen.run --project <project> --stages S0,S1           # extract, then check S1 by hand
.venv/bin/python -m tcgen.run --project <project> --stages S2,S3 --gen groq:openai/gpt-oss-20b
.venv/bin/python -m tcgen.run --project <project> --stages S6,S7
```
Everything lands in `runs/<project>/` (git-excluded). The final table is `runs/<project>/S7_report.md`.
LLM calls are cached by prompt hash in `.cache/llm`, so re-runs are free and identical.

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
