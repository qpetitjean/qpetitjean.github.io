"""One-time migration from the sibling Distill sources; never run during rendering."""
from pathlib import Path
import html
import json
import re
import shutil
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent

def frontmatter(**fields):
    return '---\n' + '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}' for key,value in fields.items()) + '\n---\n\n'

def local_links(text):
    text = re.sub(r'https://github.com/qpetitjean/qpetitjean_distill/(?:raw|blob)/main/', '/', text)
    text = text.replace('https://qpetitjean.github.io/qpetitjean_distill/', '/')
    text = text.replace('/qpetitjean_distill/', '/')
    text = re.sub(r'(/publications\.html)#section(?:-\d+)?', r'\1', text)
    for original,new in image_map.items():
        text = text.replace('/images/' + original, '/assets/' + new)
        text = text.replace("'images/" + original, "'/assets/" + new)
        text = text.replace('"images/' + original, '"/assets/' + new)
    return text

def strip_inline(text):
    def icon_link(match):
        code = match.group(1)
        label = re.search(r'text\s*=\s*[\'"]([^\'"]+)', code)
        url = re.search(r'url\s*=\s*[\'"]([^\'"]+)', code)
        return f'<a href="{html.escape(url.group(1), quote=True)}">{html.escape(label.group(1))}</a>' if label and url else ''
    text = re.sub(r'`r\s+(icon_link\([^`]+)\s*`', icon_link, text)
    text = re.sub(r'`r\s+[^`]+`', '', text)
    return text

def clean_layout(text):
    text = re.sub(r'<(?:table|tr|td)\b[^>]*>|</(?:table|tr|td)>', '', text, flags=re.I)
    text = re.sub(r'<nav>.*?</nav>', '', text, flags=re.S)
    text = re.sub(r'<html[^>]*>', '', text)
    text = re.sub(r'\s+style=("[^"]*"|\x27[^\x27]*\x27)', '', text)
    text = re.sub(r'\s+id="container"', '', text)
    text = re.sub(r'<i\b[^>]*>\s*</i>', '', text)
    text = text.replace('&ensp;', ' ').replace('&nbsp;', ' ')
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text

image_map = {
    'Home_QP.png':'portrait.webp', 'BiologicalLevelOrga.png':'biological-levels.webp',
    'LogoYEG_Final.png':'yeg-logo.webp', 'Poster_YEG_SEFA2024.png':'yeg-poster.webp',
    'Petitjeanetal-MOVER-POSTER.png':'mover-poster.webp', 'PhDApproaches.png':'phd-approaches.webp',
    'PhDVensDiag.png':'phd-overview.webp', 'BidimeProjLogo.png':'bidime-logo.webp'
}
for original,target in image_map.items():
    img = ImageOps.exif_transpose(Image.open(OLD / 'images' / original))
    img.thumbnail((1600,1800) if 'poster' in target or 'phd' in target else (1000,1100))
    img.save(ROOT / 'assets' / target, 'WEBP', quality=87, method=6)
favicon = Image.open(OLD / 'images/FavIcon.png'); favicon.thumbnail((96,96)); favicon.save(ROOT / 'assets/favicon.png')
for directory in ('Posters', 'PubList'):
    (ROOT / directory).mkdir(exist_ok=True)
    for path in (OLD / directory).glob('*.pdf'):
        shutil.copy2(path, ROOT / directory / path.name)

dates = {'09-22-2022-Welcome':'2022-09-22', '01-17-2023-Dirty-Waterways-May-Alter-Fish-Behavior':'2023-01-17', '2023-07-12-mover-package':'2023-07-12', '2024-03-20-EcotoxBehavior':'2024-03-20', '2024-08-27-yeg':'2024-08-27', '2025-10-24-data-editor-guidelines':'2025-10-24'}
manifest = []
for source in sorted((OLD / '_posts').glob('*/*.Rmd')):
    original = source.read_text(encoding='utf-8-sig')
    _, head, body = original.split('---', 2)
    title = re.search(r'^title:\s*"(.+)"', head, re.M).group(1)
    description = re.search(r'^description:\s*"(.+)"', head, re.M).group(1)
    categories_part = head.split('categories:',1)[1].split('author:',1)[0]
    categories = [line.strip()[2:].strip() for line in categories_part.splitlines() if line.strip().startswith('- ')]
    affiliation = re.search(r'^\s+affiliation:\s*(.+)', head, re.M)
    author = {'name':'Quentin Petitjean', 'url':'https://qpetitjean.github.io/'}
    if affiliation: author['affiliation'] = affiliation.group(1).strip()
    def chunk(match):
        code = match.group(0)
        if 'MoveRPoster' in code:
            return '<img src="/assets/mover-poster.webp" alt="MoveR poster describing the animal movement analysis workflow" loading="lazy">'
        if 'tweet_screenshot' in code:
            return 'Read the accompanying thread on Twitter.'
        return ''
    body = re.sub(r'```\{r[^\n]*\n.*?```', chunk, body, flags=re.S)
    body = strip_inline(body)
    body = re.sub(r'<a[^>]*>\s*<div class="avoid-clicks">.*?</div>\s*</a>', '', body, flags=re.S)
    body = re.sub(r'<iframe.*?</iframe>', '', body, flags=re.S)
    body = re.sub(r'## Last updated on.*', '', body, flags=re.S)
    body = clean_layout(local_links(body))
    # External decorative logos are omitted; preserve local scientific figures and posters.
    body = re.sub(r'<img\b(?=[^>]*src="https?://)[^>]*>', '', body)
    body = re.sub(r'<a\b[^>]*>\s*(?:<div[^>]*>\s*</div>\s*)?</a>', '', body)
    body = re.sub(r'^# ', '## ', body, flags=re.M)
    folder = ROOT / 'posts' / source.parent.name; folder.mkdir(parents=True, exist_ok=True)
    metadata = frontmatter(title=title, description=description, date=dates[source.parent.name], categories=categories, author=[author])
    (folder / 'index.qmd').write_text(metadata + '::: {.legacy-content}\n\n' + body.strip() + '\n\n:::\n', encoding='utf-8')
    manifest.append({'old':'posts/' + source.parent.name + '/index.html', 'new':'posts/' + source.parent.name + '/index.html', 'source':str(source.relative_to(OLD))})

