#!/usr/bin/env bash
# Runs ON rubyserc. Pulls the 12 open-weights subjects, smallest first, so
# models become usable one by one. Progress/result lines go to ~/clean_exp/pull.log.
B=~/clean_exp
export OLLAMA_HOST=127.0.0.1:11434
O="$B/ollama/bin/ollama"
MODELS=(
  gpt-oss:20b                 # fixed judge + executor (not a subject)
  phi3.5:3.8b                 # Phi-3.5-mini
  qwen2.5-coder:7b
  llama3.1:8b
  codegemma:7b
  granite4.1:8b               # Granite-4.1-8B (no separate -code tag exists in the registry)
  phi4:14b
  deepseek-coder-v2:16b       # DeepSeek-Coder-V2-Lite
  gemma3:27b
  qwen3:30b-a3b
  qwen2.5-coder:32b
  hf.co/bartowski/Phi-3.5-MoE-instruct-GGUF:Q4_K_M   # not in the Ollama library
  llama3.3:70b                # 43 GB: larger than the 32 GB GPU -> partial CPU offload
)
for m in "${MODELS[@]}"; do
  echo "$(date +%T) START $m" >> "$B/pull.log"
  if "$O" pull "$m" > "$B/pull_current.log" 2>&1; then
    echo "$(date +%T) OK $m" >> "$B/pull.log"
  else
    echo "$(date +%T) FAIL $m $(tail -1 $B/pull_current.log)" >> "$B/pull.log"
  fi
done
echo "$(date +%T) ALL_DONE" >> "$B/pull.log"
