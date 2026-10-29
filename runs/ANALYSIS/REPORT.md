# SRS → Test Cases: 3-Gate Pipeline Results

496 test suites (4058 test cases) from 29 project×model pairs. Pipeline: requirement extraction → Gate 1 RSS (representation choice, ≤3 re-picks) → generation → Gate 2 SFV → Gate 3 FSA (+ groundedness), ≤3 closed-loop repairs → comparison with the real implementation.

## Key findings

1. **Model comparisons use doorstop only** (every model generated for the same units there); project comparisons use only the models run on every project (CodeGemma-7B, DeepSeek-Coder-V2-Lite, Granite-4.1-8B, Llama-3.1-8B, Phi-3.5-MoE, Phi-3.5-mini, Qwen2.5-Coder-32B, Qwen2.5-Coder-7B, Qwen3-30B-A3B).
2. **Best overall adequacy:** Llama-3.1-8B (mean FSA 0.73, both-gates pass 100%); **weakest:** CodeGemma-7B (FSA 0.47, both-gates pass 25%).
3. **Format discipline (Gate 2) is the first filter:** G2 pass ranges from 0% (Phi-3.5-mini) to 100% (Gemma-3-27B). Suites that fail G2 never reach the judge.
4. **Size vs adequacy:** Spearman ρ(parameters, FSA) = 0.021 over 24 judged suites; ρ(active parameters, FSA) = 0.131 (doorstop; small n, indicative only). Model size alone explains little of the adequacy.
5. **Code-specialised vs general models:** FSA 0.58 vs 0.64, G2 pass 69% vs 54% (Mann-Whitney p = 0.297). Code specialisation does not buy requirement-level test design.
6. **MoE vs dense:** FSA 0.59 (MoE) vs 0.62 (dense).
7. **Gate success by representation (n ≥ 3 suites):** GUI Event Graphs 64% both-gates (n=28), Decision Tables 55% both-gates (n=44), Gherkin (BDD DSL) 54% both-gates (n=207), Temporal Logic (LTL) 50% both-gates (n=4), Sequence Diagrams 44% both-gates (n=18), xUnit Test Cases 29% both-gates (n=79), Use-Cases & User Stories 28% both-gates (n=39), Finite State Machines / Statecharts 28% both-gates (n=40), UML Testing Profile (UTP) 27% both-gates (n=15), Transition Systems (S, T, I) 0% both-gates (n=3), Natural Language -> DSL 0% both-gates (n=8), FSM Path-Based Representations 0% both-gates (n=5).
8. **What models choose (Gate 1):** Gherkin (BDD DSL) ×232, xUnit Test Cases ×81, Use-Cases & User Stories ×75, Decision Tables ×50, Finite State Machines / Statecharts ×41 — 18 distinct representations used out of 30. Choices cluster heavily on a few familiar notations.
9. **LLM choice vs RSS heuristic:** mean overlap with the heuristic's top-3 = 0.20; the two views of 'suitability' agree only partially, which argues for reporting both rather than trusting either.
10. **Negative-path** averages 0.53 across all judged suites.
11. **Boundary** averages 0.68 across all judged suites.
12. **Oracle precision** averages 0.47 across all judged suites.
13. **Clause coverage** averages 0.95 across all judged suites.
14. **Groundedness** averages 0.46 across all judged suites.
15. **Closed-loop repair:** 207 suites were repaired after the judge; mean FSA gain +0.13.
16. **Small vs large SRS** (same models: CodeGemma-7B, DeepSeek-Coder-V2-Lite, Granite-4.1-8B, Llama-3.1-8B, Phi-3.5-MoE, Phi-3.5-mini, Qwen2.5-Coder-32B, Qwen2.5-Coder-7B, Qwen3-30B-A3B): doorstop: FSA 0.61, both-gates 42%, tests/req 1.15; ventilator: FSA 0.71, both-gates 49%, tests/req 1.20; virtual_clinic: FSA 0.66, both-gates 38%, tests/req 1.36.
17. **Hallucinated specifics:** 243 of 496 judged suites asserted at least one value not grounded in the SRS (mean 6.1 per suite).
18. **Against the real code:** the highest share of SRS requirements whose tests reach implemented behaviour is 54% (DeepSeek-Coder-V2-Lite on doorstop).
19. **SRS-vs-code discrepancies flagged:** 173 test cases across all pairs were judged to contradict the implementation (execution failures triaged as code_mismatch + audit 'violated'); these need a manual check before being claimed.
20. **Audit validity:** on doorstop, where tests were also executed, the code audit agreed with real execution on 18% of 11 cases.
21. **Do gates predict code behaviour?** ρ(FSA, execution pass rate) = 0.433 (n=15).

