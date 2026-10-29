import json
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent          # Clean_exp/
load_dotenv(ROOT.parent / ".env")                       # Honours-Testing/.env
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
PROMPTS = ROOT / "prompts"


def prompt(name: str, **fields) -> str:
    """Load prompts/<name>.txt and fill {{FIELD}} placeholders."""
    text = (PROMPTS / f"{name}.txt").read_text()
    for k, v in fields.items():
        text = text.replace("{{" + k + "}}", v if isinstance(v, str) else json.dumps(v, indent=2))
    return text


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def read_json(p):
    return json.loads(Path(p).read_text())


def write_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def append_jsonl(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(obj) + "\n")


def inputs_dir(project: str) -> Path:
    return (ROOT / CFG["paths"]["inputs_dir"] / project).resolve()


def run_dir(project: str) -> Path:
    d = ROOT / CFG["paths"]["runs_dir"] / project
    d.mkdir(parents=True, exist_ok=True)
    return d
