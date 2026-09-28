"""Shared, dependency-free data validation for the personal website."""
from __future__ import annotations
import csv
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]

def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)

def read_csv(path):
    text = Path(path).read_bytes()
    try:
        text = text.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = text.decode("cp1252")
    return list(csv.DictReader(text.splitlines(), delimiter=";"))

def normalise_doi(value):
    value = unquote(str(value or "").strip())
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.I)
    value = value.strip().lower()
    # bioRxiv/medRxiv append a version to article URLs, not to the registered DOI.
    value = re.sub(r"^(10\.1101/\d{4}\.\d{2}\.\d{2}\.\d+)v\d+$", r"\1", value)
    if value and not re.fullmatch(r"10\.\d{4,9}/\S+", value):
        raise ValueError(f"Invalid DOI: {value!r}")
    return value

def safe_url(value, allow_local=True):
    value = str(value or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme.lower() in {"https", "http"} and parts.netloc:
        return value
    if allow_local and not parts.scheme and not parts.netloc and not value.startswith(("//", "\\")) and ".." not in Path(parts.path).parts:
        return value
    raise ValueError(f"Unsupported link: {value!r}")

def escaped(value):
    return html.escape(str(value or ""), quote=True)

def job_status(row, today=None):
    """A deadline remains open for the entire stated calendar date."""
    today = today or date.today()
    status = (row.get("status") or "open").strip().lower()
    if status not in {"open", "closed", "draft"}:
        raise ValueError(f"Unknown opportunity status: {status}")
    if status in {"closed", "draft"}:
        return status
    deadline = (row.get("deadline") or "").strip()
    if deadline and date.fromisoformat(deadline) < today:
        return "closed"
    return "open"

def validate_jobs(rows):
    seen = set()
    for row in rows:
        for field in ("id", "title", "type", "institution", "source", "summary"):
            if not row.get(field, "").strip():
                raise ValueError(f"Opportunity is missing {field}: {row.get('id', '(no id)')}")
        if row["id"] in seen:
            raise ValueError(f"Duplicate opportunity ID: {row['id']}")
        seen.add(row["id"])
        if row["type"] not in {"Postdoc", "PhD", "Master's", "Internship", "Other"}:
            raise ValueError(f"Unknown opportunity type: {row['type']}")
        if row["source"] not in {"In my group", "Shared opportunity"}:
            raise ValueError(f"Unknown opportunity source: {row['source']}")
        if not row.get("webpage") and not row.get("pdf"):
            raise ValueError(f"Opportunity {row['id']} requires a webpage or PDF")
        safe_url(row.get("webpage"))
        safe_url(row.get("pdf"))
        if row.get("deadline"):
            date.fromisoformat(row["deadline"])
        job_status(row)