## Per model (doorstop: same units for every model)

| model | suites | G2 pass | G3 pass | both | FSA | NC | OA | BC | Mg | repairs |
|---|---|---|---|---|---|---|---|---|---|---|
| Llama-3.1-8B | 4 | 100% | 100% | 100% | 0.73 | 0.50 | 0.85 | 0.88 | 0.25 | 1.50 |
| Qwen2.5-Coder-32B | 4 | 75% | 75% | 75% | 0.67 | 0.33 | 0.23 | 0.83 | 0.33 | 1.50 |
| Gemma-3-27B | 4 | 100% | 100% | 100% | 0.66 | 0.60 | 0.51 | 0.88 | 0.04 | 0 |
| DeepSeek-Coder-V2-Lite | 4 | 75% | 25% | 25% | 0.63 | 0.20 | 0.23 | 1.00 | 0.67 | 3 |
| Granite-4.1-8B | 4 | 75% | 50% | 50% | 0.57 | 0.07 | 0.28 | 0.83 | 0.00 | 1.50 |
| Qwen2.5-Coder-7B | 4 | 50% | 50% | 50% | 0.55 | 0.00 | 0.20 | 1.00 | 0.10 | 1.75 |
| Qwen3-30B-A3B | 4 | 25% | 25% | 25% | 0.53 | 1.00 | 0.20 | 0.00 | 0.00 | 2.50 |
| Phi-3.5-MoE | 4 | 25% | 25% | 25% | 0.53 | 0.00 | 0.20 | 1.00 | 0.00 | 2.25 |
| CodeGemma-7B | 4 | 75% | 25% | 25% | 0.47 | 0.04 | 0.20 | 0.67 | 0.43 | 2.50 |
| Phi-3.5-mini | 4 | 0% | 0% | 0% | – | – | – | – | – | 3 |

## Per model (all projects pooled — workloads differ, see per project × model)

| model | suites | G2 pass | G3 pass | both | SFV | FSA | CC | NC | OA | BC | Mg | repairs | tests/req |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Phi-3.5-mini | 58 | 9% | 2% | 2% | 0.54 | 0.74 | 0.89 | 0.63 | 0.24 | 1.00 | 0.62 | 2.95 | 1.42 |
| Granite-4.1-8B | 61 | 72% | 56% | 56% | 0.91 | 0.71 | 0.97 | 0.58 | 0.52 | 0.60 | 0.54 | 1.61 | 1.52 |
| Qwen2.5-Coder-32B | 61 | 93% | 85% | 85% | 0.96 | 0.71 | 0.97 | 0.56 | 0.56 | 0.80 | 0.45 | 1 | 1.91 |
| Llama-3.1-8B | 61 | 98% | 74% | 74% | 0.99 | 0.69 | 0.96 | 0.59 | 0.50 | 0.73 | 0.35 | 1.77 | 1.56 |
| Gemma-3-27B | 7 | 100% | 100% | 100% | 0.98 | 0.68 | 0.97 | 0.46 | 0.47 | 0.93 | 0.20 | 0 | 1.85 |
| Qwen3-30B-A3B | 60 | 17% | 12% | 12% | 0.31 | 0.68 | 0.94 | 0.64 | 0.70 | 0.82 | 0.47 | 2.77 | 0.37 |
| Qwen2.5-Coder-7B | 61 | 87% | 54% | 54% | 0.92 | 0.67 | 0.95 | 0.50 | 0.46 | 0.68 | 0.43 | 1.82 | 1.48 |
| Phi-3.5-MoE | 60 | 60% | 38% | 38% | 0.83 | 0.63 | 0.97 | 0.46 | 0.35 | 0.55 | 0.56 | 2.35 | 1.29 |
| DeepSeek-Coder-V2-Lite | 6 | 83% | 50% | 50% | 0.92 | 0.63 | 0.94 | 0.12 | 0.22 | 0.90 | 0.60 | 2 | 1.05 |
| CodeGemma-7B | 61 | 56% | 15% | 15% | 0.70 | 0.56 | 0.83 | 0.50 | 0.33 | 0.46 | 0.46 | 2.66 | 0.80 |

