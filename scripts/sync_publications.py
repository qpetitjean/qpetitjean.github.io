"""Refresh DOI metadata and discover public ORCID works; preserve saved successes.

No requests run during quarto render. Run this separately when updating records.
Google Scholar BibTeX exports can be merged with --scholar-bib FILE.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from site_data import ROOT, normalise_doi, read_csv, read_json, write_json

ORCID = "0000-0003-2708-7831"
ALLOWED_TYPES = {"journal-article", "preprint", "book-chapter", "book", "dissertation-thesis", "conference-paper", "other"}
CSL_TYPES = {"journal-article":"article-journal", "posted-content":"article", "book-chapter":"chapter", "dissertation":"thesis", "dissertation-thesis":"thesis", "preprint":"article"}
FIELDS = {"title", "author", "editor", "issued", "container-title", "volume", "issue", "page", "publisher", "publisher-place", "DOI", "URL", "type", "ISBN", "ISSN", "genre", "edition"}

def fetch_json(url, accept="application/json"):
    request = urllib.request.Request(url, headers={"Accept":accept, "User-Agent":"QuentinPetitjeanWebsite/1.0 (public bibliography)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def csl_record(data, doi):
    record = {key:value for key,value in data.items() if key in FIELDS}
    record["DOI"] = doi
    record["URL"] = "https://doi.org/" + doi
    record["type"] = CSL_TYPES.get(data.get("type"), data.get("type", "article-journal"))
    # Once assigned to a journal volume, prefer the issue's print date to an earlier online date.
    print_date = data.get("published-print", {}).get("date-parts", [[]])
    if data.get("volume") and print_date and print_date[0] and print_date[0][0]:
        record["issued"] = {"date-parts":print_date}
    for key in ("title", "container-title"):
        if isinstance(record.get(key), list):
            record[key] = ": ".join(record[key])
    if not record.get("title") or not record.get("author"):
        raise ValueError("Metadata has no title or authors; retained any previous record")
    # Keep only citation-relevant author fields, rather than affiliations and vendor extensions.
    record["author"] = [{k:v for k,v in author.items() if k in {"family", "given", "literal", "suffix", "non-dropping-particle", "dropping-particle"}} for author in record["author"]]
    return record

def discover_orcid():
    data = fetch_json(f"https://pub.orcid.org/v3.0/{ORCID}/works")
    found = {}
    for group in data.get("group", []):
        summaries = group.get("work-summary", [])
        summaries = sorted(summaries, key=lambda x:int(x.get("display-index", 0)), reverse=True)
        for work in summaries:
            if work.get("type") not in ALLOWED_TYPES:
                continue
            for identifier in work.get("external-ids", {}).get("external-id", []):
                if identifier.get("external-id-type") == "doi" and identifier.get("external-id-relationship") == "self":
                    doi = normalise_doi(identifier.get("external-id-value"))
                    found.setdefault(doi, {"source":"ORCID", "title":work.get("title", {}).get("title", {}).get("value", ""), "work_type":work.get("type", "")})
    return found

def sync(args):
    path = ROOT / "data/publications-cache.json"
    cache = read_json(path, {"schema_version":1, "entries":{}, "discovered":{}, "last_success":None})
    cache.setdefault("discovered", {})
    failures = []
    if not args.no_discovery:
        try:
            cache["discovered"].update(discover_orcid())
        except Exception as error:
            failures.append({"source":"ORCID", "error":str(error)})
    if args.scholar_bib:
        from build_content import quarto_command
        import subprocess
        result = subprocess.run(quarto_command() + ["pandoc", args.scholar_bib, "--from=bibtex", "--to=csljson"], capture_output=True, text=True, encoding="utf-8", check=True)
        for record in json.loads(result.stdout):
            doi = normalise_doi(record.get("DOI"))
            if doi:
                cache["discovered"].setdefault(doi, {"source":"Google Scholar export", "title":record.get("title", "")})
            else:
                # Keep complete non-DOI records as candidates for review, not silently discard them.
                candidates = read_json(ROOT / "data/import-candidates.json", [])
                if record not in candidates:
                    candidates.append(record)
                write_json(ROOT / "data/import-candidates.json", candidates)
    curated = {normalise_doi(row.get("DOI")) for row in read_csv(ROOT / "data/publications.csv") if row.get("DOI")}
    excluded = set(read_json(ROOT / "data/publication-overrides.json", {}).get("exclude", []))
    dois = (curated | set(cache["discovered"])) - excluded
    refreshed = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    queue = sorted(dois)
    visited = set()
    while queue:
        doi = queue.pop(0)
        if doi in visited:
            continue
        visited.add(doi)
        if args.only_missing and doi in cache["entries"]:
            for related in cache["entries"][doi].get("published_dois", []):
                if related not in visited and related not in excluded:
                    cache["discovered"].setdefault(related, {"source":"Published version linked by DOI metadata"})
                    queue.append(related)
            continue
        try:
            data = fetch_json("https://doi.org/" + doi, "application/vnd.citationstyles.csl+json")
            record = csl_record(data, doi)
            discovery = cache["discovered"].get(doi, {})
            is_preprint = data.get("type") == "posted-content" or discovery.get("work_type") == "preprint" or data.get("subtype") == "preprint"
            relations = data.get("relation", {})
            related = [normalise_doi(item["id"]) for item in relations.get("is-preprint-of", []) if item.get("id-type") == "doi"]
            cache["entries"][doi] = {"csl":record, "fetched_at":now, "source":data.get("source", "DOI resolver"), "kind":"Preprint" if is_preprint else "Article", "published_dois":related}
            for published in related:
                if published not in visited and published not in excluded:
                    cache["discovered"].setdefault(published, {"source":"Published version linked by DOI metadata"})
                    queue.append(published)
            refreshed += 1
            print(f"Retrieved {doi}", flush=True)
        except Exception as error:
            failures.append({"source":doi, "error":str(error), "cached":doi in cache["entries"]})
            print(f"Kept saved data for {doi}: {error}", flush=True)
        time.sleep(.3)
    if refreshed:
        cache["last_success"] = now
    cache["last_attempt"] = now
    write_json(path, cache)
    write_json(ROOT / "data/sync-report.json", {"attempted_at":now, "refreshed":refreshed, "cached_records":len(cache["entries"]), "failures":failures})
    print(f"Saved {len(cache['entries'])} records; {refreshed} refreshed; {len(failures)} lookup failures.")
    if not cache["entries"]:
        raise SystemExit("No saved bibliography is available. Resolve lookups before publishing.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-discovery", action="store_true", help="Only refresh known DOI records")
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--scholar-bib", help="BibTeX exported from your Google Scholar profile")
    sync(parser.parse_args())
