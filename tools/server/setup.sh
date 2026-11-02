#!/usr/bin/env bash
# Runs ON the GPU server. User space only: no sudo, nothing outside ~/clean_exp ($CLEAN_EXP_HOME).
# Expects ~/clean_exp/ollama.tar.zst (the Ollama release archive; not part of this repo) and
# start_ollama.sh next to this script.
set -euo pipefail
B="${CLEAN_EXP_HOME:-$HOME/clean_exp}"
mkdir -p "$B/ollama" "$B/models"
[ -x "$B/ollama/bin/ollama" ] || tar --zstd -xf "$B/ollama.tar.zst" -C "$B/ollama"
cp "$(dirname "${BASH_SOURCE[0]}")/start_ollama.sh" "$B/start_ollama.sh"
chmod +x "$B/start_ollama.sh"
if ! pgrep -u "$USER" -f "$B/ollama/bin/ollama serve" >/dev/null; then
  setsid nohup "$B/start_ollama.sh" > "$B/ollama.log" 2>&1 < /dev/null &
  sleep 5
fi
"$B/ollama/bin/ollama" --version
grep -iE "inference compute|gpu|cuda" "$B/ollama.log" | tail -5