## Per project × model

| project | model | suites | G2 | G3 | FSA | NC | BC | Mg | tests/req |
|---|---|---|---|---|---|---|---|---|---|
| doorstop | Llama-3.1-8B | 4 | 100% | 100% | 0.73 | 0.50 | 0.88 | 0.25 | 1.72 |
| doorstop | Qwen2.5-Coder-32B | 4 | 75% | 75% | 0.67 | 0.33 | 0.83 | 0.33 | 1.17 |
| doorstop | Gemma-3-27B | 4 | 100% | 100% | 0.66 | 0.60 | 0.88 | 0.04 | 1.87 |
| doorstop | DeepSeek-Coder-V2-Lite | 4 | 75% | 25% | 0.63 | 0.20 | 1.00 | 0.67 | 1.15 |
| doorstop | Granite-4.1-8B | 4 | 75% | 50% | 0.57 | 0.07 | 0.83 | 0.00 | 1.38 |
| doorstop | Qwen2.5-Coder-7B | 4 | 50% | 50% | 0.55 | 0.00 | 1.00 | 0.10 | 1.10 |
| doorstop | Qwen3-30B-A3B | 4 | 25% | 25% | 0.53 | 1.00 | 0.00 | 0.00 | 0.50 |
| doorstop | Phi-3.5-MoE | 4 | 25% | 25% | 0.53 | 0.00 | 1.00 | 0.00 | 0.92 |
| doorstop | CodeGemma-7B | 4 | 75% | 25% | 0.47 | 0.04 | 0.67 | 0.43 | 0.59 |
| doorstop | Phi-3.5-mini | 4 | 0% | 0% | – | – | – | – | 1.85 |
| ventilator | Qwen3-30B-A3B | 20 | 10% | 10% | 0.83 | 0.50 | 1.00 | 0.40 | 0.15 |
| ventilator | Qwen2.5-Coder-32B | 21 | 100% | 95% | 0.75 | 0.60 | 0.78 | 0.59 | 2.14 |
| ventilator | Granite-4.1-8B | 21 | 95% | 76% | 0.74 | 0.65 | 0.48 | 0.67 | 1.17 |
| ventilator | Qwen2.5-Coder-7B | 21 | 95% | 71% | 0.72 | 0.47 | 0.70 | 0.58 | 1.54 |
| ventilator | Gemma-3-27B | 3 | 100% | 100% | 0.71 | 0.27 | 1.00 | 0.42 | 1.82 |
| ventilator | Llama-3.1-8B | 21 | 100% | 62% | 0.69 | 0.56 | 0.64 | 0.44 | 1.41 |
| ventilator | Phi-3.5-mini | 21 | 10% | 5% | 0.68 | 0.07 | 1.00 | 1.00 | 1.35 |
| ventilator | Phi-3.5-MoE | 20 | 65% | 55% | 0.68 | 0.39 | 0.37 | 0.81 | 1.23 |
| ventilator | DeepSeek-Coder-V2-Lite | 1 | 100% | 100% | 0.58 | 0.00 | 0.50 | 1.00 | 1.00 |
| ventilator | CodeGemma-7B | 21 | 38% | 14% | 0.58 | 0.42 | 0.38 | 0.76 | 0.59 |
| virtual_clinic | Phi-3.5-mini | 33 | 9% | 0% | 0.77 | 1.00 | 1.00 | 0.38 | 1.41 |
| virtual_clinic | Granite-4.1-8B | 36 | 58% | 44% | 0.71 | 0.59 | 0.68 | 0.50 | 1.74 |
| virtual_clinic | Qwen2.5-Coder-32B | 36 | 92% | 81% | 0.69 | 0.55 | 0.81 | 0.38 | 1.86 |
| virtual_clinic | Llama-3.1-8B | 36 | 97% | 78% | 0.69 | 0.61 | 0.78 | 0.31 | 1.63 |
| virtual_clinic | DeepSeek-Coder-V2-Lite | 1 | 100% | 100% | 0.68 | 0.00 | 1.00 | 0.00 | 0.75 |
| virtual_clinic | Qwen3-30B-A3B | 36 | 19% | 11% | 0.66 | 0.62 | 0.90 | 0.57 | 0.48 |
| virtual_clinic | Qwen2.5-Coder-7B | 36 | 86% | 44% | 0.64 | 0.56 | 0.64 | 0.36 | 1.49 |
| virtual_clinic | Phi-3.5-MoE | 36 | 61% | 31% | 0.61 | 0.52 | 0.64 | 0.43 | 1.37 |
| virtual_clinic | CodeGemma-7B | 36 | 64% | 14% | 0.57 | 0.59 | 0.47 | 0.36 | 0.95 |

