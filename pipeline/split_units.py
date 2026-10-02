"""Harness step: split an article's Markdown into structural units keyed by id and offset.

Units are paragraphs, list items, captions, tables, headings, and footnotes. Footnotes in
this corpus are the numbered items under the `## Notes and references` heading; an
indented continuation block belongs to the footnote before it. Headings are emitted so
offsets are complete but are not mapped by prompt 07.

Usage: python pipeline/split_units.py <article.md> <units.json>
"""
import json, re, sys
from collections import Counter

NOTES_HEADING = re.compile(r'^## (Notes and references|Notes|Footnotes|References)\s*$')

def classify(s, in_notes):
    if re.match(r'^#{1,6} ', s): return 'heading'
    if in_notes and re.match(r'^\d+\. ', s): return 'footnote'
    if re.match(r'^(\s*[-*+]|\s*\d+\.) ', s): return 'list'
    if s.startswith('![') or re.fullmatch(r'\*[^*]+\*', s): return 'caption'
    if s.startswith('|'): return 'table'
    return 'paragraph'

def split(text):
    units, pos, in_notes = [], 0, False
    for block in re.split(r'\n\s*\n', text):
        s = block.strip('\n')
        if not s.strip():
            continue
        start = text.index(s, pos); end = start + len(s); pos = end
        if NOTES_HEADING.match(s.strip()):
            in_notes = True
        if in_notes and s.startswith('    ') and units and units[-1]['type'] == 'footnote':
            units[-1]['end_offset'] = end
            units[-1]['text'] = text[units[-1]['start_offset']:end]
            continue
        units.append({'id': f'U{len(units)+1:03d}', 'type': classify(s, in_notes),
                      'start_offset': start, 'end_offset': end, 'text': s})
    for u in units:
        assert text[u['start_offset']:u['end_offset']] == u['text']
    return units

if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    text = open(src).read()
    units = split(text)
    json.dump({'source': src, 'units': units}, open(out, 'w'), indent=1, ensure_ascii=False)
    print(out, len(units), dict(Counter(u['type'] for u in units)))
