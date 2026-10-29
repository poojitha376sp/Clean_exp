#!/usr/bin/env bash
# Resume after the 2026-09-27 ~20:00 network outage (server unreachable). Waits until the
# GPU server answers, then: redo broken/missing suites, re-audit partly failed audits,
# then the models still to run. Finished suites and cached calls are reused.
cd "$(dirname "$0")/.."
L=runs/run_all.log
until curl -s -m 5 localhost:11435/api/version > /dev/null; do sleep 30; done
echo "$(date +%T) SERVER BACK -> resume" >> $L
have() { curl -s -m 10 localhost:11435/api/tags | grep -q "\"name\":\"$1\""; }
code_phase() { local g=$1; shift
  for p in "$@"; do
    if [ "$p" = doorstop ]; then .venv/bin/python -u -m tcgen.run --project doorstop --stages S6,S6A --gen "$g" >> runs/doorstop.S6.log 2>&1
    else .venv/bin/python -u -m tcgen.run --project "$p" --stages S6A --gen "$g" >> "runs/$p.S6A.log" 2>&1; fi
  done; echo "$(date +%T) CODE-DONE $g : $*" >> $L; }
gen() { local tag=$1; shift; local g="ollama:$tag"; local w=0
  until have "$tag"; do [ $w = 0 ] && echo "$(date +%T) WAIT-DOWNLOAD $tag" >> $L; w=1; sleep 60; done
  echo "$(date +%T) MODEL $g : $*" >> $L
  for p in "$@"; do .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 --gen "$g" >> "runs/$p.run.log" 2>&1 & done
  wait; echo "$(date +%T) MODEL-DONE $g" >> $L
  code_phase "$g" "$@"; }
ALL="doorstop ventilator virtual_clinic"
# 1) fix what the outage / qwen3 thinking broke
gen qwen3:30b-a3b $ALL
gen hf.co/bartowski/Phi-3.5-MoE-instruct-GGUF:Q4_K_M $ALL
gen phi3.5:3.8b ventilator virtual_clinic
# 2) redo audits that had failed calls (only the failed batches are re-sent; the rest is cached)
for g in qwen2.5-coder:7b qwen2.5-coder:32b llama3.1:8b granite4.1:8b codegemma:7b phi3.5:3.8b; do code_phase "ollama:$g" ventilator virtual_clinic; done
code_phase ollama:phi3.5:3.8b doorstop
# 3) models still to run
gen hf.co/bartowski/phi-4-GGUF:Q4_K_M $ALL
gen gemma3:27b ventilator virtual_clinic
gen deepseek-coder-v2:16b ventilator virtual_clinic
gen llama3.3:70b $ALL
echo "$(date +%T) ALL-PAIRS-DONE" >> $L
