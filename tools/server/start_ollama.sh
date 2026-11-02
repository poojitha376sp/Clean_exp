#!/usr/bin/env bash
# Starts the Ollama server exactly as used for the reported runs (Ollama 0.34.4, single GPU).
# Binds to 127.0.0.1 only; reach it through an SSH tunnel (tunnel_keepalive.sh) or run it on the same
# machine as the pipeline. Everything lives under $CLEAN_EXP_HOME (default: ~/clean_exp).
B="${CLEAN_EXP_HOME:-$HOME/clean_exp}"

# Optional: user-space copy of the NVIDIA driver libraries matching the loaded kernel driver (used when
# the installed userspace libs do not match; skip this line if your driver is consistent).
[ -d "$B/nv" ] && export LD_LIBRARY_PATH="$B/nv:${LD_LIBRARY_PATH:-}"

export OLLAMA_MODELS="$B/models"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_CONTEXT_LENGTH=12288      # = llm.ollama_num_ctx in config.yaml
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0        # quantised KV cache (the models themselves are quantised too, mostly Q4_K_M)
export OLLAMA_NUM_PARALLEL=3            # = pipeline.workers in config.yaml
export OLLAMA_MAX_LOADED_MODELS=3
export OLLAMA_KEEP_ALIVE=30m
export OLLAMA_VULKAN=1
exec "$B/ollama/bin/ollama" serve
