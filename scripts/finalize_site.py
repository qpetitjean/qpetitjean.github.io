"""Add an explicit, unique canonical URL to every rendered page."""
from pathlib import Path
import re
from site_data import ROOT

site = ROOT/'_site'
for page in site.rglob('*.html'):
    relative = page.relative_to(site).as_posix()
    if relative.endswith('index.html'): relative = relative[:-10]
    canonical = 'https://qpetitjean.github.io/' + relative
    content = page.read_text(encoding='utf-8')
    content = re.sub(r'<link\b[^>]*rel=[\'"]canonical[\'"][^>]*>\s*', '', content)
    content = content.replace('<head>', '<head>\n<link rel="canonical" href="' + canonical + '">', 1)
    page.write_text(content, encoding='utf-8')
print('Added page-specific canonical URLs.')
