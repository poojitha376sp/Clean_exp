"""
S6 (audit mode) -- language-agnostic comparison of generated tests with the
real implementation, for code that can't be built/run here (C++ firmware,
legacy web apps).

For every suite: freeze (same as execution mode), retrieve the code excerpts
most related to the suite's test cases (identifier-overlap search over the
repo), and ask the fixed executor model for a per-case verdict:
satisfied | violated | not_implemented | unclear.

Outputs runs/<p>/<gen>/S6_audit.json. Per requirement, "reached by code" =
at least one of its test cases judged satisfied or violated (i.e. the code
implements that behaviour, correctly or not).
"""

import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from . import llm, suite
from .execute import SKIP_DIRS, freeze
from .represent import fmt_reqs
from .util import CFG, inputs_dir, prompt, run_dir, slug, write_json
from .extract import load_units

CODE_EXT = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".go",
            ".rb", ".php", ".kt", ".html", ".qml", ".ino"}
CHUNK_LINES = 60
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]+")
STOP = set("the a an and or of to in for with on is are be shall must should will when then given that this "
           "from by as at it if not no into its test case expected system user verify check".split())


def _tokens(text):
    out = []
    for t in TOKEN.findall(text):
        for part in re.sub(r"([a-z])([A-Z])", r"\1 \2", t).replace("_", " ").split():
            p = part.lower()
            if len(p) > 2 and p not in STOP:
                out.append(p[:12])
    return out


def _is_vendored(rel, lines):
    """Minified / third-party bundles (jquery.min.js, MathJax...) would swamp retrieval."""
    return (".min." in rel or re.search(r"(^|/)(vendor|third_party|node_modules|static/lib)/", rel) is not None
            or any(len(l) > 1000 for l in lines[:200]))


