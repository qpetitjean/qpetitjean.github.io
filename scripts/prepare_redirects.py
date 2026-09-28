"""Prepare old-site redirect files for review; never modify or publish the old site."""
import html
import json
from pathlib import Path
from site_data import ROOT

destination = ROOT / 'migration/legacy-redirects'
for entry in json.loads((ROOT/'migration/url-map.json').read_text(encoding='utf-8')):
    target = 'https://qpetitjean.github.io/' + ('' if entry['new']=='index.html' else entry['new'])
    path = destination/entry['old']; path.parent.mkdir(parents=True,exist_ok=True)
    url=html.escape(target,quote=True)
    path.write_text(f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Page moved — Quentin Petitjean</title><link rel="canonical" href="{url}"><meta http-equiv="refresh" content="0; url={url}"></head><body><p>This page has moved. <a href="{url}">Continue to the new website</a>.</p></body></html>\n',encoding='utf-8')
print(f'Prepared redirects in {destination}. Existing PDF paths must remain available in the old site.')

