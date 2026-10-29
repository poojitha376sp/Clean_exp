"""
S6 -- run the generated tests against the real implementation.

For every final suite of a generator (Gate 2 passed; Gate 3 pass/fail kept as
a flag so we can correlate gate scores with execution outcomes):

  1. copy inputs/<p>/code -> a throwaway workspace (the original is never touched)
  2. the fixed executor model turns each batch of canonical test cases into a
     runnable test file (one test function per case id; non-automatable cases
     become skips with a reason)
  3. files that fail to import/collect get ONE fix round (that is a test bug,
     not a code finding)
  4. run the test command with JUnit XML (+ coverage for Python)
  5. every failing test is triaged by the executor model:
     code_mismatch | test_bug | spec_ambiguous

Outputs runs/<p>/<gen>/S6_execution.json and the workspace with the tests.

inputs/<p>/project.yaml (all optional):
  language: python | javascript | java | ...
  framework: pytest | jest | junit5 | ...
  setup: "pip install -r requirements.txt"      # run once in the workspace
  test_cmd: "..."          # must write JUnit XML to {junit}; {tests} = generated tests dir
  src_globs: ["src/**/*.py"]
"""

import hashlib
import json
import os
import time
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from . import llm, suite
from .represent import fmt_reqs
from .util import CFG, inputs_dir, prompt, run_dir, slug, write_json
from .extract import load_units

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist", "target", ".idea", ".vscode"}
CODE_EXT = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rb", ".php", ".kt"}

LANG_DEFAULTS = {
    "python": {"framework": "pytest", "ext": ".py", "fence": "python",
               "name_rule": "test_<id with non-alphanumerics replaced by _>",
               "skip_rule": "call pytest.skip(\"...\") as its first line",
               "test_cmd": "{py} -m coverage run --branch --source=. -m pytest {tests} -q -p no:cacheprovider --junitxml={junit}"},
    "javascript": {"framework": "jest", "ext": ".test.js", "fence": "javascript",
                   "name_rule": "test('<id> ...', ...)", "skip_rule": "test.skip",
                   "test_cmd": "npx jest {tests} --ci --reporters=default --reporters=jest-junit"},
    "java": {"framework": "junit5", "ext": "Test.java", "fence": "java",
             "name_rule": "void test_<id with non-alphanumerics replaced by _>()",
             "skip_rule": "Assumptions.abort(\"...\")", "test_cmd": "mvn -q test"},
}


def _project_conf(project):
    code = inputs_dir(project) / "code"
    conf_path = inputs_dir(project) / "project.yaml"
    conf = yaml.safe_load(conf_path.read_text()) if conf_path.exists() else {}
    if "language" not in conf:
        counts = {}
        for p in code.rglob("*"):
            if p.is_file() and not (set(p.parts) & SKIP_DIRS):
                counts[p.suffix] = counts.get(p.suffix, 0) + 1
        conf["language"] = "python" if counts.get(".py", 0) >= max(counts.get(".js", 0), counts.get(".java", 0)) else \
            ("javascript" if counts.get(".js", 0) >= counts.get(".java", 0) else "java")
    d = LANG_DEFAULTS.get(conf["language"], LANG_DEFAULTS["python"])
    return {**d, **conf}


def _source_files(root):
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in CODE_EXT
                  and not (set(p.relative_to(root).parts) & SKIP_DIRS)
                  and not re.search(r"(^|/)(tests?|__tests__)/|test_|_test\.|\.test\.|Test\.java$", str(p.relative_to(root))))


def _signatures(text):
    keep = [l for l in text.splitlines() if re.match(r"\s*(def |class |async def |export |function |public |private |protected |static )", l)]
    return "\n".join(keep)


def code_context(root, budget):
    files = _source_files(root)
    tree = "\n".join(str(p.relative_to(root)) for p in files[:400])
    parts, used = [], 0
    for p in files:                                   # full text while it fits, else signatures
        txt = p.read_text(errors="ignore")
        block = f"--- {p.relative_to(root)} ---\n{txt}\n"
        if used + len(block) > budget:
            block = f"--- {p.relative_to(root)} (signatures only) ---\n{_signatures(txt)}\n"
        if used + len(block) > budget:
            continue
        parts.append(block)
        used += len(block)
    return tree, "".join(parts)


def _run(cmd, cwd, timeout):
    env = {**os.environ, "PYTHONPATH": str(cwd)}        # tests import the project from its root
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, (r.stdout + r.stderr)[-6000:]
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT after {timeout}s"


