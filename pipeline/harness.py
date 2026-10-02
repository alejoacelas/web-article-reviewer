"""Deterministic harness steps between Workflow stages.

The Workflow script has no filesystem, so each stage agent reads its prompt template,
the article, its input file and its output schema from disk and saves its JSON under
<run-dir>/stages/. This module turns those saved outputs into the next stage's inputs:

  python3 pipeline/harness.py inputs <run-dir> <stage>   # write inputs/<stage>-*.json, print batches
  python3 pipeline/harness.py join   <run-dir> <stage>   # validate + locate + join, write joined/<stage>.json

`join` checks that every expected id has exactly one entry, that enumerated fields hold
allowed values, that required fields are present, locates every quoted passage in the
article (exact, then smart-quote-normalised) and records offsets and the containing
structural unit. Problems are recorded on the entry (`harness`), never dropped.
Stage numbers: 01 targets, 02 links, 03 facts, 04 discover, 05 draft, 06 polish,
07 map, 08 prune, 09 validate/merge, 10 grade.
"""
import json, os, re, sys, glob
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
NORM = str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '-', ' ': ' '})
BATCH = 25
MAP_BATCH = 40

def load(run, name):
    p = os.path.join(run, name)
    return json.load(open(p)) if os.path.exists(p) else None

def save(run, name, obj):
    p = os.path.join(run, name); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, 'w'), indent=1, ensure_ascii=False); return p

def article(run):
    return open(load(run, 'bundle.json')['identity']['article_path']).read()

def locate(text, ntext, passage, hint=None):
    """Return (start, end, method) or (None, None, reason). `hint` is a preferred offset."""
    if not passage: return None, None, 'empty'
    cands = [m.start() for m in re.finditer(re.escape(passage), text)]
    method = 'exact'
    if not cands:
        cands = [m.start() for m in re.finditer(re.escape(passage.translate(NORM)), ntext)]
        method = 'normalized'
    if not cands:
        p = re.sub(r'\s+', ' ', passage.translate(NORM)).strip()
        m = re.search(re.escape(p).replace(r'\ ', r'\s+'), ntext)
        if m: return m.start(), m.end(), 'whitespace'
        return None, None, 'unlocated'
    if len(cands) > 1:
        if hint is not None:
            s = min(cands, key=lambda c: abs(c - hint)); return s, s + len(passage), method + '-nearest-of-%d' % len(cands)
        return cands[0], cands[0] + len(passage), 'ambiguous-%d' % len(cands)
    return cands[0], cands[0] + len(passage), method

def unit_at(units, off):
    for u in units:
        if u['start_offset'] <= off < u['end_offset']: return u['id']
    return None

def stage_files(run, stage):
    return sorted(glob.glob(os.path.join(run, 'stages', f'{stage}-*.json')))

def check_schema(entry, schema_item):
    probs = []
    for f in schema_item.get('required', []):
        if f not in entry: probs.append(f'missing field {f}')
    for f, spec in schema_item.get('properties', {}).items():
        if f in entry and 'enum' in spec and entry[f] not in spec['enum']: probs.append(f'bad enum {f}={entry[f]!r}')
    return probs

def merge_stage_outputs(run, stage, key):
    out = []
    for f in stage_files(run, stage):
        d = json.load(open(f)); out.extend(d.get(key, []) if isinstance(d, dict) else [])
    return out

def coalesce(items, size, section_key='section'):
    groups, cur = [], []
    for it in items:
        if cur and cur[-1][section_key] != it[section_key]: groups.append(cur); cur = []
        cur.append(it)
    if cur: groups.append(cur)
    batches, cur = [], []
    for g in groups:
        while len(g) > size:
            if cur: batches.append(cur); cur = []
            batches.append(g[:size]); g = g[size:]
        if len(cur) + len(g) > size: batches.append(cur); cur = []
        cur.extend(g)
    if cur: batches.append(cur)
    return batches

