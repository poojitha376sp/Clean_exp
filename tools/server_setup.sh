#!/usr/bin/env bash
# Runs ON rubyserc as user serc. User space only: no sudo, nothing outside ~/clean_exp.
set -euo pipefail
B=~/clean_exp
mkdir -p "$B/ollama" "$B/models"
[ -x "$B/ollama/bin/ollama" ] || tar --zstd -xf "$B/ollama.tar.zst" -C "$B/ollama"
cat > "$B/start_ollama.sh" <<EOS
#!/usr/bin/env bash
# Ollama on 127.0.0.1 only (reach it through an SSH tunnel), models kept in ~/clean_exp/models.
# nv/ = user-space copy of the NVIDIA 580.126.09 libs that match the loaded kernel driver.
export LD_LIBRARY_PATH=$B/nv:\${LD_LIBRARY_PATH:-}
export OLLAMA_MODELS=$B/models OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_KEEP_ALIVE=30m OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=16384
exec $B/ollama/bin/ollama serve
EOS
chmod +x "$B/start_ollama.sh"
if ! pgrep -u "$USER" -f "$B/ollama/bin/ollama serve" >/dev/null; then
  setsid nohup "$B/start_ollama.sh" > "$B/ollama.log" 2>&1 < /dev/null &
  sleep 5
fi
"$B/ollama/bin/ollama" --version
grep -iE "inference compute|gpu|cuda" "$B/ollama.log" | tail -5
