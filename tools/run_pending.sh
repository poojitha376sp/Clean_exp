#!/usr/bin/env bash
# 2026-09-27: run the pending (model, projects) pairs, one model at a time.
# After each model's generation, its code comparison runs in the background
# (executor = gpt-oss only) while the next model generates.
cd "$(dirname "$0")/.."
L=runs/run_all.log
code_phase() {  # code_phase <model> <projects...>
  local g=$1; shift
  for p in "$@"; do
    if [ "$p" = doorstop ]; then
      .venv/bin/python -u -m tcgen.run --project doorstop --stages S6,S6A --gen "$g" >> runs/doorstop.S6.log 2>&1
    else
      .venv/bin/python -u -m tcgen.run --project "$p" --stages S6A --gen "$g" >> "runs/$p.S6A.log" 2>&1
    fi
  done
  echo "$(date +%T) CODE-DONE $g : $*" >> $L
}
gen() {  # gen <model> <projects...>
  local g=$1; shift
  echo "$(date +%T) MODEL $g : $*" >> $L
  for p in "$@"; do .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 --gen "$g" >> "runs/$p.run.log" 2>&1 & done
  wait
  echo "$(date +%T) MODEL-DONE $g" >> $L
  code_phase "$g" "$@" &
}
gen ollama:deepseek-coder-v2:16b ventilator virtual_clinic
gen ollama:gemma3:27b ventilator virtual_clinic
gen ollama:codegemma:7b doorstop ventilator virtual_clinic
gen ollama:granite4.1:8b doorstop ventilator virtual_clinic
gen ollama:phi3.5:3.8b ventilator virtual_clinic
code_phase ollama:phi3.5:3.8b doorstop        # phi3.5 doorstop suites exist from 2026-09-26
wait
echo "$(date +%T) PENDING-ALL-DONE" >> $L
