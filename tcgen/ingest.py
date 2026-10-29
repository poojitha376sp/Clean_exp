"""S0 -- turn whatever SRS files the project has (PDF / DOCX / MD / TXT) into one clean text file."""

import re

from .util import inputs_dir, run_dir, write_json


def _pdf(path):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def _docx(path):
    import docx
    d = docx.Document(str(path))
    out = [p.text for p in d.paragraphs]
    for t in d.tables:                       # tables often hold requirement lists
        for row in t.rows:
            out.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(out)


def _text(path):
    return path.read_text(errors="ignore")


READERS = {".pdf": _pdf, ".docx": _docx, ".md": _text, ".txt": _text, ".rst": _text}


def _yaml_items(files):
    """Requirement-per-file YAML (e.g. doorstop: REQ001.yml with level/header/
    text/links/active/normative). Returns one text block ordered by level, or
    None if these aren't requirement items."""
    import yaml
    items = []
    for f in files:
        try:
            d = yaml.safe_load(f.read_text(errors="ignore"))
        except yaml.YAMLError:
            continue
        if not isinstance(d, dict) or "text" not in d:
            continue
        if d.get("active") is False:
            continue
        items.append((str(d.get("level", "")), f.stem, d))
    if not items:
        return None

    def lvl(x):
        return [int(n) if n.isdigit() else 0 for n in re.split(r"[.]", x[0])]

    out, structured = [], []
    for level, uid, d in sorted(items, key=lvl):
        head = f"{level} {d.get('header') or ''}".strip()
        body = (d.get("text") or "").strip()
        links = [list(l)[0] if isinstance(l, dict) else str(l) for l in (d.get("links") or [])]
        if d.get("normative") is False:
            out.append(f"{head}\n(informative) {body}")
        else:
            out.append(f"{head}\n{uid}: {body}" + (f"\n(links to: {', '.join(links)})" if links else ""))
            structured.append({"id": uid, "section": level, "section_title": (d.get("header") or "").strip(),
                               "text": " ".join(body.split()), "kind": "functional", "testable": True, "refs": links})
    return "\n\n".join(out), structured


_RST_UNDERLINE = re.compile(r"^([=\-^~\"'`#*+])\1{2,}\s*$")


def rst_items(text):
    """Sphinx-needs style '.. item:: ID' blocks (e.g. RespiraWorks' SRS.rst):
    id, :fulfills:/:links: options, the paragraph after them, and the heading
    they sit under. Returns [] if the document has no such items."""
    lines = text.splitlines()
    items, heading, i = [], "", 0
    while i < len(lines):
        ln = lines[i]
        if i + 1 < len(lines) and ln.strip() and _RST_UNDERLINE.match(lines[i + 1]) and not ln.startswith(".."):
            heading = ln.strip()
            i += 2
            continue
        m = re.match(r"^\.\.\s+item::\s+(\S+)", ln)
        if not m:
            i += 1
            continue
        uid, refs, body = m.group(1), [], []
        i += 1
        while i < len(lines) and re.match(r"^\s+:\w+:", lines[i]):
            refs += re.findall(r"[A-Z][A-Z0-9-]*-\d+", lines[i])
            i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(".."):
            if i + 1 < len(lines) and _RST_UNDERLINE.match(lines[i + 1]):
                break
            body.append(lines[i].strip())
            i += 1
        if body:
            items.append({"id": uid, "section": heading, "section_title": heading, "text": " ".join(body),
                          "kind": "functional", "testable": True, "refs": refs})
    return items


def clean(text):
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*Page \d+( of \d+)?\s*\n", "\n", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def run(project):
    srs_dir = inputs_dir(project) / "srs"
    files = sorted(p for p in srs_dir.rglob("*") if p.suffix.lower() in READERS)
    ymls = sorted(p for p in srs_dir.rglob("*") if p.suffix.lower() in (".yml", ".yaml"))
    parts, structured = [], []
    yaml_text, yaml_struct = _yaml_items(ymls) if ymls else (None, [])
    structured += yaml_struct
    if yaml_text:
        print(f"  S0 {len(ymls)} YAML requirement items: {len(yaml_text)} chars")
        parts.append(f"===== DOCUMENT: requirement items ({srs_dir.name}) =====\n{clean(yaml_text)}")
    if not files and not parts:
        raise SystemExit(f"No SRS files (.pdf/.docx/.md/.txt/.rst/.yml) in {srs_dir}")
    for f in files:
        raw = READERS[f.suffix.lower()](f)
        if f.suffix.lower() == ".rst":
            structured += rst_items(raw)
        text = clean(raw)
        print(f"  S0 {f.name}: {len(text)} chars")
        parts.append(f"===== DOCUMENT: {f.name} =====\n{text}")
    out = run_dir(project) / "S0_srs.txt"
    out.write_text("\n\n".join(parts))
    items_path = run_dir(project) / "S0_items.json"
    if structured:
        # The SRS already lists requirements with ids: S1 uses these verbatim, no LLM.
        write_json(items_path, structured)
        print(f"  S0 {len(structured)} structured requirement items found (used directly by S1)")
    elif items_path.exists():
        items_path.unlink()
    return out