def _prepare_workspace(project, gen_dir, conf, arm):
    ws = gen_dir / f"S6_workspace_{arm}"
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(inputs_dir(project) / "code", ws, ignore=shutil.ignore_patterns(*SKIP_DIRS))
    (ws / "tests_generated").mkdir()
    py = sys.executable
    if conf["language"] == "python":
        env_dir = run_dir(project) / "S6_pyenv"          # one env per project, shared by generators
        if not env_dir.exists():
            subprocess.run([sys.executable, "-m", "venv", str(env_dir)], check=True)
            subprocess.run([str(env_dir / "bin/pip"), "install", "-q", "pytest", "coverage"], check=True)
            if (ws / "requirements.txt").exists():
                subprocess.run([str(env_dir / "bin/pip"), "install", "-q", "-r", "requirements.txt"], cwd=ws)
        py = str(env_dir / "bin/python")
    if conf.get("setup"):
        code, out = _run(conf["setup"].format(py=py), ws, 900)
        print(f"    setup exit={code}")
    return ws, py


def _parse_junit(path):
    res = {}
    if not path.exists():
        return res
    for tc in ET.parse(path).getroot().iter("testcase"):
        name = tc.get("name", "")
        status, msg = "passed", ""
        for tag in ("failure", "error", "skipped"):
            el = tc.find(tag)
            if el is not None:
                status = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                msg = ((el.get("message") or "") + "\n" + (el.text or ""))[-3000:]
                break
        res[name] = {"status": status, "message": msg, "file": tc.get("classname", "")}
    return res


def _alnum(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _match(case_key, results):
    """Map a case to its test result. Compare with every non-alphanumeric
    stripped: models write 'U03_3.3__Gherkin__TC-001' as
    'test_U03_3_3___Gherkin___TC_001', so underscore counts differ."""
    k = _alnum(case_key)
    for name, r in results.items():
        if _alnum(name).endswith(k) or k in _alnum(name):
            return r
    return None


def freeze(suites, path):
    """Fingerprint every test case BEFORE the code is opened. The report
    re-checks these hashes, which shows that test generation (S0-S5) used the
    SRS only and nothing changed after the implementation was seen."""
    manifest = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "suites": {f"{s['unit_id']}/{s['representation']}":
                           hashlib.sha256(json.dumps(s["test_cases"], sort_keys=True).encode()).hexdigest()
                           for s in suites}}
    write_json(path, manifest)
    return manifest


