"""Validate local links, canonical URLs, and the complete migrated page inventory."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import json
import sys
from site_data import ROOT

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=set(); self.canonicals=[]; self.images=[]
    def handle_starttag(self, tag, attributes):
        attr = dict(attributes)
        if attr.get('id'): self.ids.add(attr['id'])
        if tag == 'link' and attr.get('rel') == 'canonical': self.canonicals.append(attr.get('href',''))
        if tag == 'img': self.images.append(attr)
        for key in ('href','src'):
            if attr.get(key): self.links.append((tag,attr[key]))

def main():
    site = ROOT/'_site'; problems=[]; pages={}
    for path in site.rglob('*.html'):
        parser=Page(); parser.feed(path.read_text(encoding='utf-8')); pages[path.resolve()]=parser
    for path,parser in pages.items():
        relative = path.relative_to(site)
        if len(parser.canonicals) != 1: problems.append(f'{relative}: expected one canonical URL, got {parser.canonicals}')
        elif parser.canonicals[0] != 'https://qpetitjean.github.io/' + (relative.as_posix() if relative.name != 'index.html' else relative.parent.as_posix().replace('.', '') + ('/' if relative.parent.as_posix() != '.' else '')):
            # Quarto can represent index pages using the explicit index.html form.
            explicit = 'https://qpetitjean.github.io/' + relative.as_posix()
            if parser.canonicals[0] != explicit: problems.append(f'{relative}: unexpected canonical {parser.canonicals[0]}')
        for tag,value in parser.links:
            url=urlsplit(value)
            if url.scheme or url.netloc: continue
            if not url.path: target=path
            else: target=(site/url.path.lstrip('/') if url.path.startswith('/') else path.parent/unquote(url.path)).resolve()
            if target.is_dir(): target=target/'index.html'
            if not target.exists(): problems.append(f'{relative}: missing {value}')
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                problems.append(f'{relative}: missing fragment {value}')
        for img in parser.images:
            if 'alt' not in img: problems.append(f'{relative}: image has no alt text: {img.get("src")}')
        text=path.read_text(encoding='utf-8')
        if '`r ' in text or '\\@ref(' in text: problems.append(f'{relative}: unconverted R Markdown syntax')
    expected = [item['new'] for item in json.loads((ROOT/'migration/url-map.json').read_text())]
    for filename in expected:
        if not (site/filename).is_file(): problems.append(f'Missing migrated page: {filename}')
    if any(site.rglob('Recap_reviews-QP.xlsx')):
        problems.append('The private review workbook must not be included in the public website.')
    homepage=site/'index.html'
    if homepage.stat().st_size>500_000: problems.append('Homepage HTML exceeds 500 KB')
    if problems:
        print('\n'.join(problems)); raise SystemExit(1)
    print(f'Checked {len(pages)} HTML pages: local links, fragments, canonical URLs, image labels and legacy URLs passed.')
    print(f'Homepage HTML: {homepage.stat().st_size:,} bytes. Portrait: {(site/"assets/IMG_0143.JPG").stat().st_size:,} bytes.')

if __name__ == '__main__': main()