communications = (OLD / 'communications.Rmd').read_text(encoding='utf-8-sig').split('---',2)[2]
communications = re.sub(r'```\{r[^\n]*\n.*?```', '', communications, flags=re.S)
communications = clean_layout(local_links(strip_inline(communications)))
communications = re.sub(r'(?<=href=")(?=Posters/)', '/', communications)
communications = communications.replace('<span>&#42;</sup>', '<span>&#42;</span>')
communications = communications.replace('# ORAL COMMUNICATIONS', '## Talks').replace('# POSTER PRESENTATIONS', '## Posters')
communications = re.sub(r'^## (20\d\d)', r'### \1', communications, flags=re.M)
(ROOT / 'communications.qmd').write_text(frontmatter(title='Talks & posters', description='Conference presentations, invited talks and resources.', toc=True) + '::: {.legacy-content}\n\n' + communications + '\n:::\n', encoding='utf-8')

cv = (OLD / 'cv.Rmd').read_text(encoding='utf-8-sig').split('---',2)[2]
def cv_chunk(match):
    code = match.group(0)
    figures = {'PhDApproaches':('phd-approaches.webp','Research questions and experimental approaches during my PhD'), 'PhDVensDiag':('phd-overview.webp','Research themes explored during my PhD')}
    for marker,(image,alt) in figures.items():
        if marker in code: return f'<img src="/assets/{image}" alt="{alt}" loading="lazy">'
    if 'GraphAbsChemos' in code: return '<p><a href="https://doi.org/10.1016/j.chemosphere.2021.130337">View the study and graphical abstract.</a></p>'
    if 'CagesTypes' in code: return '<p><a href="https://doi.org/10.1007/s11356-016-8261-1">View the study and experimental cage designs.</a></p>'
    return ''
cv = re.sub(r'```\{r[^\n]*\n.*?```', cv_chunk, cv, flags=re.S)
cv = clean_layout(local_links(strip_inline(cv)))
cv = re.sub(r'<!--.*?-->', '', cv, flags=re.S)
cv = re.sub(r'\(see fig\.\s*\\@ref\([^)]+\)(?: below)?\)', '', cv)
cv = re.sub(r'\s*\(over 2 hours, see fig\.\s*\\@ref\([^)]+\)\)', ' (over two hours)', cv)
cv = re.sub(r'<img\b(?=[^>]*src="https?://)[^>]*>', '', cv)
cv = re.sub(r'### PEER REVIEWS\s*', '', cv)
cv = re.sub(r'### REVIEW SUMMARY\s*', '', cv)
cv = re.sub(r'^# (.+)$', lambda m:'## ' + m.group(1).capitalize(), cv, flags=re.M)
cv = cv.replace('### EDITORIAL DUTIES', '### Editorial duties').replace('### CONGRESS ORGANIZATION', '### Conference organisation').replace('### MEMBERSHIP', '### Membership')
(ROOT / 'cv.qmd').write_text(frontmatter(title='Curriculum vitae', description='Research experience, teaching, service and community involvement.', toc=True) + '<button type="button" class="print-button" data-print>Print / save as PDF</button>\n\n::: {.legacy-content}\n\n' + cv.strip() + '\n\n:::\n', encoding='utf-8')

for page in ('index','news','publications','communications','cv'):
    manifest.append({'old':page + '.html', 'new':page + '.html'})
(ROOT / 'migration').mkdir(exist_ok=True)
(ROOT / 'migration/url-map.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print('Migrated six posts, CV, talks, poster/publication PDFs and optimised local images.')

