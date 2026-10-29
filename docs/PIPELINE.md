# Clean_exp pipeline — every step, why, pros/cons, what to observe

Research question for this experiment: **given an SRS, can LLMs generate test
cases that pass the 3-gate framework (RSS → SFV → FSA), and do those gate
scores say anything about how the tests behave against the real
implementation?** There is no expert ground truth for the three projects, so
the implementation itself is the external yardstick (S6).

```
inputs/<project>/srs/*  ──S0 ingest──► S0_srs.txt
                          ──S1 extract (fixed extractor model)──► S1_requirements.json, S1_units.json
for each generator model:
   ──S2 Gate 1 RSS  (LLM picks reps → heuristic RSS scores → ≤3 re-picks)──► S2_representations.json
   ──S3 generate ─► S4 Gate 2 SFV ─► S5 Gate 3 FSA   (closed loop, ≤3 repairs)──► S3_S5_suites/*.json
   ──S6 execute vs code (fixed executor model)──► S6_execution.json, S6_workspace/tests_generated/
──S7 report──► S7_report.md, S7_summary.csv
```

**No data leakage:** S0–S5 read **only** `inputs/<p>/srs/`. The implementation (`inputs/<p>/code/`) is opened for the first time in S6, which runs only after every generator has finished generating. Before S6 opens the code, every suite's test cases are fingerprinted (`S6_frozen_<arm>.json`, sha256 per suite). S7 re-checks the fingerprints (`tests_frozen_before_code_ok`), which shows that no test changed after the code was seen. Residual caveats: the S6 executor model *does* see the code when translating tests, so its prompt forbids changing expectations and triage flags `test_bug`s; and public repos may be in a model's pre-training data (a limitation to state in the paper).

Run: `cd Clean_exp && .venv/bin/python -m tcgen.run --project <name>`
(`--stages S2,S3` to redo part; `--gen <spec>` for one model; `--units U01_3.1` to restrict.)

---

## S0 — Ingest
**What:** every `.pdf/.docx/.md/.txt` in `inputs/<p>/srs/` → one cleaned text file (page footers stripped; DOCX tables kept as `a | b | c` rows).
**Why:** the three SRSs come in different formats; later stages need plain text.
**Pros:** format-agnostic, zero LLM cost. **Cons:** PDF extraction loses figures, and multi-column/table layouts can come out scrambled.
**Observe:** char counts per file; skim `S0_srs.txt` for garbled tables — if a requirement table is scrambled, convert that SRS to DOCX/MD by hand.

## S1 — Requirement extraction → test units
**What:** the SRS is chunked (~7k chars on paragraph boundaries); a *fixed* extractor model returns atomic requirements `{id, section, text, kind, testable, refs}`. The SRS's own IDs are kept; otherwise `<PROJ>-<section>-n`. Requirements are grouped into **units** (a section's testable requirements, split evenly to ≤ `unit_max_reqs`) plus the out-of-unit requirements they reference (dependency context).
**Why:** replaces the old Mongo/CSV import, which only fit the Gemini spreadsheet. A unit is the granularity the old pipeline used (a section), small enough for 8K-token rate limits.
**Pros:** works for any SRS; the same requirements for every generator, so model comparisons are fair; the `testable` flag keeps background prose out of coverage.
**Cons:** extraction errors propagate (missed/merged requirements); `refs` only catches explicit references; this is an LLM step, so it's not perfectly reproducible without the cache.
**Observe:** requirement count vs what you know of the SRS (a **human checkpoint** — skim `S1_requirements.json` before spending on S2+), testable ratio, chunk failures.

## S2 — Gate 1: Representation Suitability (RSS)
**What:** the *generator* picks K+1 representations from the 30-item catalog per unit. Each pick is scored by the ported heuristic RSS (m1 concern alignment, m2 abstraction, m3 Occam, m4 LLM feasibility, m5–m10 expanded; weights by inferred system type: standard / safety_critical / data_pipeline / distributed_concurrent / interaction_heavy / rapid_prototyping). Picks < 0.60 are rejected with their metric breakdown fed back, for ≤3 re-picks. We also compute the heuristic's own top-3 over all 30 and record the **agreement**.
**Why:** this is the framework's first gate; choosing the representation is part of what's being evaluated.
**Pros:** the LLM brings semantic judgement and the heuristic brings a consistent, explainable filter; logging agreement tells us whether the two views align.
**Cons:** the RSS heuristic is keyword-based (cue regexes plus a group lookup table) — it can't read nuance, so it's a *consistency check, not ground truth*. A fallback keeps the best below-threshold pick (flagged `fallback_below_threshold`) so a unit is never left untested.
**Observe:** G1 pass rate, re-pick rounds, which representations each model favours per project type, the agreement figure.
**Fixed vs old code:** the old substring lookup mapped several catalog names ("Use-Cases & User Stories", "Financial/Rule Tables", "UML Testing Profile"…) to the group-1 default; there's now an explicit 30-name table (`gates/config.py: CATALOG`).

