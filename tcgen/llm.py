"""
One LLM client for every stage.

- Model spec "<provider>:<model>". Providers are declared in config.yaml
  (`providers:`): any OpenAI-compatible endpoint (Groq, OpenAI, Gemini,
  Anthropic, OpenRouter, Together, DeepSeek, a vLLM server...) plus native
  Ollama. API keys come from .env via each provider's key_env.
- Retries with backoff on 429 / 5xx / network errors (honours Retry-After).
- NO mock fallback: if a call finally fails it raises LLMError, and the
  caller records the failure. (The old pipeline silently saved a canned
  mock reply as a "test suite" and scored it.)
- Disk cache keyed on a hash of (model, prompt, params): re-running a stage
  costs nothing and gives identical outputs.
- Every real call is appended to runs/llm_calls.jsonl (tokens, latency).
"""

import hashlib
import json
import os
import random
import re
import time
from pathlib import Path

import requests

from .util import CFG, ROOT, append_jsonl



class LLMError(RuntimeError):
    pass


def _cache_path(key: str) -> Path:
    d = ROOT / CFG["paths"]["cache_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


def call(spec: str, prompt: str, *, system: str = None, max_tokens: int = None,
         stage: str = "", use_cache: bool = True, think=None) -> str:
    provider, _, model = spec.partition(":")
    lc = CFG["llm"]
    params = {
        "temperature": lc["temperature"],
        "seed": lc["seed"],
        "max_tokens": max_tokens or lc["max_tokens"],
    }
    if think is not None:
        params["think"] = think          # Ollama reasoning level for this call only (e.g. gpt-oss "low")
    key = hashlib.sha256(json.dumps([spec, system, prompt, params], sort_keys=True).encode()).hexdigest()
    cp = _cache_path(key)
    if use_cache and cp.exists():
        return json.loads(cp.read_text())["text"]

    t0 = time.time()
    pconf = CFG.get("providers", {}).get(provider)
    if pconf is None:
        raise LLMError(f"unknown provider {provider!r} in model spec {spec!r} (add it under providers: in config.yaml)")
    if pconf.get("kind") == "ollama":
        text, usage = _ollama(pconf, model, prompt, system, params)
    else:
        text, usage = _openai_compat(pconf, provider, model, prompt, system, params)
    text = strip_think(text)
    if not text:
        raise LLMError(f"{spec} returned an empty response")

    cp.write_text(json.dumps({"spec": spec, "text": text}))
    append_jsonl(ROOT / CFG["paths"]["runs_dir"] / "llm_calls.jsonl", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": stage, "model": spec,
        "latency_s": round(time.time() - t0, 2), **usage,
    })
    return text


def _retrying(fn, what):
    lc = CFG["llm"]
    last = None
    for attempt in range(1, lc["max_retries"] + 1):
        try:
            return fn()
        except _Retry as r:
            last = r.reason
            wait = r.wait if r.wait is not None else lc["backoff_base_s"] * 2 ** (attempt - 1)
        except requests.RequestException as e:
            last = str(e)
            wait = lc["backoff_base_s"] * 2 ** (attempt - 1)
        wait = min(wait, 120) + random.uniform(0, 1)
        print(f"    [{what}] attempt {attempt} failed ({last}); retrying in {wait:.0f}s")
        time.sleep(wait)
    raise LLMError(f"{what}: gave up after {lc['max_retries']} attempts ({last})")


class _Retry(Exception):
    def __init__(self, reason, wait=None):
        self.reason, self.wait = reason, wait