class CodeIndex:
    def __init__(self, root):
        self.chunks = []
        self.file_map = {}                    # rel path -> def/class names (compact map of the codebase)
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix not in CODE_EXT or set(p.relative_to(root).parts) & SKIP_DIRS:
                continue
            rel = str(p.relative_to(root))
            if re.search(r"(^|/)(tests?|__tests__|test_\w+)(/|\.)|_test\.|\.test\.|Test\.java$|migrations/", rel):
                continue                      # never show the project's own tests
            lines = p.read_text(errors="ignore").splitlines()
            if _is_vendored(rel, lines):
                continue
            text = "\n".join(lines)
            if p.suffix == ".py":
                names = re.findall(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", text, re.MULTILINE)
            else:   # C/C++/Java/JS-style declarations: "type name(args) {" or "class Name"
                names = re.findall(r"^\s*(?:class|struct)\s+(\w+)|^[\w:<>*&\s]*?\b(\w+)\s*\([^;{}]*\)\s*(?:const)?\s*\{?\s*$", text, re.MULTILINE)
                names = [a or b for a, b in names]
            keep = [n for n in dict.fromkeys(names) if n and not n.startswith("_") and n not in ("if", "for", "while", "switch", "return")]
            self.file_map[rel] = keep[:25]
            for i in range(0, len(lines), CHUNK_LINES):
                body = "\n".join(lines[i:i + CHUNK_LINES])
                if body.strip():
                    self.chunks.append((f"{rel}:{i + 1}", body, Counter(_tokens(rel + " " + body))))
        df = Counter(t for _, _, c in self.chunks for t in c)
        n = max(1, len(self.chunks))
        import math
        self.idf = {t: math.log(n / (1 + d)) + 1 for t, d in df.items()}

    def map_text(self, budget_chars=6000, queries=None):
        """Compact file -> functions map; with queries, most relevant files first."""
        order = list(self.file_map)
        if queries:
            score = Counter()
            for q in queries:
                for rank, (loc, _) in enumerate(self._rank(q)):
                    score[loc.split(":")[0]] += 6 - rank
            order.sort(key=lambda f: -score[f])
        out, used = [], 0
        for rel in order:
            names = self.file_map[rel]
            line = f"{rel}: {', '.join(names)}" if names else rel
            if used + len(line) > budget_chars:
                out.append(f"... ({len(self.file_map) - len(out)} more files)")
                break
            out.append(line)
            used += len(line) + 1
        return "\n".join(out)

    def search_many(self, queries, budget_chars, per_query=2):
        """Top chunks for EACH query (one per test case), merged -- so every
        case gets code related to it, not one blended search per batch."""
        picked, seen, used = [], set(), 0
        ranked = [self._rank(q) for q in queries]
        for depth in range(per_query):
            for r in ranked:
                if depth < len(r):
                    loc, body = r[depth]
                    if loc in seen:
                        continue
                    block = f"--- {loc} ---\n{body}\n"
                    if used + len(block) > budget_chars:
                        continue
                    seen.add(loc)
                    picked.append(block)
                    used += len(block)
        return "".join(picked) or "(no related code found)"

    def _rank(self, query):
        q = Counter(_tokens(query))
        scored = []
        for loc, body, c in self.chunks:
            s = sum(self.idf.get(t, 0) * min(c[t], 3) * w for t, w in q.items() if t in c)
            if s > 0:
                scored.append((s, loc, body))
        return [(loc, body) for s, loc, body in sorted(scored, reverse=True)[:6]]

    def search(self, query, budget_chars):
        q = Counter(_tokens(query))
        scored = []
        for loc, body, c in self.chunks:
            s = sum(self.idf.get(t, 0) * min(c[t], 3) * w for t, w in q.items() if t in c)
            if s > 0:
                scored.append((s, loc, body))
        out, used = [], 0
        for s, loc, body in sorted(scored, reverse=True):
            block = f"--- {loc} ---\n{body}\n"
            if used + len(block) > budget_chars:
                continue
            out.append(block)
            used += len(block)
            if used > budget_chars * 0.95:
                break
        return "".join(out) or "(no related code found)"


def run(project, gen):
    gen_dir = run_dir(project) / slug(gen)
    suites = [s for s in suite.load_all(project, gen) if s.get("test_cases")]
    if not suites:
        print(f"  S6-audit [{gen}] no suites; skipping")
        return None
    frozen = freeze(suites, gen_dir / "S6_frozen_audit.json")             # before any code access
    index = CodeIndex(inputs_dir(project) / "code")
    units = {u["unit_id"]: u for u in load_units(project)}
    ex, bs = CFG["models"]["executor"], CFG["execution"]["batch_size"]
    jobs = []
    for s in suites:
        cases = [c for c in s["test_cases"] if isinstance(c, dict)]
        for i in range(0, len(cases), bs):
            jobs.append((s, cases[i:i + bs]))

    def one(job):
        s, batch = job
        unit = units[s["unit_id"]]
        queries = [" ".join([c.get("title", ""), " ".join(c.get("steps", [])), " ".join(c.get("expected", []))]) for c in batch]
        p = prompt("audit", REQS=fmt_reqs(unit["reqs"]), CASES=json.dumps(batch, indent=1), MAP=index.map_text(queries=queries),
                   CODE=index.search_many(queries, CFG["execution"].get("audit_code_chars", 14000)))
        try:
            verdicts = llm.extract_json(llm.call(ex, p, stage="S6_audit", think=CFG["models"].get("executor_think")))
        except llm.LLMError as e:
            verdicts = None
        by_id = {v.get("id"): v for v in verdicts if isinstance(v, dict)} if isinstance(verdicts, list) else {}
        out = []
        for k, c in enumerate(batch):
            v = by_id.get(c.get("id")) or (verdicts[k] if isinstance(verdicts, list) and k < len(verdicts) and isinstance(verdicts[k], dict) else {})
            verdict = v.get("verdict") if v.get("verdict") in ("satisfied", "violated", "not_implemented", "unclear") else "audit_failed"
            out.append({"suite": f"{s['unit_id']}/{s['representation']}", "case_id": c.get("id"), "req_ids": c.get("req_ids", []),
                        "kind": c.get("kind"), "gate3_pass": s["gate3_pass"], "fsa_score": (s.get("fsa") or {}).get("fsa_score"),
                        "verdict": verdict, "evidence": v.get("evidence"), "reason": v.get("reason")})
        return out

    with ThreadPoolExecutor(CFG["pipeline"].get("workers", 1)) as pool:
        cases = [c for batch in pool.map(one, jobs) for c in batch]

    cnt = Counter(c["verdict"] for c in cases)
    req_best = defaultdict(set)
    for c in cases:
        for r in c["req_ids"]:
            req_best[r].add(c["verdict"])
    all_reqs = {r for u in units.values() for r in u["req_ids"]}
    tested = set(req_best)
    reached = {r for r, v in req_best.items() if v & {"satisfied", "violated"}}
    summary = {
        "generator": gen, "mode": "audit", "frozen_before_code": frozen["frozen_at"], "n_cases": len(cases),
        **{f"n_{k}": cnt.get(k, 0) for k in ("satisfied", "violated", "not_implemented", "unclear", "audit_failed")},
        "satisfied_rate": round(cnt["satisfied"] / max(1, len(cases)), 3),
        "violated_rate": round(cnt["violated"] / max(1, len(cases)), 3),
        "srs_reqs_total": len(all_reqs), "srs_reqs_with_tests": len(tested & all_reqs),
        "srs_reqs_reached_by_code": len(reached & all_reqs),
        "srs_coverage_by_tests": round(len(tested & all_reqs) / max(1, len(all_reqs)), 3),
        "srs_reached_by_code_rate": round(len(reached & all_reqs) / max(1, len(all_reqs)), 3),
        "reqs_with_violation": sorted(r for r, v in req_best.items() if "violated" in v),
    }
    write_json(gen_dir / "S6_audit.json", {"summary": summary, "cases": cases})
    print(f"  S6-audit [{gen}] " + json.dumps({k: summary[k] for k in ("n_cases", "n_satisfied", "n_violated", "n_not_implemented", "srs_coverage_by_tests", "srs_reached_by_code_rate")}))
    return summary