## Per representation

| representation | suites | G2 | G3 | both | SFV | FSA | BC | NC |
|---|---|---|---|---|---|---|---|---|
| Gherkin (BDD DSL) | 207 | 75% | 54% | 54% | 0.82 | 0.67 | 0.73 | 0.51 |
| xUnit Test Cases | 79 | 40% | 29% | 29% | 0.61 | 0.68 | 0.67 | 0.54 |
| Decision Tables | 44 | 75% | 55% | 55% | 0.77 | 0.70 | 0.76 | 0.70 |
| Finite State Machines / Statecharts | 40 | 42% | 28% | 28% | 0.71 | 0.66 | 0.47 | 0.44 |
| Use-Cases & User Stories | 39 | 51% | 28% | 28% | 0.86 | 0.62 | 0.59 | 0.38 |
| GUI Event Graphs | 28 | 86% | 64% | 64% | 0.96 | 0.74 | 0.55 | 0.61 |
| Sequence Diagrams | 18 | 72% | 44% | 44% | 0.85 | 0.67 | 0.90 | 0.48 |
| UML Testing Profile (UTP) | 15 | 73% | 27% | 27% | 0.92 | 0.58 | 0.36 | 0.69 |
| Natural Language -> DSL | 8 | 0% | 0% | 0% | 0.31 | – | – | – |
| FSM Path-Based Representations | 5 | 60% | 0% | 0% | 0.76 | 0.45 | 0.00 | 0.33 |
| Temporal Logic (LTL) | 4 | 50% | 50% | 50% | 0.85 | 0.83 | 1.00 | 0.90 |
| Transition Systems (S, T, I) | 3 | 0% | 0% | 0% | 0.00 | – | – | – |
| Test Requirement Matrix | 2 | 50% | 50% | 50% | 0.67 | 0.64 | 1.00 | 0.00 |
| Protocol State Machines | 1 | 0% | 0% | 0% | 0.60 | – | – | – |
| Interface Automata | 1 | 0% | 0% | 0% | 0.77 | – | – | – |
| Goal-Oriented (KAOS / i*) | 1 | 0% | 0% | 0% | 0.75 | – | – | – |
| Feature Vectors & Distributions | 1 | 0% | 0% | 0% | 0.75 | – | – | – |

## Per representation group

| group | suites | G2 | G3 | FSA |
|---|---|---|---|---|
| Scenario/Behavioral | 247 | 71% | 50% | 0.67 |
| Stateful/Transitions | 49 | 41% | 22% | 0.62 |
| Logical/Rules | 44 | 75% | 55% | 0.70 |
| Programmatic/Code | 87 | 37% | 26% | 0.68 |
| Concurrency/Interaction | 66 | 76% | 48% | 0.69 |
| Math/Symbolic/Contracts | 3 | 33% | 33% | 0.64 |

## Model classes

**By size**

| size | suites | G2 | both | FSA | Mg |
|---|---|---|---|---|---|
| small (<10B) | 302 | 65% | 40% | 0.67 | 0.44 |
| medium (10-20B) | 6 | 83% | 50% | 0.63 | 0.60 |
| large (>20B) | 188 | 58% | 47% | 0.68 | 0.47 |