def _openai_compat(pconf, provider, model, prompt, system, params):
    key = os.environ.get(pconf.get("key_env", ""), "")
    if pconf.get("key_env") and not key:
        raise LLMError(f"{pconf['key_env']} ({provider}) not set in .env")
    url = pconf["base_url"].rstrip("/") + "/chat/completions"
    body_params = {k: v for k, v in params.items() if k != "think"}   # Ollama-only option
    limit = pconf.get("max_request_tokens")       # e.g. Groq free tier counts prompt + max_tokens against 8K TPM
    if limit:
        est_prompt = int(len((system or "") + prompt) / 3.2) + 50
        body_params["max_tokens"] = max(256, min(body_params["max_tokens"], limit - est_prompt))
    if "max_tokens" in CFG.get("model_params", {}).get(model, {}):
        body_params["max_tokens"] = min(body_params["max_tokens"], CFG["model_params"][model]["max_tokens"])
    body_params.update(CFG.get("model_params", {}).get(model, {}))
    if pconf.get("no_seed"):
        body_params.pop("seed", None)
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]

    def once():
        r = requests.post(url, timeout=CFG["llm"]["timeout_s"],
                          headers={"Authorization": f"Bearer {key}"} if key else {},
                          json={"model": model, "messages": msgs, **body_params})
        if r.status_code == 429 or r.status_code >= 500:
            ra = r.headers.get("retry-after")
            try:
                msg = r.json().get("error", {}).get("message", "")[:160]
            except ValueError:
                msg = r.text[:160]
            if "per day" in msg:                    # daily quota: retrying within minutes is pointless
                raise LLMError(f"{provider} {model}: DAILY LIMIT reached -- {msg}")
            raise _Retry(f"HTTP {r.status_code} {msg}", float(ra) if ra else None)
        if r.status_code >= 400:
            raise LLMError(f"{provider} {model}: HTTP {r.status_code}: {r.text[:300]}")
        d = r.json()
        u = d.get("usage", {})
        return d["choices"][0]["message"].get("content") or "", {
            "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens")}

    return _retrying(once, f"{provider} {model}")


def _ollama(pconf, model, prompt, system, params):
    lc = CFG["llm"]
    base = pconf.get("base_url", "http://localhost:11434").rstrip("/")

    think = params.get("think")
    if think is None:          # per-model default, e.g. qwen3 "thinking" models: off, else the answer can come back empty
        think = CFG.get("model_params", {}).get(model, {}).get("think")

    def once():
        body = {
            "model": model, "prompt": prompt, "system": system or "", "stream": False,
            "options": {"temperature": params["temperature"], "seed": params["seed"],
                        "num_predict": params["max_tokens"], "num_ctx": lc["ollama_num_ctx"]}}
        if think is not None:
            body["think"] = think
        r = requests.post(f"{base}/api/generate", timeout=lc["timeout_s"], json=body)
        if r.status_code >= 500:
            raise _Retry(f"HTTP {r.status_code}")
        if r.status_code >= 400:
            raise LLMError(f"ollama {model}: HTTP {r.status_code}: {r.text[:300]}")
        d = r.json()
        return d.get("response", ""), {"prompt_tokens": d.get("prompt_eval_count"),
                                       "completion_tokens": d.get("eval_count")}

    return _retrying(once, f"ollama {model}")


# ---------------------------------------------------------------- parsing helpers

def extract_json(text: str):
    """Pull the first JSON object/array out of an LLM reply (fenced or bare).
    Returns None if nothing parses."""
    if not text:
        return None
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text):
        v = _loads(m.group(1))
        if v is not None:
            return v
    for opener, closer in (("{", "}"), ("[", "]")):
        s, e = text.find(opener), text.rfind(closer)
        if s != -1 and e > s:
            v = _loads(text[s:e + 1])
            if v is not None:
                return v
    return None


def _loads(s):
    """json.loads with two common LLM slips repaired: trailing commas, and
    numbers written with thousands separators (e.g. "amount": 3,000)."""
    for fix in (lambda x: x,
                lambda x: re.sub(r",\s*([}\]])", r"\1", x),
                lambda x: re.sub(r"(?<=[:\[]\s)(\d{1,3}(?:,\d{3})+)(?=\s*[,}\]\n])|(?<=[:\[])(\d{1,3}(?:,\d{3})+)(?=\s*[,}\]\n])",
                                 lambda m: (m.group(1) or m.group(2)).replace(",", ""), re.sub(r",\s*([}\]])", r"\1", x))):
        try:
            return json.loads(fix(s))
        except json.JSONDecodeError:
            continue
    return None


def extract_block(text: str, tag: str):
    """Content of a ```<tag> ... ``` fenced block, or None."""
    m = re.search(rf"```{re.escape(tag)}\s*\n([\s\S]*?)```", text or "")
    return m.group(1).strip() if m else None
