#!/usr/bin/env bash
# 2026-09-27 (user: "download all the LLMs in the 14 and do all pairs"): every open model x every project.
# Fast models first, slow ones (DeepSeek on CPU kernels, Llama-70B > 32 GB VRAM) last.
# Waits for each model's download; after a model's generation, its code comparison runs in the background.
cd "$(dirname "$0")/.."
L=runs/run_all.log
have() { curl -s -m 10 localhost:11435/api/tags | grep -q "\"name\":\"$1\""; }
code_phase() {
  local g=$1; shift
  for p in "$@"; do
    if [ "$p" = doorstop ]; then .venv/bin/python -u -m tcgen.run --project doorstop --stages S6,S6A --gen "$g" >> runs/doorstop.S6.log 2>&1
    else .venv/bin/python -u -m tcgen.run --project "$p" --stages S6A --gen "$g" >> "runs/$p.S6A.log" 2>&1; fi
  done
  echo "$(date +%T) CODE-DONE $g : $*" >> $L
}
gen() {  # gen <ollama tag> <projects...>
  local tag=$1; shift; local g="ollama:$tag"
  local waited=0
  until have "$tag"; do [ $waited = 0 ] && echo "$(date +%T) WAIT-DOWNLOAD $tag" >> $L; waited=1; sleep 60; done
  echo "$(date +%T) MODEL $g : $*" >> $L
  for p in "$@"; do .venv/bin/python -u -m tcgen.run --project "$p" --stages S2,S3 --gen "$g" >> "runs/$p.run.log" 2>&1 & done
  wait
  echo "$(date +%T) MODEL-DONE $g" >> $L
  code_phase "$g" "$@" &
}
ALL="doorstop ventilator virtual_clinic"
gen codegemma:7b $ALL
gen granite4.1:8b $ALL
gen phi3.5:3.8b ventilator virtual_clinic
code_phase ollama:phi3.5:3.8b doorstop &
gen qwen3:30b-a3b $ALL
gen qwen2.5-coder:32b $ALL
gen hf.co/bartowski/Phi-3.5-MoE-instruct-GGUF:Q4_K_M $ALL
gen hf.co/bartowski/phi-4-GGUF:Q4_K_M $ALL
gen gemma3:27b ventilator virtual_clinic
gen deepseek-coder-v2:16b ventilator virtual_clinic
gen llama3.3:70b $ALL
wait
echo "$(date +%T) ALL-PAIRS-DONE" >> $L
