"""Build the per-article args bundle the Workflow script consumes.

Usage: python pipeline/prepare.py <capture-dir> <run-dir> [--no-head-check]

Reads <capture-dir>/article.md and manifest.json (from article-to-google-doc), splits
structural units, lists every external link occurrence with its section, containing
unit, sentence, and a live HEAD signal, and writes <run-dir>/bundle.json holding the
identity, article text, units, link units and batches, the ten prompt templates, and
the ten output schemas. The Workflow script fills placeholders by string replacement.
"""
import json, re, sys, os, datetime, concurrent.futures, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from split_units import split

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
LINK = re.compile(r'\[((?:[^\[\]]|\[[^\]]*\])*)\]\((https?://[^)\s]+)(?:\s+"[^"]*")?\)')
BATCH = 25

def head(url):
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0 (article reviewer link check)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {'status': r.status, 'final_url': r.geturl(), 'redirected': r.geturl().rstrip('/') != url.rstrip('/'), 'error': None}
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'final_url': e.geturl(), 'redirected': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'status': None, 'final_url': None, 'redirected': False, 'error': type(e).__name__}

def coalesce(items, size):
    """One batch per leaf section, but adjacent small sections share a call and a
    section over `size` targets is split. Returns lists of ids."""
    groups, cur = [], []
    for it in items:
        if cur and cur[-1]['section'] != it['section']:
            groups.append(cur); cur = []
        cur.append(it)
    if cur: groups.append(cur)
    batches, cur = [], []
    for g in groups:
        while len(g) > size:
            if cur: batches.append(cur); cur = []
            batches.append(g[:size]); g = g[size:]
        if len(cur) + len(g) > size:
            batches.append(cur); cur = []
        cur.extend(g)
    if cur: batches.append(cur)
    return [[i['id'] for i in b] for b in batches]

def sentence_around(text, start, end):
    left = max(text.rfind('. ', 0, start), text.rfind('\n', 0, start), text.rfind('? ', 0, start), text.rfind('! ', 0, start))
    left = 0 if left < 0 else left + 2 if text[left] != '\n' else left + 1
    m = re.search(r'[.?!](?=\s|$)|\n', text[end:])
    right = end + (m.end() if m else len(text) - end)
    return text[left:right].strip()

def main(capture, run_dir, head_check=True):
    text = open(os.path.join(capture, 'article.md')).read()
    manifest = json.load(open(os.path.join(capture, 'manifest.json')))
    wp = manifest['wordpress']
    units = split(text)
    headings = [u for u in units if u['type'] == 'heading']
    def section_at(off):
        sec = 'Preamble'
        for h in headings:
            if h['start_offset'] <= off:
                sec = re.sub(r'<[^>]+>', '', h['text'].lstrip('# ')).strip()
            else:
                break
        return sec
    def unit_at(off):
        for u in units:
            if u['start_offset'] <= off < u['end_offset']:
                return u['id']
        return None
    links = []
    images = 0
    for m in LINK.finditer(text):
        anchor, url = m.group(1), m.group(2)
        if m.start() > 0 and text[m.start()-1] == '!':
            images += 1  # image embed, not a citation link
            continue
        links.append({'id': f'L{len(links)+1:03d}', 'anchor_text': anchor, 'url': url,
                      'start_offset': m.start(), 'end_offset': m.end(),
                      'section': section_at(m.start()), 'structural_unit_id': unit_at(m.start()),
                      'sentence': sentence_around(text, m.start(), m.end())})
    if head_check and links:
        urls = sorted({l['url'] for l in links})
        with concurrent.futures.ThreadPoolExecutor(16) as ex:
            sig = dict(zip(urls, ex.map(head, urls)))
        for l in links:
            l['signal'] = sig[l['url']]
    # batch links by section, splitting sections over BATCH targets
    batches = coalesce(links, BATCH)
    prompts = {f'{n:02d}': open(p).read() for n, p in
               ((int(f[:2]), os.path.join(PROJECT, 'prompts', f)) for f in sorted(os.listdir(os.path.join(PROJECT, 'prompts'))) if re.match(r'\d\d-.*\.md$', f))}
    schemas = {f[:2]: json.load(open(os.path.join(HERE, 'schemas', f))) for f in sorted(os.listdir(os.path.join(HERE, 'schemas'))) if f.endswith('.schema.json')}
    identity = {'title': wp['title'], 'url': manifest['canonical_url'], 'wordpress_id': wp['id'],
                'wordpress_modified': wp['modified'], 'wordpress_type': wp['rest_base'],
                'captured_markdown_sha256': manifest.get('outputs', {}).get('markdown_sha256') or __import__('hashlib').sha256(text.encode()).hexdigest(),
                'checked_at': datetime.date.today().isoformat(),
                'article_path': os.path.abspath(os.path.join(capture, 'article.md')),
                'run_dir': os.path.abspath(run_dir),
                'word_count': len(text.split())}
    os.makedirs(os.path.join(run_dir, 'stages'), exist_ok=True)
    bundle = {'identity': identity, 'article': text, 'units': units, 'links': links, 'link_batches': batches,
              'sections': [section_at(h['start_offset']) for h in headings], 'prompts': prompts, 'schemas': schemas, 'batch_size': BATCH}
    json.dump(bundle, open(os.path.join(run_dir, 'bundle.json'), 'w'), ensure_ascii=False)
    json.dump({'units': units}, open(os.path.join(run_dir, 'units.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump({'links': links, 'batches': batches}, open(os.path.join(run_dir, 'links.json'), 'w'), indent=1, ensure_ascii=False)
    from collections import Counter
    print(json.dumps({'units': len(units), 'unit_types': dict(Counter(u['type'] for u in units)), 'links': len(links), 'image_embeds_excluded': images,
                      'link_batches': [len(b) for b in batches], 'signals': dict(Counter((l.get('signal') or {}).get('error') or ('redirect' if (l.get('signal') or {}).get('redirected') else 'ok') for l in links)),
                      'bundle_bytes': os.path.getsize(os.path.join(run_dir, 'bundle.json'))}, indent=1))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], head_check='--no-head-check' not in sys.argv)
