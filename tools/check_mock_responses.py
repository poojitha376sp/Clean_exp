#!/usr/bin/env python3
"""Scan the prompt cache and the saved results for canned/mock LLM responses.

The current client (tcgen/llm.py) has no mock fallback: a failed call raises LLMError / LLMFatal.
The *old* pipeline used to save a canned reply as a "test suite", so this checks that none of that
text is in the data the paper's numbers come from.

  python3 tools/check_mock_responses.py [--cache .cache/llm] [--runs runs]

Hits are candidates for manual review (--show prints them): judge comments and test inputs that merely
talk about mocks in xUnit tests also match. Prints the number of hits per model and exits 1 if there is any hit (0 otherwise). A missing cache
directory is reported, not an error: the cache is distributed separately (README).
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Deliberately narrow: ordinary uses of "mock" in generated tests (unittest.mock, mock_network_delay...)
# must not match, only text that describes the response itself as a stand-in.
MOCK = re.compile(
    r"\[MOCK|MOCK[_ ]RESPONSE|\bmock(?:ed)?\s+(?:response|reply|llm|completion|suite|output)\b"
    r"|\bthis is a (?:mock|dummy|placeholder|canned)\b|\b(?:dummy|canned|placeholder) (?:response|reply)\b"
    r"|\blorem ipsum\b|\bresponse unavailable\b|\bfallback (?:response|mock)\b", re.I)


def scan_cache(d: Path, ok=frozenset()):
    hits, total = Counter(), Counter()
    for f in d.glob("*.json"):
        try:
            j = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        spec = j.get("spec", "?")
        total[spec] += 1
        if MOCK.search(j.get("text", "")) and f"cache:{f.stem[:12]}" not in ok:
            hits[spec] += 1
    return hits, total


def reviewed(root: Path) -> set:
    """Entries inspected by hand that are NOT mock responses: paths relative to runs/, or cache:<first 12 hex of the file name>."""
    f = root / "tools" / "mock_scan_reviewed.txt"
    if not f.exists():
        return set()
    return {ln.split("#")[0].strip() for ln in f.read_text().splitlines() if ln.split("#")[0].strip()}


def scan_runs(d: Path, show=False, ok=frozenset()):
    hits, total = Counter(), Counter()
    for f in d.glob("*/*/S3_S5_suites/*.json"):          # runs/<project>/<model>/S3_S5_suites/*.json
        model = f.parts[-3]
        total[model] += 1
        text = f.read_text(errors="ignore")
        m = MOCK.search(text)
        if m and str(f.relative_to(d)) not in ok:
            hits[model] += 1
            if show:
                print(f"  {f.relative_to(d)}: ...{text[max(0, m.start() - 80):m.end() + 60]!r}...")
    return hits, total


def report(title, hits, total):
    print(f"\n{title}: {sum(total.values())} files, {sum(hits.values())} with mock-response text")
    for m in sorted(total):
        print(f"  {m:75s} {hits[m]:5d} / {total[m]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--cache", default=str(root / ".cache/llm"))
    ap.add_argument("--runs", default=str(root / "runs"))
    ap.add_argument("--show", action="store_true", help="print the matching snippet of every hit")
    a = ap.parse_args()
    bad = 0
    ok = reviewed(root)
    if Path(a.cache).is_dir():
        h, t = scan_cache(Path(a.cache), ok); report("cache", h, t); bad += sum(h.values())
    else:
        print(f"cache not found at {a.cache} (not scanned; see README 'Exact re-run without a GPU')")
    h, t = scan_runs(Path(a.runs), a.show, ok); report("saved suites", h, t); bad += sum(h.values())
    print(f"({len(ok)} hits manually reviewed and allow-listed in tools/mock_scan_reviewed.txt)")
    print("\nRESULT:", "no mock-response text found" if not bad else f"{bad} suspicious files")
    sys.exit(1 if bad else 0)