# ---------------------------------------------------------------- inputs
def inputs(run, stage):
    b = load(run, 'bundle.json'); text = article(run); units = b['units']
    schema = b['schemas'][stage]
    batches = []
    if stage == '01':
        batches = [{'id': '01-all', 'path': None, 'count': 0}]
    elif stage == '02':
        for i, ids in enumerate(b['link_batches'], 1):
            idset = set(ids); items = [{k: l[k] for k in ('id', 'anchor_text', 'url', 'sentence', 'section', 'signal')} for l in b['links'] if l['id'] in idset]
            batches.append({'id': f'02-b{i:02d}', 'path': save(run, f'inputs/02-b{i:02d}.json', {'assigned_link_targets': items}), 'count': len(items), 'section': items[0]['section']})
    elif stage == '03':
        j = load(run, 'joined/01.json')['factual_targets']
        for i, grp in enumerate(coalesce(j, BATCH), 1):
            items = [{k: t[k] for k in ('id', 'passage', 'fact', 'role', 'section')} for t in grp]
            batches.append({'id': f'03-b{i:02d}', 'path': save(run, f'inputs/03-b{i:02d}.json', {'assigned_factual_targets': items}), 'count': len(items), 'section': items[0]['section']})
    elif stage == '04':
        batches = [{'id': '04-all', 'path': None, 'count': 0}]
    elif stage == '05':
        f = load(run, 'joined/04.json')['findings']
        batches = [{'id': '05-all', 'path': save(run, 'inputs/05-all.json', {'later_development_findings': f}), 'count': len(f)}]
    elif stage == '06':
        e = load(run, 'joined/05.json')['edits']
        batches = [{'id': '06-all', 'path': save(run, 'inputs/06-all.json', {'drafted_whole_article_edits': e}), 'count': len(e)}]
    elif stage == '07':
        mappable = [u for u in units if u['type'] != 'heading']
        index = [{'id': u['id'], 'type': u['type'], 'start_offset': u['start_offset'], 'preview': u['text'][:90]} for u in units]
        for i in range(0, len(mappable), MAP_BATCH):
            grp = mappable[i:i + MAP_BATCH]
            batches.append({'id': f'07-b{i // MAP_BATCH + 1:02d}', 'path': save(run, f'inputs/07-b{i // MAP_BATCH + 1:02d}.json', {'assigned_units': grp, 'all_units_index': index}), 'count': len(grp)})
    elif stage == '08':
        e = load(run, 'joined/06.json')['edits']; m = load(run, 'joined/07.json')['units']
        batches = [{'id': '08-all', 'path': save(run, 'inputs/08-all.json', {'polished_whole_article_edits': e}), 'count': len(e), 'map_path': save(run, 'inputs/purpose-map.json', {'units': m})}]
    elif stage == '09':
        targeted = [x for x in load(run, 'joined/02.json')['results'] + load(run, 'joined/03.json')['results'] if x['verdict'] in ('change', 'editorial_escalation')]
        whole = [x for x in (load(run, 'joined/08.json') or {'items': []})['items'] if x['verdict'] in ('keep', 'convert_to_escalation')]
        batches = [{'id': '09-all', 'path': save(run, 'inputs/09-all.json', {'targeted_corrections': targeted, 'retained_whole_article_items': whole}), 'count': len(targeted) + len(whole)}]
    elif stage == '10':
        j = load(run, 'joined/09.json')['items']
        retained = [x for x in j if x['verdict'] in ('accept', 'repaired') and x['merge'] in ('retained', 'conflict_recorded')]
        targets_checked = len(load(run, 'joined/02.json')['results']) + len(load(run, 'joined/03.json')['results'])
        batches = [{'id': '10-all', 'path': save(run, 'inputs/10-all.json', {'retained_items_after_merge': retained, 'run_metadata': {'targets_checked': targets_checked}}), 'count': len(retained), 'map_path': os.path.join(run, 'inputs/purpose-map.json')}]
    save(run, f'inputs/{stage}-schema.json', schema)
    print(json.dumps({'stage': stage, 'batches': batches}))

