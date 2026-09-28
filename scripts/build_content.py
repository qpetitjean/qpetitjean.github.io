"""Offline pre-render: format APA citations, validate data, generate accessible HTML."""
from __future__ import annotations
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from sync_reviews import refresh as refresh_reviews, journal_html, yearly_html
from site_data import ROOT, escaped as e, normalise_doi, read_csv, read_json, safe_url, validate_jobs, job_status, write_json

def quarto_command():
    candidates = [shutil.which("quarto")]
    if os.environ.get("QUARTO_BIN_PATH"):
        candidates.extend(str(Path(os.environ["QUARTO_BIN_PATH"]) / name) for name in ("quarto.exe", "quarto"))
    if os.name == "nt":
        candidates.append("C:/Program Files/RStudio/resources/app/bin/quarto/bin/quarto.exe")
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return [str(candidate)]
    raise RuntimeError("Quarto must be installed and available on PATH.")

class CitationParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.entries = {}; self.current = None; self.depth = 0; self.parts = []
    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "div" and "csl-entry" in attr.get("class", "").split():
            self.current = attr["id"].removeprefix("ref-"); self.depth = 1; self.parts = []
        elif self.current:
            if tag == "div": self.depth += 1
            self.parts.append(self.get_starttag_text())
    def handle_endtag(self, tag):
        if self.current:
            if tag == "div":
                self.depth -= 1
                if self.depth == 0:
                    self.entries[self.current] = "".join(self.parts).strip(); self.current = None; return
            self.parts.append(f"</{tag}>")
    def handle_data(self, text):
        if self.current: self.parts.append(text)
    def handle_entityref(self, name):
        if self.current: self.parts.append(f"&{name};")
    def handle_charref(self, name):
        if self.current: self.parts.append(f"&#{name};")

