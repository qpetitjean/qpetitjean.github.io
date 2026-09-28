"""Reuse the Distill CV's review-counting rules, publishing only aggregates.

Read the same local workbook during local renders. On GitHub (where the workbook
is absent), use the committed aggregate cache. No manuscript-level data is saved.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime
from pathlib import Path
import os

from site_data import ROOT, escaped as e, read_json, safe_url, write_json

WORKBOOK = Path("C:/Users/qpetitjean/Desktop/WORK/Reviews/Recap_reviews-QP.xlsx")
CACHE = ROOT / "data/reviews-summary.json"


def summarise(article_rows, data_rows, journal_urls, updated):
    """One row with a submission date = one review, as in the original R code."""
    journals = {"article": Counter(), "data": Counter()}
    years = {"article": Counter(), "data": Counter()}
    for kind, rows in (("article", article_rows), ("data", data_rows)):
        for row in rows:
            submitted = row.get("Date review Submitted")
            if submitted is None or submitted == "":
                continue
            if not isinstance(submitted, (datetime, date)):
                raise ValueError("A submitted-review date is not an Excel date; correct the workbook before rendering.")
            journal = str(row.get("Journal name") or "").strip()
            if not journal:
                raise ValueError("A submitted review is missing its journal name.")
            journals[kind][journal] += 1
            years[kind][submitted.year] += 1
    names = journals["article"].keys() | journals["data"].keys()
    annual = years["article"].keys() | years["data"].keys()

    def counts(key, source):
        article = source["article"][key]
        data = source["data"][key]
        return {"article": article, "data": data, "total": article + data}

    by_journal = [dict(journal=name, url=safe_url(journal_urls.get(name, ""), allow_local=False),
                       **counts(name, journals)) for name in names]
    by_journal.sort(key=lambda row: (-row["total"], row["journal"].casefold()))
    return {
        "updated": str(updated),
        "journals": by_journal,
        "years": [dict(year=year, **counts(year, years)) for year in sorted(annual)],
        "totals": {key: sum(row[key] for row in by_journal) for key in ("article", "data", "total")},
    }


def read_workbook(path):
    try:
        from openpyxl import load_workbook
    except ImportError as error:
        raise RuntimeError("Reading the local review workbook needs openpyxl in QUARTO_PYTHON. GitHub uses the saved summary without this dependency.") from error
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        def rows(sheet, required):
            values = iter(workbook[sheet].values)
            header = next(values)
            if not set(required).issubset(header):
                raise ValueError(f"Required review columns are missing from {sheet}.")
            # Select only the columns needed for counts/links, never manuscript details.
            indices = {key: header.index(key) for key in required}
            for values in values:
                yield {key: values[index] for key, index in indices.items()}
        urls = {str(row["JournalName"]).strip(): str(row["URL"] or "").strip()
                for row in rows("JournalsURL", ["JournalName", "URL"]) if row["JournalName"]}
        # Use the public publisher link rather than an institutional login proxy.
        urls = {name: url.replace("https://link-springer-com.inrae.idm.oclc.org/", "https://link.springer.com/")
                for name, url in urls.items()}
        columns = ["Date review Submitted", "Journal name"]
        return summarise(rows("ArticleRevSummary", columns), rows("DataRevSummary", columns),
                         urls, date.today())
    finally:
        workbook.close()


def refresh(workbook=None, cache=CACHE):
    explicit = workbook or os.environ.get("REVIEWS_WORKBOOK")
    path = Path(explicit) if explicit else WORKBOOK
    if path.is_file():
        summary = read_workbook(path)
        write_json(cache, summary)
        print(f'Review summary refreshed: {summary["totals"]["total"]} submitted reviews.')
        return summary
    if explicit:
        raise FileNotFoundError("The configured review workbook was not found; check REVIEWS_WORKBOOK.")
    saved = read_json(cache)
    if saved is None:
        raise FileNotFoundError("No review summary is available. Render once with the local workbook and commit data/reviews-summary.json.")
    print(f'Using saved review summary from {saved["updated"]}.')
    return saved


def journal_html(summary):
    total = summary["totals"]
    parts = [f'<p><strong>{total["total"]} submitted reviews</strong>: {total["article"]} article reviews and {total["data"]} data &amp; code reviews.</p>',
             '<ul class="review-journals">']
    for row in summary["journals"]:
        name = e(row["journal"])
        link = f'<a href="{e(safe_url(row["url"], allow_local=False))}">{name}</a>' if row["url"] else name
        parts.append(f'<li>{link} <span class="review-count">(n = {row["total"]})</span></li>')
    parts.append(f'</ul><p class="review-note">Completed reviews only; includes article and data &amp; code reviews. Updated {e(summary["updated"])}.</p>')
    return "\n".join(parts)


def yearly_html(summary):
    rows = summary["years"]
    if not rows:
        return '<p>No completed reviews recorded yet.</p>'
    maximum = max(5, ((max(row["total"] for row in rows) + 4) // 5) * 5)
    first, last = rows[0]["year"], rows[-1]["year"]
    # Fill any intervening zero-review years; absence is not a connecting data point.
    by_year = {row["year"]: row for row in rows}
    years = list(range(first, last + 1))
    x = lambda year: 64 + (year - first) * 640 / max(1, last - first)
    y = lambda count: 286 - count * 226 / maximum
    parts = ['<figure class="review-figure"><svg class="review-chart" viewBox="0 0 760 340" role="img" aria-labelledby="review-chart-title review-chart-desc">',
             '<title id="review-chart-title">Submitted reviews by year</title>',
             '<desc id="review-chart-desc">Article reviews, data and code reviews, and their combined total. Exact counts are available in the table below.</desc>']
    for tick in range(0, maximum + 1, max(1, maximum // 5)):
        parts.append(f'<line class="review-grid" x1="64" x2="704" y1="{y(tick)}" y2="{y(tick)}"/><text x="50" y="{y(tick)+5}" text-anchor="end">{tick}</text>')
    for year in years:
        parts.append(f'<text x="{x(year)}" y="314" text-anchor="middle">{year}</text>')
    series = [("article", "Article reviews", "0"), ("data", "Data & code reviews", "5 4"), ("total", "Total", "2 4")]
    for index, (key, label, dash) in enumerate(series):
        legend_x = (64, 278, 576)[index]
        parts.append(f'<g class="review-series-{key}"><line x1="{legend_x}" x2="{legend_x+27}" y1="25" y2="25" stroke-width="3" stroke-dasharray="{dash}"/><text x="{legend_x+36}" y="30">{e(label)}</text>')
        points = ' '.join(f'{x(year)},{y(by_year.get(year, {}).get(key, 0))}' for year in years)
        parts.append(f'<polyline points="{points}" fill="none" stroke-width="3" stroke-dasharray="{dash}"/>')
        for year in years:
            count = by_year.get(year, {}).get(key, 0)
            parts.append(f'<circle cx="{x(year)}" cy="{y(count)}" r="4.5"><title>{year}: {count} {e(label.lower())}</title></circle>')
        parts.append('</g>')
    parts.append('</svg><figcaption>Article and data &amp; code reviews submitted each year. The current year is shown to date.</figcaption></figure>')
    parts.append('<details class="review-table-details"><summary>View yearly counts</summary><div class="review-table-wrap"><table class="review-table"><caption>Submitted reviews by year</caption><thead><tr><th scope="col">Year</th><th scope="col">Article reviews</th><th scope="col">Data &amp; code reviews</th><th scope="col">Total</th></tr></thead><tbody>')
    for year in years:
        row = by_year.get(year, {})
        parts.append(f'<tr><th scope="row">{year}</th><td>{row.get("article", 0)}</td><td>{row.get("data", 0)}</td><td>{row.get("total", 0)}</td></tr>')
    parts.append('</tbody></table></div></details>')
    return "\n".join(parts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, help="Override the local review workbook path")
    args = parser.parse_args()
    refresh(args.workbook)