**Code-specialised vs general**

| code model | suites | G2 | both | FSA |
|---|---|---|---|---|
| yes | 189 | 79% | 51% | 0.66 |
| no | 307 | 53% | 38% | 0.69 |

**MoE vs dense**

| MoE | suites | G2 | both | FSA |
|---|---|---|---|---|
| no | 370 | 70% | 49% | 0.68 |
| yes | 126 | 40% | 26% | 0.64 |

## Gate 1 (representation choice)

| model | units | G1 pass | fallback | re-picks | agree w/ heuristic |
|---|---|---|---|---|---|
| Qwen2.5-Coder-7B | 59 | 100% | 0% | 0.02 | 0.25 |
| Llama-3.1-8B | 59 | 100% | 0% | 0 | 0.30 |
| DeepSeek-Coder-V2-Lite | 59 | 92% | 8% | 0.37 | 0.23 |
| Gemma-3-27B | 23 | 100% | 0% | 0.09 | 0.26 |
| CodeGemma-7B | 59 | 97% | 3% | 0.22 | 0.11 |
| Granite-4.1-8B | 59 | 100% | 0% | 0.09 | 0.20 |
| Phi-3.5-mini | 59 | 92% | 3% | 0.53 | 0.14 |
| Qwen3-30B-A3B | 59 | 98% | 0% | 0.24 | 0.25 |
| Qwen2.5-Coder-32B | 59 | 100% | 0% | 0.03 | 0.23 |
| Phi-3.5-MoE | 59 | 97% | 2% | 0.14 | 0.25 |
| Phi-4-14B | 23 | 0% | 0% | 0 | 0.00 |

**Representations chosen per project**

| project | representation | times_chosen |
|---|---|---|
| doorstop | Gherkin (BDD DSL) | 14 |
| doorstop | Use-Cases & User Stories | 8 |
| doorstop | xUnit Test Cases | 6 |
| doorstop | Decision Tables | 6 |
| doorstop | Finite State Machines / Statecharts | 3 |
| doorstop | Transition Systems (S, T, I) | 1 |
| doorstop | UML Testing Profile (UTP) | 1 |
| doorstop | Natural Language -> DSL | 1 |
| ventilator | Gherkin (BDD DSL) | 85 |
| ventilator | Finite State Machines / Statecharts | 30 |
| ventilator | xUnit Test Cases | 27 |
| ventilator | Use-Cases & User Stories | 21 |
| ventilator | GUI Event Graphs | 20 |
| ventilator | Decision Tables | 10 |
| ventilator | Temporal Logic (LTL) | 4 |
| ventilator | Sequence Diagrams | 4 |
| ventilator | FSM Path-Based Representations | 4 |
| ventilator | Natural Language -> DSL | 2 |
| ventilator | UML Testing Profile (UTP) | 1 |
| virtual_clinic | Gherkin (BDD DSL) | 133 |
| virtual_clinic | xUnit Test Cases | 48 |
| virtual_clinic | Use-Cases & User Stories | 46 |
| virtual_clinic | Decision Tables | 34 |
| virtual_clinic | Sequence Diagrams | 14 |
| virtual_clinic | UML Testing Profile (UTP) | 13 |
| virtual_clinic | Finite State Machines / Statecharts | 8 |
| virtual_clinic | GUI Event Graphs | 8 |
| virtual_clinic | Natural Language -> DSL | 6 |
| virtual_clinic | Transition Systems (S, T, I) | 2 |
| virtual_clinic | Feature Vectors & Distributions | 2 |
| virtual_clinic | Test Requirement Matrix | 2 |
| virtual_clinic | Financial/Rule Tables | 1 |
| virtual_clinic | Protocol State Machines | 1 |
| virtual_clinic | FSM Path-Based Representations | 1 |
| virtual_clinic | Interface Automata | 1 |
| virtual_clinic | Goal-Oriented (KAOS / i*) | 1 |

## Against the real implementation

**Execution (doorstop)** — all suites, and gate-passing suites only; coverage shown with the number of tests that produced it.