## S3 — Generation
**What:** per (unit, representation) the generator writes **two things**: the suite in the representation's own notation (```artifact```) and the same cases as **canonical JSON** (`id, title, req_ids, kind, preconditions, inputs, steps, expected`). The prompt states the rubric it'll be scored on (the old phase-2 "metrics-aware" idea) plus the representation's sufficiency checklist.
**Why:** the canonical form makes every downstream check uniform across 30 very different notations — schema validation, traceability, judging, and conversion to executable tests.
**Pros:** representation-specific output is kept (the framework's point) *and* is machine-checkable. **Cons:** longer outputs (more tokens), and the model can make the artifact and the JSON disagree (the judge sees both).
**Observe:** test cases per requirement, positive/negative/boundary mix, output length.

## S4 — Gate 2: Syntactic Form Validity (SFV)
**What:** `SFV = 0.5·schema + 0.5·representation`. *schema* = fraction of canonical cases valid against `schemas/testcase.schema.json` with unique ids and req_ids that exist. *representation* = a syntax check routed by the representation's **actual** group: Gherkin → the official gherkin parser; xUnit → Python `ast`; state machines → states/initial/transitions/events check; tables, sequence and symbolic notations → the old group validators; use cases/goal models → actor + main + alternative/exception flow + numbered steps. **Pass** = all cases schema-valid AND representation score ≥ group threshold. Failure → issues fed back → repair.
**Why:** catch malformed output cheaply before paying for the judge.
**Pros:** deterministic, free, explains its failures. **Cons:** checks for notations without an official grammar are heuristic; SFV says nothing about meaning.
**Observe:** SFV failure rate per representation/model, which issues recur, repairs needed.
**Fixed vs old code:** the old `run_metrics.py` hard-coded `"Finite State Machine"`, so every suite got a generic "has a heading / numbered list / arrow" check.

## S5 — Gate 3: Functional Semantic Adequacy (FSA) + groundedness
**What:** one judge call returns clause coverage (CC), negative coverage (NC), oracle assertiveness (OA), boundary coverage (BC), and every concrete value with an entailment verdict → `Mg = 1 − hallucinated/asserted`. `FSA = wc·CC + wn·NC + wo·OA + wb·BC + wg·Mg` (weights by system type). Computed without an LLM: **traceability** = testable requirements with ≥1 test case. **Pass** = FSA ≥ 0.50 AND traceability = 1.0. Failure → untraced requirements, uncovered clauses, ungrounded values and judge weaknesses fed back → repair (which re-runs SFV first).
**Why:** the semantic gate — are the right things tested, with real oracles, without invented facts?
**Pros:** the judge is a **different model family** from the generators (no self-grading, unlike the old setup); traceability is exact; groundedness is itemised, so it's auditable.
**Cons:** the judge is still an LLM (noise and leniency); the same judge for all makes it fair but not perfect. Worth hand-labelling ~10 suites to calibrate it.
**Observe:** FSA sub-scores (NC and BC are usually the weak spots), hallucinated values, how much repairs raise FSA, suites that stay below threshold after 3 repairs.
**Repair budget:** one shared budget of `max_repairs` (3) regeneration attempts across Gate 2 and Gate 3 per suite. If nothing passes, the best attempt is kept and flagged.

## S6 — Execute against the real code
**What:** the code is copied to a throwaway workspace (originals untouched). A *fixed* executor model turns each batch of canonical cases into a runnable test file (one test per case id; cases that can't run become skips tagged `NOT_AUTOMATABLE` / `NOT_IMPLEMENTED`); files that fail to import get one fix round. The tests run (Python: pytest + coverage, branch coverage on). Each failing test is triaged: **code_mismatch** (implementation disagrees with the SRS), **test_bug**, or **spec_ambiguous**.
**Why:** it's the only ground truth we have. A test that faithfully encodes the SRS and fails is evidence of an SRS↔code gap; coverage shows how much of the implementation the SRS-derived tests reach.
**Pros:** objective signal, real bugs found, lets us check whether gate scores predict useful tests (`exec_ok_rate_G3pass` vs `G3fail` in the report).
**Cons:** the translation step adds its own errors (hence triage plus a hand spot-check); tests are only as good as the executor's understanding of the code API; non-Python projects need `project.yaml` test commands; triage is an LLM verdict — **spot-check every `code_mismatch` by hand before claiming it.**
**Observe:** executable rate, pass rate, number of code mismatches (verified), test bugs, not-implemented features, line/branch coverage.

## S7 — Report
Per generator: G1/G2/G3 pass rates, SFV/FSA and sub-score means, traceability, repairs, test-case counts, execution results, coverage, and gate-vs-execution correlation. Per representation: suites, gate passes, mean FSA. Files: `S7_report.md`, `S7_summary.csv`.

---

## Improvements over the original pipeline
1. **No silent mocks.** Failed calls raise, get logged, and are excluded (the old pipeline scored canned mock text as test suites).
2. **Canonical test schema** under every representation → real SFV, exact traceability, and executability.
3. **SFV routed by the true representation**, with real parsers where they exist.
4. **Judge ≠ generator family**; the same judge for all generators.
5. **Deterministic traceability** next to the judge's clause coverage.
6. **Explicit 30-representation → group table** (no silent group-1 defaults).
7. **Gate 1 records LLM vs heuristic agreement** instead of trusting either blindly.
8. **Execution against real code** as external validation, plus correlation with the gates.
9. **Reproducibility:** temperature 0, fixed seed, prompt-hash cache, per-call token/latency log (`runs/llm_calls.jsonl`), every repair attempt saved.
10. **Fair comparison:** extractor, judge and executor are fixed across generators, so only the generator varies.

## Known limitations / next steps
- The RSS heuristic is keyword-based — consider an LLM-scored RSS (m1–m4 by a judge) and compare the two.
- Calibrate the FSA judge on a hand-labelled sample (Cohen's κ, as in the SLR).
- Add mutation testing (`mutmut`) in S6 to measure how strong the test suites are.
- Groq free tier: 8K tokens/minute and ~200K tokens/day per model. Full runs need the GPU server (Ollama/vLLM) or paid keys.
