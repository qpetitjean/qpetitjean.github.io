# Quentin Petitjean — Quarto website

This repository contains the quarto version of my original distill website (migration has been made with help of Codex using GPT-6 Astra model). 
`_site` contains the generated pages, not the editable source.

## Preview and render

Requirements: Quarto 1.8.25 or later and Python 3.11 or later. 

From this folder:

```sh
quarto preview
```

For a complete build and checks:

```sh
python -m unittest discover -s tests -v
quarto render
python scripts/check_site.py
```

If Python is not on the PATH, set `QUARTO_PYTHON` to its executable before running Quarto. 
`preview.ps1` locates the bundled Python and the Quarto installation included with RStudio.

## Update publications

`data/publications.csv` keeps the original semicolon-separated column names: `Title;FileName;Extension;Data;Code;StatReport;Preprint;DOI`. For a new DOI-based record, only the DOI is required; the other fields are optional. `FileName` is either a full-text URL or the name of a file in `PubList` without the extension. Local PDFs stay in `PubList/`.

```sh
python scripts/sync_publications.py
quarto render
```

The refresh discovers public journal articles/preprints/books/theses/conference papers from ORCID, retrieves DOI metadata, and follows explicit preprint-to-publication relationships. 
Known preprints appear under their published version, retaining data, code and preprint links. Failed requests retain the saved record. 
The site builds offline from `data/publications-cache.json`; the visible refresh date is the last successful metadata retrieval, not the latest site build.

The weekly workflow proposes a pull request with refreshed metadata. This avoids publishing incorrect metadata without review. GitHub must allow Actions to create pull requests. 
Merge a satisfactory refresh to publish it. 
Daily site builds keep opportunity deadlines current even when no content changes. GitHub may disable scheduled workflows in inactive public repositories; 
check the Actions tab if the site has not been updated for a while.

To update ORCID with Google Scholar: open your Scholar profile, select your publications, export them as **BibTeX**, then run:

```sh
python scripts/sync_publications.py --scholar-bib path/to/scholar.bib
```

DOI records are imported automatically. 
Non-DOI records go to `data/import-candidates.json` for review; 
add accepted CSL-JSON entries to `data/manual-publications.json`. 
This route does not scrape Scholar or require a paid service.

Corrections belong in `data/publication-overrides.json`. 
They take precedence over external metadata. Use `records[doi].csl` for citation fields, `kind` for work type, `published_dois` for an explicit relationship, or `exclude` to suppress a DOI. 
DOI keys are lowercase without `https://doi.org/`. Review `data/sync-report.json` after a refresh.

Publication tags and the Keyword filter use **the keywords reported by the authors**, saved in `data/publication-keywords.json`. 
Each record includes the exact keyword list, its source and the verification date. 
Original spelling and capitalisation are retained; case-only variants share one filter option. 
To add keywords, use the lowercase DOI as the record key (or the CSL `id` for a manual reference), and copy the keyword list from the article or its author-keyword metadata. 
Never substitute journal subject categories or infer keywords from titles. If no list can be verified, the entry shows only its publication type. 
Published papers use their own keywords, not those of an earlier preprint. 
These verified lists survive automatic bibliography refreshes; newly discovered works remain without keyword tags until their list is checked.

References use Pandoc citeproc and the APA CSL file in `styles/apa.csl`. 
The style is from the [Citation Style Language project](https://github.com/citation-style-language/styles/blob/master/apa.csl); its authors and licence are recorded in that file. 
Bibliography grouping and bold highlighting of your name are website presentation choices.

Publication entries with a DOI also display live [Altmetric](https://docs.altmetric.com/badges/getting-started/) and [Dimensions](https://badge.dimensions.ai/) badges. Each provider is loaded once on the publications page. Their coverage determines which works display metrics; the bibliography itself still works offline.

## Add an opportunity

Add one row to `data/opportunities.csv` (UTF-8, semicolon-separated). Quote any field containing a semicolon. Fields:

| Field | Meaning |
|---|---|
| id | Unique URL anchor, such as `bee-phd-2027` |
| title | Position title |
| type | `Postdoc`, `PhD`, `Master's`, `Internship`, or `Other` |
| institution | Recruiting organisation |
| location | City/country, or remote |
| deadline | `YYYY-MM-DD`, or blank for open until filled |
| source | `In my group` or `Shared opportunity` |
| status | `open`, `closed`, or `draft` |
| summary | Short plain-text description |
| webpage | Full announcement URL, optional if a PDF is provided |
| pdf | PDF URL or `downloads/opportunities/filename.pdf` |

A deadline remains open throughout that calendar date. 
Closed jobs remain accessible through the status filter. 
Drafts are excluded. Never use a fabricated vacancy to fill an empty page: the site intentionally has a clear empty state when there are no announcements.

## CV review counts — edit only your local workbook

Keep editing `C:/Users/qpetitjean/Desktop/WORK/Reviews/Recap_reviews-QP.xlsx`, in its existing location. Save the workbook, then render the website as usual. The pre-render script reads it automatically and refreshes the CV's journal totals and yearly chart. There is no summary file to edit by hand and no separate refresh step.

`scripts/sync_reviews.py` adapts the counting rules from the original Distill `cv.Rmd`: one submitted-review row counts as one review, using `ArticleRevSummary` and `DataRevSummary`; journal links come from `JournalsURL`. Rows without a submission date are excluded. Both article and data/code reviews contribute to each journal's total. Editorial positions remain editable in `cv.qmd`.

Local workbook reading requires `openpyxl`, which is already present in the Python used by `preview.ps1`. On another computer, install it in the Python used by Quarto. To change the workbook location, set `REVIEWS_WORKBOOK` to its full path. A missing explicitly configured file or invalid workbook stops the build rather than silently publishing stale counts.

Only journal names/URLs and aggregated counts by journal and year are saved in `data/reviews-summary.json`. That file is generated automatically and travels with the normal website commit/push. GitHub cannot read your local drive: its builds use the last generated summary without needing Excel, R, or `openpyxl`. To publish new counts, save the workbook, render locally, and push the usual website changes. A GitHub-only rebuild cannot see new local workbook edits.

The workbook itself stays outside the repository, is ignored by Git if accidentally copied in, and must never be included in the published `_site` folder. No manuscript titles, author names, evaluations or editorial decisions are exported.

## Repository visibility and GitHub Pages

This website uses a **public** `qpetitjean.github.io` repository and GitHub Pages, compatible with GitHub Free. The source files and generated aggregate review counts are public. The confidential review workbook stays in its existing local folder, outside this repository.

The public website address is `https://qpetitjean.github.io/`. GitHub Actions renders the site and publishes only `_site`. See the [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

## Add news and edit pages

Create `posts/YYYY-MM-DD-short-title/index.qmd` with `title`, `description`, ISO `date` and `categories` in its header. 
The homepage and news index update during rendering. 
The six migrated posts preserve their original URL directory names and historical affiliations. 
Standalone pages can be edited directly in RStudio.

`index.qmd` controls the homepage. `styles/theme.scss`, `styles/dark.scss` and `styles/site.css` control the design. Images use local files, including `assets/IMG_0143.JPG` for the portrait and `assets/OsmiaMating.jpg` for the favicon and system fonts avoid external font downloads. The CV has a print/save-to-PDF button and a print stylesheet.
