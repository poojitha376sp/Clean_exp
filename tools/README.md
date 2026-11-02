# tools/ — running and analysing the experiment

All commands are run from the repo root. The project inputs are in `inputs/`; API keys and GPU credentials come from `../.env` (one level above the repo).

## Layout

| path | what it is |
|---|---|
| `run_experiment.sh` | **The driver.** Every generator in `config.yaml` x every project: generation (S2,S3), then code stage (S6/S6A). |
| `lib.sh` | Helpers sourced by the driver (`log`, `generate`, `code_phase`, waiting for server/model). |
| `server/` | Everything for the GPU server (rubyserc): tunnel, SSH helper, Ollama install, model pulls. |
| `reproduce.sh` | Rebuilds `runs/ANALYSIS/*`, sensitivity and figures from the committed data; PASS/FAIL per file. No GPU. |
| `check_mock_responses.py` | Scans the cache and saved suites for stand-in (mock) answers; `mock_scan_reviewed.txt` lists the hand-reviewed false positives. |
| `sensitivity.py` | Weight-sensitivity check of Gate 1 (RSS) and Gate 3 (FSA). Cited in the paper. |
| `verify_threshold_claim.py` | Checks the paper's claim that design-document thresholds fail >70% of suites at Gate 2. |
| `legacy/` | The 13 one-off scripts that actually ran the experiment in September 2026. Archived, not for reuse. |

## Running the experiment

```bash
tools/server/tunnel_keepalive.sh &          # localhost:11435 -> server Ollama; reconnects on drops
tools/run_experiment.sh                     # everything; resumable
tools/run_experiment.sh --phase gen         # generation only
tools/run_experiment.sh --phase code        # S6/S6A only
tools/run_experiment.sh --offline           # no GPU: every call must come from .cache/llm, else abort
tools/run_experiment.sh --projects "doorstop" --models "qwen2.5-coder:7b llama3.1:8b"
```

- **Resumable.** Finished suites are skipped and LLM calls come from `.cache/llm`. After an outage, just run it again; it waits for the server and for each model to be pulled.
- **Model-major order.** One model at a time, its projects in parallel, so only generator + judge sit in GPU memory (no swapping). The model list and order come from `models.generators` in `config.yaml`.
- **Tests are generated without seeing the code.** Stages S2-S3 read only the SRS; the code in `inputs/<project>/code/` is read only by S6 (execution) and S6A (audit). Only `doorstop` runs generated tests (S6); ventilator (C++ firmware) and virtual_clinic get the code audit (S6A) only.
- Logs: `runs/run_all.log` (one line per step), `runs/<project>.run.log` and `runs/<project>.S6.log` (full output).

## server/

| script | where it runs | purpose |
|---|---|---|
| `tunnel_keepalive.sh` | your machine | Self-healing SSH tunnel `localhost:11435 -> server:11434`. Leave it running. |
| `gpu_ssh.sh` | your machine | Run one command on the server (`gpu_ssh.sh 'nvidia-smi'`), or `--tunnel` for a one-shot tunnel on the same port. Refuses reboot/shutdown/sudo. |
| `setup.sh` | the server | User-space Ollama install and `start_ollama.sh` (localhost only, one model loaded, 16k context). |
| `pull_models.sh` | the server | Pulls the 12 subjects plus `gpt-oss:20b` (judge/executor), smallest first. Log: `~/clean_exp/pull.log`. |
| `start_ollama.sh` | the server | Starts Ollama with the exact settings of the reported runs (context 12288, flash attention, q8_0 KV cache, 3 parallel). |
| `_credentials.sh` | (sourced) | Loads `GPU_USER`, `GPU_HOST` and `GPU_SSH_KEY` (or the optional `GPU_PASS`) from `../.env`; template: `.env.example`. |

Port **11435** is used everywhere on your side (`config.yaml`, `lib.sh`, both tunnel scripts); 11434 is only the server's own Ollama port.

## Analysis scripts

```bash
python3 -B tools/sensitivity.py             # writes runs/ANALYSIS/sensitivity.json
python3 -B tools/verify_threshold_claim.py  # prints the threshold-claim check
```
Both read only committed data (`runs/ANALYSIS/suites.csv`, `runs/*/S1_units.json`), need no GPU, and need `numpy`, `pandas`, `scipy`.
What the sensitivity numbers mean: [docs/PIPELINE.md, "Gate weights and sensitivity"](../docs/PIPELINE.md#gate-weights-thresholds-and-sensitivity).

## legacy/ (what ran, in order)

The experiment was driven by hand-written scripts that grew as the plan changed. `run_experiment.sh` replaces them. Kept only so the history is auditable.

| script | what it did |
|---|---|
| `run_all.sh`, `run_reverse.sh` | Two workers over the generator list, forward and reverse, meeting in the middle. |
| `run_by_model.sh` | First model-major driver (generator list from config). |
| `run_plan.sh` -> `run_plan2.sh` -> `run_plan3.sh` | Successive plans for doorstop/ventilator subsets (Phi-4 dropped as unusable; Gemma-3 swapped in). |
| `doorstop_code_phase.sh`, `ventilator_code_phase.sh`, `vc_phase.sh` | Per-project code phase, started when generation finished. |
| `code_phase_v2.sh` | Code comparison re-run with per-test-case retrieval and a codebase map. |
| `run_pending.sh`, `run_all_pairs.sh` | 2026-09-27: "all 12 models x all projects", with the code phase in the background. |
| `resume_after_outage.sh` | Same as `run_all_pairs.sh` after the 2026-09-27 network outage, plus re-audits of failed batches. |

They `cd` to the repo root via `../..`, so they still run from `tools/legacy/`. They predate the move of the inputs into the repo and still refer to `../inputs` and `../.code_staging`; use `run_experiment.sh` instead.