| project | model | tests | pass | fail | error | skipped | pass rate | pass rate (gate-passing) | code bugs | test bugs | line cov % | line cov % per 10 tests |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| doorstop | Qwen2.5-Coder-7B | 25 | 1 | 4 | 8 | 12 | 20% | 0% | 1 | 11 | 15.05 | 6.02 |
| doorstop | Llama-3.1-8B | 47 | 0 | 19 | 0 | 20 | 0% | 0% | 1 | 18 | 15.35 | 3.27 |
| doorstop | DeepSeek-Coder-V2-Lite | 27 | 0 | 11 | 0 | 16 | 0% | 0% | 0 | 11 | 14.52 | 5.38 |
| doorstop | Gemma-3-27B | 49 | 0 | 4 | 21 | 24 | 0% | 0% | 4 | 21 | 14.45 | 2.95 |
| doorstop | CodeGemma-7B | 16 | 0 | 5 | 0 | 11 | 0% | 0% | 0 | 5 | 14.82 | 9.26 |
| doorstop | Granite-4.1-8B | 38 | 0 | 3 | 8 | 20 | 0% | – | 1 | 10 | 14.52 | 3.82 |
| doorstop | Phi-3.5-mini | 46 | 0 | 5 | 0 | 41 | 0% | – | 0 | 5 | 14.52 | 3.16 |
| doorstop | Qwen3-30B-A3B | 10 | 0 | 0 | 0 | 10 | 0% | – | 0 | 0 | 0.00 | 0.00 |
| doorstop | Qwen2.5-Coder-32B | 33 | 1 | 8 | 9 | 15 | 11% | 11% | 0 | 17 | 14.85 | 4.50 |
| doorstop | Phi-3.5-MoE | 24 | 0 | 4 | 5 | 11 | 0% | 0% | 0 | 9 | 14.52 | 6.05 |

**Code audit (all projects)**

| project | model | tests | satisfied | violated | not impl | unclear | satisfied rate | satisfied (gate-passing) | violated (gate-passing) | SRS reqs with tests | SRS reqs reached in code |
|---|---|---|---|---|---|---|---|---|---|---|---|
| doorstop | Qwen2.5-Coder-7B | 25 | 0 | 0 | 4 | 21 | 0% | 0% | 0% | 100% | 0% |
| doorstop | Llama-3.1-8B | 47 | 2 | 0 | 3 | 42 | 4% | 4% | 0% | 100% | 15% |
| doorstop | DeepSeek-Coder-V2-Lite | 27 | 6 | 1 | 3 | 17 | 22% | 0% | 0% | 100% | 54% |
| doorstop | Gemma-3-27B | 49 | 9 | 0 | 5 | 35 | 18% | 18% | 0% | 100% | 23% |
| doorstop | CodeGemma-7B | 16 | 2 | 0 | 5 | 9 | 12% | 0% | 0% | 100% | 15% |
| doorstop | Granite-4.1-8B | 38 | 0 | 0 | 6 | 32 | 0% | 0% | 0% | 100% | 0% |
| doorstop | Phi-3.5-mini | 46 | 0 | 3 | 2 | 40 | 0% | – | – | 38% | 23% |
| doorstop | Qwen3-30B-A3B | 10 | 0 | 0 | 2 | 8 | 0% | 0% | 0% | 38% | 0% |
| doorstop | Qwen2.5-Coder-32B | 33 | 3 | 1 | 2 | 27 | 9% | 9% | 3% | 100% | 23% |
| doorstop | Phi-3.5-MoE | 24 | 8 | 0 | 1 | 15 | 33% | 75% | 0% | 100% | 46% |
| ventilator | Qwen2.5-Coder-7B | 228 | 13 | 6 | 80 | 128 | 6% | 6% | 4% | 95% | 7% |
| ventilator | Llama-3.1-8B | 209 | 11 | 7 | 49 | 138 | 5% | 6% | 3% | 92% | 14% |
| ventilator | CodeGemma-7B | 84 | 5 | 0 | 29 | 50 | 6% | 4% | 0% | 57% | 3% |
| ventilator | Granite-4.1-8B | 174 | 7 | 0 | 67 | 98 | 4% | 5% | 0% | 94% | 4% |
| ventilator | Phi-3.5-mini | 192 | 6 | 0 | 63 | 121 | 3% | 17% | 0% | 70% | 3% |
| ventilator | Qwen3-30B-A3B | 15 | 0 | 0 | 0 | 15 | 0% | 0% | 0% | 11% | 0% |
| ventilator | Qwen2.5-Coder-32B | 321 | 23 | 8 | 56 | 232 | 7% | 7% | 3% | 100% | 12% |
| ventilator | Phi-3.5-MoE | 173 | 12 | 6 | 69 | 85 | 7% | 9% | 5% | 89% | 15% |
| virtual_clinic | Qwen2.5-Coder-7B | 313 | 30 | 31 | 78 | 168 | 10% | 8% | 14% | 82% | 13% |
| virtual_clinic | Llama-3.1-8B | 369 | 37 | 16 | 122 | 190 | 10% | 9% | 4% | 92% | 15% |
| virtual_clinic | CodeGemma-7B | 191 | 19 | 9 | 43 | 117 | 10% | 23% | 0% | 60% | 10% |
| virtual_clinic | Granite-4.1-8B | 365 | 20 | 23 | 104 | 215 | 6% | 6% | 8% | 88% | 11% |
| virtual_clinic | Qwen3-30B-A3B | 74 | 10 | 0 | 23 | 39 | 14% | 21% | 0% | 23% | 2% |
| virtual_clinic | Qwen2.5-Coder-32B | 418 | 41 | 32 | 133 | 205 | 10% | 11% | 9% | 95% | 14% |
| virtual_clinic | Phi-3.5-MoE | 298 | 25 | 23 | 96 | 147 | 8% | 8% | 13% | 82% | 12% |