def format_citations(records):
    with tempfile.TemporaryDirectory(prefix="quarto-citations-") as temp:
        bib = Path(temp) / "records.json"
        bib.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(quarto_command() + ["pandoc", "--from=markdown", "--to=html", "--citeproc", "--bibliography=" + str(bib), "--csl=" + str(ROOT / "styles/apa.csl")], input="---\nnocite: '@*'\n---\n\n::: {#refs}\n:::\n", text=True, encoding="utf-8", capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
    parser = CitationParser(); parser.feed(result.stdout)
    missing = {record["id"] for record in records} - set(parser.entries)
    if missing: raise ValueError(f"Citation formatter omitted: {missing}")
    return parser.entries

def publications():
    cache = read_json(ROOT / "data/publications-cache.json", {"entries":{}})
    overrides = read_json(ROOT / "data/publication-overrides.json", {})
    keyword_records = read_json(ROOT / "data/publication-keywords.json", {}).get("records", {})
    rows = read_csv(ROOT / "data/publications.csv")
    curated = {normalise_doi(row.get("DOI")):row for row in rows if row.get("DOI")}
    records = []
    for doi, entry in cache["entries"].items():
        if doi in overrides.get("exclude", []): continue
        csl = dict(entry["csl"])
        for field in ("ISSN", "ISBN"):
            if isinstance(csl.get(field), list): csl[field] = "; ".join(csl[field])
        override = overrides.get("records", {}).get(doi, {})
        csl.update(override.get("csl", {}))
        csl["id"] = "pub-" + hashlib.sha256(doi.encode()).hexdigest()[:12]
        row = curated.get(doi, {})
        kind = override.get("kind", entry.get("kind", "Article"))
        if csl.get("type") == "thesis": kind = "Thesis"
        records.append({"doi":doi, "csl":csl, "extra":row, "kind":kind, "keywords":keyword_records.get(doi, {}).get("keywords", []), "published_dois":override.get("published_dois", entry.get("published_dois", []))})
    for manual in read_json(ROOT / "data/manual-publications.json", []):
        records.append({"doi":"", "csl":manual, "extra":{}, "kind":"Thesis" if manual.get("type") == "thesis" else "Other", "keywords":keyword_records.get(manual["id"], {}).get("keywords", []), "published_dois":[]})
    if not records: raise ValueError("No bibliography records; run scripts/sync_publications.py first.")
    # Group linked preprints under their published version, while retaining the preprint link.
    by_doi = {record["doi"]:record for record in records if record["doi"]}
    grouped = set()
    for record in records:
        if record["kind"] == "Preprint":
            for related in record["published_dois"]:
                if related in by_doi and by_doi[related]["kind"] != "Preprint":
                    by_doi[related].setdefault("related_preprints", []).append(record["doi"])
                    for key in ("Data", "Code", "StatReport", "Preprint"):
                        if record["extra"].get(key) and not by_doi[related]["extra"].get(key):
                            by_doi[related]["extra"][key] = record["extra"][key]
                    grouped.add(record["doi"])
    records = [record for record in records if not record["doi"] or record["doi"] not in grouped]
    def year(record):
        parts = (record["csl"].get("issued") or {}).get("date-parts") or [[0]]
        return int(parts[0][0] or 0)
    records.sort(key=lambda record:(-year(record), record["csl"]["title"].lower()))
    formatted = format_citations([record["csl"] for record in records])
    # Preserve each paper's wording; merge case-only variants in the filter menu.
    keywords = {}
    for record in records:
        for keyword in record["keywords"]:
            keywords.setdefault(keyword.lower(), keyword)
    parts = ['<div data-filter-list data-singular="publication" data-plural="publications">', '<div class="filter-bar"><label>Search publications<input data-filter="search" type="search" placeholder="Title, author or keyword"></label>']
    for key,label,values in [("kind", "Type", sorted({r["kind"] for r in records})), ("keyword", "Keyword", sorted(keywords.values(), key=str.lower)), ("year", "Year", sorted({str(year(r)) for r in records}, reverse=True))]:
        parts.append(f'<label>{label}<select data-filter="{key}"><option value="all">All {label.lower()}s</option>' + ''.join(f'<option value="{e(v)}">{e(v)}</option>' for v in values) + '</select></label>')
    parts.extend(['</div>', f'<p class="result-count" data-result-count aria-live="polite">{len(records)} publications</p>', '<p data-no-results hidden>No publications match these filters.</p>'])
    for record in records:
        csl = record["csl"]; extra = record["extra"]; doi = record["doi"]; identifier = csl["id"]
        citation = formatted[identifier]
        citation = re.sub(r"(Petitjean,\s*Q\.)", r"<strong>\1</strong>", citation)
        target = safe_url("https://doi.org/" + doi if doi else csl.get("URL", ""))
        title = e(re.sub("<[^>]+>", "", csl["title"]))
        links = []
        if doi: links.append(("DOI", target))
        filename = extra.get("FileName", "")
        if filename:
            if filename.startswith(("https://", "http://")):
                links.append(("Full text", filename))
            else:
                pdf = "PubList/" + filename + extra.get("Extension", ".pdf")
                if (ROOT / pdf).is_file(): links.append(("PDF", pdf))
        for key,label in [("Data", "Data"), ("Code", "Code"), ("StatReport", "Report"), ("Preprint", "Preprint")]:
            if extra.get(key): links.append((label, extra[key]))
        if not any(label == "Preprint" for label,_ in links):
            links.extend(("Preprint", "https://doi.org/" + p) for p in record.get("related_preprints", []))
        links = list(dict.fromkeys(links))
        link_html = ''.join(f'<a href="{e(safe_url(url))}">{label}</a>' for label,url in links)
        keyword_html = ''.join(f'<span class="tag">{e(keyword)}</span>' for keyword in record["keywords"])
        keyword_values = e('|'.join(record["keywords"]))
        metrics = ''
        if doi:
            metrics = (f'<div class="pub-metrics" role="group" aria-label="Article metrics">'
                       f'<div class="altmetric-embed" data-badge-type="1" data-badge-popover="bottom" data-doi="{e(doi)}"></div>'
                       f'<span class="__dimensions_badge_embed__" data-doi="{e(doi)}" data-style="large_rectangle" data-legend="hover-bottom"></span></div>')
        parts.append(f'<article class="publication" id="{identifier}" data-filter-item data-kind="{e(record["kind"])}" data-keyword="{keyword_values}" data-year="{year(record)}"><div class="pub-year">{year(record) or "n.d."}</div><div><h2><a href="{e(target)}">{title}</a></h2><div class="citation" id="citation-{identifier}">{citation}</div><div class="pub-tags"><span class="tag pub-kind">{e(record["kind"])}</span>{keyword_html}</div><div class="pub-links">{link_html}<button type="button" class="copy-citation" data-citation="citation-{identifier}">Copy citation</button></div>{metrics}</div></article>')
    stamp = (cache.get("last_success") or "")[:10]
    parts.append(f'<p class="result-count">References last refreshed {e(stamp)}. <a href="https://scholar.google.com/citations?user=GMudi1sAAAAJ&amp;hl=en">Google Scholar</a> · <a href="https://orcid.org/0000-0003-2708-7831">ORCID</a></p><span id="copy-status" class="visually-hidden" role="status"></span></div>')
    # Load each provider once, after all DOI badge containers; only on this page.
    parts.append('<script async src="https://embed.altmetric.com/assets/embed.js"></script><script async src="https://badge.dimensions.ai/static/ai/badge.js" charset="utf-8"></script>')
    # Every manually curated DOI must be accounted for, including a linked preprint.
    missing = set(curated) - set(cache["entries"]) - set(overrides.get("exclude", []))
    if missing: raise ValueError(f"Curated references missing metadata: {sorted(missing)}")
    return '\n'.join(parts)

def opportunities():
    rows = read_csv(ROOT / "data/opportunities.csv"); validate_jobs(rows)
    today = date.today()
    rows = [row for row in rows if job_status(row, today) != "draft"]
    rows.sort(key=lambda row:(job_status(row, today) != "open", row.get("deadline") or "9999-12-31", row["title"]))
    if not rows:
        return '<div class="empty-state"><p class="eyebrow">Research opportunities</p><h2>No announcements at the moment.</h2><p>New positions and shared opportunities will appear here with their application deadlines and full descriptions.</p></div>', ''
    parts = ['<div data-filter-list data-singular="opportunity" data-plural="opportunities"><div class="filter-bar"><label>Search opportunities<input type="search" data-filter="search" placeholder="Topic, institution or location"></label>']
    for key,label,values in [("kind", "Position type", ["Postdoc", "PhD", "Master's", "Internship", "Other"]), ("source", "Source", ["In my group", "Shared opportunity"]), ("status", "Status", ["open", "closed"])]:
        options = '<option value="all">All</option>'
        for value in values:
            selected = ' selected' if key == "status" and value == "open" else ''
            options += f'<option value="{e(value)}"{selected}>{e(value.title() if key == "status" else value)}</option>'
        parts.append(f'<label>{label}<select data-filter="{key}">{options}</select></label>')
    parts.append('</div><p class="result-count" data-result-count aria-live="polite"></p><p data-no-results hidden>No opportunities match these filters.</p>')
    for row in rows:
        status = job_status(row, today)
        deadline = row.get("deadline") or "Open until filled"
        if status == "closed" and not row.get("deadline"): deadline = "Closed"
        links = ''.join(f'<a href="{e(safe_url(row[key]))}">{label}</a>' for key,label in [("webpage", "Full announcement ↗"), ("pdf", "Job description (PDF)")] if row.get(key))
        parts.append(f'<article class="job-entry" id="{e(row["id"])}" data-filter-item data-kind="{e(row["type"])}" data-source="{e(row["source"])}" data-status="{status}"><span class="tag">{e(row["type"])}</span> <span class="tag">{e(row["source"])}</span><h2>{e(row["title"])}</h2><div class="job-meta"><span>{e(row["institution"])}</span><span>{e(row.get("location"))}</span><span>{"Deadline: " if row.get("deadline") else ""}{e(deadline)}</span><span>{status.title()}</span></div><p>{e(row["summary"])}</p><div class="pub-links">{links}</div></article>')
    parts.append('</div>')
    opened = [row for row in rows if job_status(row, today) == "open"]
    home = ''
    if opened:
        home = f'<section class="home-section"><div class="section-heading"><h2>Open opportunities</h2><a class="text-link" href="opportunities.html">View all ↗</a></div>' + ''.join(f'<div class="news-row"><span class="tag">{e(r["type"])}</span><a href="opportunities.html#{e(r["id"])}">{e(r["title"])}</a><span class="news-category">{e(r["institution"])}</span></div>' for r in opened[:3]) + '</section>'
    return '\n'.join(parts), home

def home_news():
    # JSON scalar values are valid YAML, so the migrated headers can be read without a YAML dependency.
    records = []
    for path in (ROOT / "posts").glob("*/index.qmd"):
        head = path.read_text(encoding="utf-8").split("---", 2)[1]
        values = {}
        for field in ("title", "date", "description"):
            match = re.search(rf"^{field}: (.+)$", head, re.M)
            if match:
                try: values[field] = json.loads(match.group(1))
                except json.JSONDecodeError: values[field] = match.group(1).strip('"')
        values["url"] = path.relative_to(ROOT).as_posix().replace(".qmd", ".html")
        records.append(values)
    records.sort(key=lambda item:item.get("date", ""), reverse=True)
    parts = ['<section class="home-section" aria-labelledby="news-title"><div class="section-heading"><h2 id="news-title">Recent news</h2><a class="text-link" href="news.html">All news ↗</a></div>']
    for record in records[:3]:
        stamp = date.fromisoformat(record["date"])
        parts.append(f'<div class="news-row"><time datetime="{stamp}">{stamp.strftime("%d %b %Y")}</time><a href="{e(record["url"])}">{e(record["title"])}</a><span aria-hidden="true">↗</span></div>')
    parts.append('</section>')
    return '\n'.join(parts)

def main():
    destination = ROOT / "_generated"; destination.mkdir(exist_ok=True)
    jobs, home_jobs = opportunities()
    reviews = refresh_reviews()
    for filename,content in {"publications.html":publications(), "opportunities.html":jobs, "home-opportunities.html":home_jobs, "home-news.html":home_news(), "reviews-journals.html":journal_html(reviews), "reviews-yearly.html":yearly_html(reviews)}.items():
        # Raw block prevents Markdown from reinterpreting citation punctuation or HTML tables.
        (destination / filename).write_text('```{=html}\n' + content + '\n```\n', encoding="utf-8")
    print("Prepared bibliography, opportunities, recent news and CV review counts.")

if __name__ == "__main__":
    main()