def run(project, gen, arm="gated"):
    """Execute every final suite that has test cases; gate pass/fail is kept
    as a flag so execution outcomes can be compared against gate verdicts."""
    gen_dir = run_dir(project) / slug(gen)
    suites = [s for s in suite.load_all(project, gen) if s.get("test_cases")]
    if not suites:
        print(f"  S6 [{gen}/{arm}] no suites with test cases; skipping")
        return None
    frozen = freeze(suites, gen_dir / f"S6_frozen_{arm}.json")          # before any code access
    conf = _project_conf(project)
    ws, py = _prepare_workspace(project, gen_dir, conf, arm)
    tree, source = code_context(ws, CFG["execution"]["max_source_chars"])
    units = {u["unit_id"]: u for u in load_units(project)}
    ex = CFG["models"]["executor"]
    bs = CFG["execution"]["batch_size"]

    cases = []                         # flat list with a globally unique key per case
    files = []
    for s in suites:
        for i in range(0, len(s["test_cases"]), bs):
            batch = s["test_cases"][i:i + bs]
            tagged = []
            for tc in batch:
                # a valid identifier in every language, so it can sit inside a test function name
                key = re.sub(r"\W", "_", f"{s['unit_id']}__{slug(s['representation'])[:12]}__{tc.get('id')}")
                tagged.append({**tc, "id": key})
                cases.append({"key": key, "suite": f"{s['unit_id']}/{s['representation']}", "case": tc,
                              "gate3_pass": s["gate3_pass"], "fsa_score": (s.get("fsa") or {}).get("fsa_score")})
            stem = re.sub(r"\W", "_", f"{s['unit_id']}_{s['representation'][:20]}_{i // bs}")   # valid module/class name
            fname = ws / "tests_generated" / (f"test_{stem}{conf['ext']}" if conf["ext"].startswith(".") else f"{stem}_{conf['ext']}")
            files.append((fname, tagged, units[s["unit_id"]]))

    for fname, tagged, unit in files:
        print(f"  S6 [{gen}/{arm}] writing {fname.name}")
        for fix_round in range(2):
            fb = ""
            if fix_round == 1:
                fb = f"\nTHE PREVIOUS VERSION OF THIS FILE FAILED TO LOAD/COLLECT:\n{collect_err}\nFix it (imports, syntax, API names) without changing what is asserted.\n"
            from .audit import CodeIndex
            if "_index" not in locals():
                _index = CodeIndex(ws)
            queries = [" ".join([c.get("title", ""), " ".join(c.get("steps", [])), " ".join(c.get("expected", []))]) for c in tagged]
            source = _index.search_many(queries, CFG["execution"]["max_source_chars"], per_query=2)
            tree = _index.map_text(queries=queries)
            p = prompt("to_executable", FRAMEWORK=conf["framework"], LANGUAGE=conf["language"], TREE=tree, SOURCE=source,
                       REQS=fmt_reqs(unit["reqs"]), CASES=json.dumps(tagged, indent=1), NAME_RULE=conf["name_rule"],
                       SKIP_RULE=conf["skip_rule"], FEEDBACK=fb, FENCE=conf["fence"])
            try:
                raw = llm.call(ex, p, stage="S6_to_exec", think=CFG["models"].get("executor_think"))
            except llm.LLMError as e:
                print(f"    executor failed: {e}")
                break
            code = llm.extract_block(raw, conf["fence"]) or llm.extract_block(raw, "") or raw
            fname.write_text(code)
            if conf["language"] != "python":
                break
            rc, out = _run(f"{py} -m pytest {fname.relative_to(ws)} --collect-only -q -p no:cacheprovider", ws, 120)
            if rc in (0, 5):
                break
            collect_err = out[-2500:]

    junit = gen_dir / f"S6_junit_{arm}.xml"
    junit.unlink(missing_ok=True)                 # never read a previous run's results
    cmd = conf["test_cmd"].format(py=py, tests="tests_generated", junit=junit)
    rc, out = _run(cmd, ws, CFG["execution"]["test_timeout_s"])
    results = _parse_junit(junit if junit.exists() else ws / "junit.xml")
    coverage = None
    if conf["language"] == "python":
        cj = gen_dir / f"S6_coverage_{arm}.json"
        _run(f"{py} -m coverage json -o {cj}", ws, 120)
        if cj.exists():
            t = json.loads(cj.read_text())["totals"]
            coverage = {"line_pct": round(t.get("percent_covered", 0), 2),
                        "branches": t.get("num_branches"), "covered_branches": t.get("covered_branches")}

    src_all = "\n".join(p.read_text(errors="ignore") for p in _source_files(ws))[:12000]
    n_triaged = 0
    # a file that failed to import shows up as one error entry for the whole file
    file_errors = {n: r for n, r in results.items() if r["status"] == "error" and not n.startswith("test_")}
    for c in cases:
        r = _match(c["key"], results)
        if r is None:
            f = next((f for f, t, _ in files if any(x["id"] == c["key"] for x in t)), None)
            r = next((fe for n, fe in file_errors.items() if f is not None and f.stem in n + fe.get("file", "")), None)
            if r is not None:
                r = {**r, "message": "COLLECTION ERROR (whole file): " + r["message"]}
        c["status"] = r["status"] if r else "missing"
        c["message"] = (r or {}).get("message", "")[:1500]
        if c["status"] == "skipped":
            c["skip_kind"] = "not_implemented" if "NOT_IMPLEMENTED" in c["message"] else "not_automatable"
        if c["status"] in ("failed", "error") and n_triaged < 60:
            n_triaged += 1
            unit = units[c["suite"].split("/")[0]]
            test_code = next((f.read_text() for f, t, _ in files if any(x["id"] == c["key"] for x in t)), "")
            m = re.search(rf"def test_\w*{re.escape(re.sub(r'[^A-Za-z0-9]', '_', c['key']))}[\s\S]*?(?=\ndef |\Z)", test_code)
            try:
                v = llm.extract_json(llm.call(ex, prompt("triage", REQS=fmt_reqs(unit["reqs"]), CASE=json.dumps(c["case"]),
                                                          TEST_CODE=(m.group(0) if m else test_code)[:4000],
                                                          FAILURE=c["message"], CODE=src_all), stage="S6_triage", think=CFG["models"].get("executor_think")))
            except llm.LLMError as e:
                v = {"verdict": "triage_failed", "explanation": str(e)}
            c["triage"] = v if isinstance(v, dict) else {"verdict": "unparseable"}

    def count(st):
        return sum(1 for c in cases if c["status"] == st)

    executed = count("passed") + count("failed")
    summary = {
        "generator": gen, "arm": arm, "frozen_before_code": frozen["frozen_at"], "language": conf["language"], "exit_code": rc, "run_output_tail": out[-3000:],
        "n_cases": len(cases), "passed": count("passed"), "failed": count("failed"), "error": count("error"),
        "skipped": count("skipped"), "missing": count("missing"),
        "not_implemented": sum(1 for c in cases if c.get("skip_kind") == "not_implemented"),
        "executable_rate": round((executed + count("error")) / max(1, len(cases)), 3),
        "pass_rate_of_executed": round(count("passed") / max(1, executed), 3),
        "code_mismatches": sum(1 for c in cases if (c.get("triage") or {}).get("verdict") == "code_mismatch"),
        "test_bugs": sum(1 for c in cases if (c.get("triage") or {}).get("verdict") == "test_bug"),
        "coverage": coverage,
    }
    write_json(gen_dir / f"S6_execution_{arm}.json", {"summary": summary, "cases": cases})
    print(f"  S6 [{gen}/{arm}] {json.dumps({k: summary[k] for k in ('n_cases', 'passed', 'failed', 'error', 'skipped', 'code_mismatches', 'coverage')})}")
    return summary
