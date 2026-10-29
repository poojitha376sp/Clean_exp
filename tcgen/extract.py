"""
S1 -- extract atomic requirements from the SRS text, then group them into
test units.

Same extractor model for every generator (config models.extractor), so all
generators are tested on identical requirements.

Outputs  runs/<p>/S1_requirements.json   every requirement
         runs/<p>/S1_units.json          test units = a section's testable
                                         requirements (split to <= unit_max_reqs),
                                         plus the out-of-unit requirements they reference
"""

import re
from collections import OrderedDict

from . import llm
from .util import CFG, prompt, read_json, run_dir, write_json

CHUNK_CHARS = 3500      # small enough for Groq free-tier per-minute input/output limits


def _chunks(text):
    """Split on blank lines near CHUNK_CHARS so sections mostly stay whole;
    PDF text often has no blank lines, so over-long blocks split on lines."""
    paras, cur, out = [], "", []
    for block in text.split("\n\n"):
        if len(block) <= CHUNK_CHARS:
            paras.append(block)
            continue
        piece = ""
        for line in block.split("\n"):
            if len(piece) + len(line) > CHUNK_CHARS and piece:
                paras.append(piece)
                piece = ""
            piece += line + "\n"
        if piece.strip():
            paras.append(piece)
    for p in paras:
        if len(cur) + len(p) > CHUNK_CHARS and cur:
            out.append(cur)
            cur = ""
        cur += p + "\n\n"
    if cur.strip():
        out.append(cur)
    return out


def _dedupe_ids(reqs):
    seen = {}
    for r in reqs:
        base = str(r.get("id") or "R").strip()
        n = seen.get(base, 0)
        seen[base] = n + 1
        r["id"] = base if n == 0 else f"{base}#{n + 1}"
    return reqs


def _section_key(sec):
    """Group by chapter ("4.2.1" -> "4"); unnumbered headings ("Alarms") by name.
    Units are then split evenly to <= unit_max_reqs, so a big chapter still
    yields several small units while tiny subsections don't become 1-req units."""
    parts = re.findall(r"\d+", str(sec or ""))
    if parts:
        return parts[0]
    return re.sub(r"[^A-Za-z0-9]+", "_", str(sec or "misc")).strip("_")[:20] or "misc"


def build_units(reqs, max_reqs):
    by_id = {r["id"]: r for r in reqs}
    by_section = OrderedDict()
    for r in reqs:
        by_section.setdefault(_section_key(r.get("section")), []).append(r)
    units = []
    for sec, rs in by_section.items():
        testable = [r for r in rs if r.get("testable")]
        n_units = -(-len(testable) // max_reqs) if testable else 0
        size = -(-len(testable) // n_units) if n_units else 1          # balanced split, e.g. 10 -> 5+5 not 8+2
        for i in range(0, len(testable), size):
            members = testable[i:i + size]
            member_ids = {r["id"] for r in members}
            deps = []
            for r in members:
                for ref in r.get("refs") or []:
                    ref = str(ref)
                    targets = [by_id[ref]] if ref in by_id else [x for x in reqs if str(x.get("section", "")).startswith(ref) and x.get("testable")][:3]
                    deps += [t for t in targets if t["id"] not in member_ids and t not in deps]
            title = members[0].get("section_title") or ""
            units.append({"unit_id": f"U{len(units) + 1:02d}_{sec}", "section": sec, "title": title,
                          "req_ids": [r["id"] for r in members], "reqs": members, "deps": deps[:8]})
    return _merge_small(units, max_reqs)


def _merge_small(units, max_reqs):
    """Merge neighbouring units while the result stays <= max_reqs, so 1-3
    requirement fragments (e.g. a numbered feature list) don't become units."""
    merged = []
    for u in units:
        if merged and len(merged[-1]["req_ids"]) + len(u["req_ids"]) <= max_reqs and \
                (len(merged[-1]["req_ids"]) < max_reqs // 2 or len(u["req_ids"]) < max_reqs // 2):
            m = merged[-1]
            m["section"] = f"{m['section']}+{u['section']}" if u["section"] not in m["section"].split("+") else m["section"]
            m["req_ids"] += u["req_ids"]
            m["reqs"] += u["reqs"]
            m["deps"] = [d for d in m["deps"] + u["deps"] if d["id"] not in m["req_ids"]][:8]
        else:
            merged.append(u)
    for i, u in enumerate(merged, 1):
        u["unit_id"] = f"U{i:02d}_{u['section'].split('+')[0]}"
    return merged


def run(project):
    rd = run_dir(project)
    if (rd / "S0_items.json").exists():                  # SRS lists its own requirement items
        reqs = _dedupe_ids(read_json(rd / "S0_items.json"))
        write_json(rd / "S1_requirements.json", {"requirements": reqs, "failures": [], "source": "structured items (no LLM)"})
        units = build_units(reqs, CFG["pipeline"]["unit_max_reqs"])
        write_json(rd / "S1_units.json", units)
        print(f"  S1 {len(reqs)} requirements taken verbatim from the SRS items -> {len(units)} units")
        return units
    text = (rd / "S0_srs.txt").read_text()
    chunks = _chunks(text)
    prefix = re.sub(r"[^A-Za-z0-9]", "", project)[:6].upper() + "-"
    reqs, failures = [], []
    for i, ch in enumerate(chunks, 1):
        print(f"  S1 extracting chunk {i}/{len(chunks)}")
        try:
            raw = llm.call(CFG["models"]["extractor"], prompt("extract", PREFIX=prefix, DOC=project, PART=str(i), CHUNK=ch),
                           stage="S1_extract")
        except llm.LLMError as e:
            failures.append({"chunk": i, "error": str(e)})
            continue
        items = llm.extract_json(raw)
        if not isinstance(items, list):
            failures.append({"chunk": i, "error": "unparseable", "raw": raw[:500]})
            continue
        reqs += [r for r in items if isinstance(r, dict) and r.get("text")]
    reqs = _dedupe_ids(reqs)
    write_json(rd / "S1_requirements.json", {"requirements": reqs, "failures": failures})
    units = build_units(reqs, CFG["pipeline"]["unit_max_reqs"])
    write_json(rd / "S1_units.json", units)
    n_test = sum(1 for r in reqs if r.get("testable"))
    print(f"  S1 {len(reqs)} requirements ({n_test} testable) -> {len(units)} units; {len(failures)} chunk failures")
    return units


def rebuild_units(project):
    """Re-group existing S1 requirements into units (no LLM call)."""
    rd = run_dir(project)
    reqs = read_json(rd / "S1_requirements.json")["requirements"]
    units = build_units(reqs, CFG["pipeline"]["unit_max_reqs"])
    write_json(rd / "S1_units.json", units)
    return units


def load_units(project):
    return read_json(run_dir(project) / "S1_units.json")