# ---------------------------------------------------------------- join
def join(run, stage):
    b = load(run, 'bundle.json'); text = article(run); ntext = text.translate(NORM); units = b['units']
    schema = b['schemas'][stage]
    key = {'01': 'factual_targets', '02': 'results', '03': 'results', '04': 'findings', '05': 'edits', '06': 'edits', '07': 'units', '08': 'items', '09': 'items', '10': 'items'}[stage]
    idkey = {'01': 'id', '02': 'target_id', '03': 'target_id', '04': 'id', '05': 'finding_id', '06': 'edit_id', '07': 'id', '08': 'item_id', '09': 'item_id', '10': 'item_id'}[stage]
    entries = merge_stage_outputs(run, stage, key)
    item_schema = schema['properties'][key]['items']
    # expected ids
    expected = None
    if stage == '02': expected = [l['id'] for l in b['links']]
    elif stage == '03': expected = [t['id'] for t in load(run, 'joined/01.json')['factual_targets']]
    elif stage == '05': expected = [f['id'] for f in load(run, 'joined/04.json')['findings']]
    elif stage == '06': expected = [e['finding_id'] for e in load(run, 'joined/05.json')['edits']]
    elif stage == '07': expected = [u['id'] for u in units if u['type'] != 'heading']
    elif stage == '08': expected = [e['edit_id'] for e in load(run, 'joined/06.json')['edits']]
    elif stage == '09': i = load(run, 'inputs/09-all.json'); expected = [x['target_id'] for x in i['targeted_corrections']] + [x['item_id'] for x in i['retained_whole_article_items']]
    elif stage == '10': expected = [x['item_id'] for x in load(run, 'inputs/10-all.json')['retained_items_after_merge']]
    problems = Counter(); located = Counter()
    by_id = {}
    for e in entries:
        eid = e.get(idkey)
        h = {'problems': check_schema(e, item_schema)}
        if eid in by_id: h['problems'].append('duplicate id'); problems['duplicate'] += 1
        by_id[eid] = e
        # locate passages
        hint = None
        if stage in ('02', '03', '09', '10') and expected is not None:
            src = _source_unit(run, stage, eid)
            hint = src.get('start_offset') if src else None
        for field in ('passage', 'anchor_sentence', 'sentence'):
            if e.get(field):
                s, en, m = locate(text, ntext, e[field], hint)
                h[field + '_offsets'] = [s, en]; h[field + '_match'] = m; located[m.split('-')[0]] += 1
                if s is None: h['problems'].append(f'{field} unlocated')
                elif hint is None: hint = s
        if hint is not None:
            h['structural_unit_id'] = unit_at(units, hint)
        elif stage == '02':
            l = next((l for l in b['links'] if l['id'] == eid), None)
            if l: h['structural_unit_id'] = l['structural_unit_id']
        if stage == '09' and e.get('verdict') in ('accept', 'repaired'):
            src = _source_unit(run, stage, eid) or {}
            h['structural_unit_id'] = (src.get('harness') or {}).get('structural_unit_id') or h.get('structural_unit_id')
        for p in h['problems']: problems[p.split(' ')[0]] += 1
        e['harness'] = h
    # missing
    missing = []
    if expected is not None:
        for eid in expected:
            if eid not in by_id:
                missing.append(eid); problems['missing'] += 1
                by_id[eid] = {idkey: eid, 'verdict': 'missing', 'harness': {'problems': ['no entry returned by the stage'], 'structural_unit_id': None}}
        extra = [i for i in by_id if i not in set(expected)]
        for i in extra: problems['unexpected'] += 1; by_id[i]['harness']['problems'].append('id not in assigned set')
    ordered = [by_id[i] for i in (expected or list(by_id))]
    # stage-specific joins: carry the source unit onto each entry for downstream readers
    if stage in ('02', '03', '05', '06', '08', '09', '10'):
        for e in ordered:
            src = _source_unit(run, stage, e[idkey])
            if src: e['unit'] = {k: v for k, v in src.items() if k not in ('harness',)} if stage in ('02', '03') else src
    out = {key: ordered, 'harness_summary': {'entries': len(entries), 'expected': len(expected) if expected is not None else None, 'missing': missing, 'located': dict(located), 'problems': dict(problems), 'files': [os.path.basename(f) for f in stage_files(run, stage)]}}
    if stage in ('02', '03', '05', '06', '08', '09', '10'):
        vk = {'05': 'scope', '06': 'scope', '10': 'edit_class'}.get(stage, 'verdict')
        out['harness_summary']['verdicts'] = dict(Counter(e.get(vk, 'missing') for e in ordered))
    if stage == '10':
        d = json.load(open(stage_files(run, '10')[0])); out['article'] = d.get('article')
    save(run, f'joined/{stage}.json', out)
    print(json.dumps(out['harness_summary']))

def _source_unit(run, stage, eid):
    """The upstream record an entry refers to."""
    b = load(run, 'bundle.json')
    if stage == '02': return next((l for l in b['links'] if l['id'] == eid), None)
    if stage == '03': return next((t for t in load(run, 'joined/01.json')['factual_targets'] if t['id'] == eid), None)
    if stage == '05': return next((f for f in load(run, 'joined/04.json')['findings'] if f['id'] == eid), None)
    if stage == '06': return next((f for f in load(run, 'joined/05.json')['edits'] if f['finding_id'] == eid), None)
    if stage == '08': return next((f for f in load(run, 'joined/06.json')['edits'] if f['edit_id'] == eid), None)
    if stage == '09':
        i = load(run, 'inputs/09-all.json')
        return next((x for x in i['targeted_corrections'] if x['target_id'] == eid), None) or next((x for x in i['retained_whole_article_items'] if x['item_id'] == eid), None)
    if stage == '10': return next((x for x in load(run, 'inputs/10-all.json')['retained_items_after_merge'] if x['item_id'] == eid), None)
    return None

if __name__ == '__main__':
    cmd, run, stage = sys.argv[1], sys.argv[2], sys.argv[3]
    {'inputs': inputs, 'join': join}[cmd](run, stage)