## Statistics

```
spearman_params_vs_FSA: (-0.015, 311)
spearman_active_params_vs_FSA: (0.047, 311)
spearman_params_vs_CC: (0.021, 308)
spearman_active_params_vs_CC: (0.016, 308)
spearman_params_vs_NC: (-0.03, 308)
spearman_active_params_vs_NC: (0.051, 308)
spearman_params_vs_BC: (-0.024, 308)
spearman_active_params_vs_BC: (0.029, 308)
spearman_params_vs_OA: (-0.003, 308)
spearman_active_params_vs_OA: (0.116, 308)
spearman_params_vs_Mg: (0.041, 308)
spearman_active_params_vs_Mg: (-0.063, 308)
spearman_params_vs_SFV: (0.048, 496)
spearman_active_params_vs_SFV: (0.439, 496)
spearman_params_vs_n_tests: (-0.114, 496)
spearman_active_params_vs_n_tests: (0.319, 496)
spearman_params_vs_repairs: (-0.094, 496)
spearman_active_params_vs_repairs: (-0.37, 496)
spearman_FSA_vs_exec_pass_rate: (0.433, 15)
spearman_FSA_vs_code_mismatch: (0.142, 24)
spearman_unit_size_vs_FSA: (0.087, 311)
mw_code_vs_general_FSA: (10902.0, 0.1407)
mw_code_vs_general_SFV: (36439.0, 0.0)
mw_small_vs_large_FSA: (9742.0, 0.1622)
mw_doorstop_vs_ventilator_FSA: (788.0, 0.0017)
repair_FSA_gain: {'n_repaired': 207, 'mean_gain': 0.131}
spearman_params_vs_FSA_fair: (0.021, 24)
spearman_active_params_vs_FSA_fair: (0.131, 24)
```

## Method notes

- Same extracted requirements, judge and executor model (gpt-oss-20b, a different family from all subjects) for every generator.
- Test generation used the SRS only; every suite was fingerprinted before the code was opened (checked).
- Ventilator and virtual-clinic: 1 representation per unit (the model's top Gate-1 pick); doorstop: 2 — time budget.
- Execution (doorstop, Python) runs the generated tests; audit mode (all projects) has the executor model judge each test against retrieved code excerpts.
- n = 1 run per model at temperature 0; differences of a few points are within noise.
