"""Deliver a finished run into a Google Doc with gdoc.

Usage: python3 pipeline/deliver.py <run-dir> --folder <drive-folder-id> [--doc <existing-doc-id>] [--dry-run]

Creates a native Doc from the captured article, then for every reviewed unit:
- retained `change` / `drafted_edit`  -> minimal `gdoc suggest` (only the words that differ,
  widened until the match is unique) + a comment anchored on the new text, or on unchanged
  context beside the edit, so the anchor survives acceptance
- retained `editorial_escalation` / `footnote` -> anchored comment (open)
- no_change / unverifiable / pruned / rejected -> anchored comment, then `gdoc resolve`
  so the history is kept but the editor sees only open items.
Comments are plain (`Problem / Why / Sources`) and never truncated: text beyond the Docs
limit (2048 UTF-8 bytes) continues as a reply in the same thread. Placement failures are
recorded in <run-dir>/delivery.json, never mentioned in the Doc. With --doc and an
existing delivery.json for that Doc, only items whose comment or suggestion failed are
redone.
"""
import json, os, re, subprocess, sys, time

ACCOUNT = os.environ.get('GDOC_ACCOUNT')
LIMIT = 1900  # bytes per comment; the API refuses > 2048
CALLOUT = re.compile(r'\[(\d+)\]\(#fn-\d+\)')
MDLINK = re.compile(r'\[((?:[^\[\]]|\[[^\]]*\])*)\]\((?:https?://|#)[^)\s]+(?:\s+"[^"]*")?\)')

def visible(md):
    """Approximate the text Google Docs shows for a Markdown fragment."""
    s = re.sub(r'\\([\\`{}#+\-.!$>|~])', r'\1', md)
    s = CALLOUT.sub(r'\1', s); s = MDLINK.sub(r'\1', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s); s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'\1', s)
    s = re.sub(r'^\s*(?:[-*+]|\d+\.)\s+', '', s.strip()); s = re.sub(r'^#+\s*', '', s)
    s = re.sub(r'\\([*_\[\]()])', r'\1', s)
    return re.sub(r'[ \t]+', ' ', s).strip()

def keep_links(md):
    """Replacement text for gdoc suggest: inline markdown links stay, everything else flattens."""
    s = re.sub(r'<[^>]+>', '', CALLOUT.sub(r'\1', md)).strip()
    s = re.sub(r'^\s*(?:[-*+]|\d+\.)\s+', '', s)
    return re.sub(r'\\([\\`{}#+\-.!$>|~])', r'\1', s)

def minimal_diff(old, new):
    """Split old/new into (prefix, old_core, new_core, suffix) on word boundaries."""
    ow, nw = old.split(' '), new.split(' ')
    i = 0
    while i < min(len(ow), len(nw)) and ow[i] == nw[i]: i += 1
    j = 0
    while j < min(len(ow), len(nw)) - i and ow[-1 - j] == nw[-1 - j]: j += 1
    prefix = ' '.join(ow[:i]); suffix = ' '.join(ow[len(ow) - j:]) if j else ''
    return prefix, ' '.join(ow[i:len(ow) - j]), ' '.join(nw[i:len(nw) - j]), suffix

def gdoc(*a, dry=False):
    if not ACCOUNT:
        raise ValueError('Set GDOC_ACCOUNT before delivering to Google Docs')
    quiet = ['--quiet'] if a[0] in ('suggest', 'comment', 'resolve', 'reply') else []
    cmd = ['gdoc', *a, '--account', ACCOUNT, '--json'] + quiet
    if dry: return {'ok': True, 'dry_run': True, 'cmd': cmd}
    js = None
    for attempt in range(3):
        p = subprocess.run(cmd, capture_output=True, text=True)
        js = None
        for line in reversed(p.stdout.strip().splitlines()):
            if line.startswith('{'):
                try: js = json.loads(line); break
                except json.JSONDecodeError: pass
        if js is None: js = {'ok': False, 'stderr': p.stderr.strip()[-600:], 'code': p.returncode}
        if js.get('ok'): return js
        if '429' in json.dumps(js) or '503' in json.dumps(js): time.sleep(5 * (attempt + 1)); continue
        return js
    return js

def chunks(text, limit=LIMIT):
    out, cur = [], ''
    for para in text.split('\n'):
        cand = (cur + '\n' + para) if cur else para
        if len(cand.encode()) <= limit: cur = cand; continue
        if cur: out.append(cur); cur = ''
        while len(para.encode()) > limit:
            cut = para.encode()[:limit].decode('utf-8', 'ignore'); k = cut.rfind(' ')
            cut = cut[:k] if k > limit // 2 else cut
            out.append(cut); para = para[len(cut):].lstrip()
        cur = para
    if cur: out.append(cur)
    return out or ['']

def sources(ev):
    urls = []
    for e in ev or []:
        u = (e.get('url') or '').strip()
        if u and u not in urls: urls.append(u)
    return 'Sources:\n' + '\n'.join(urls) if urls else 'Sources: none recorded.'

def main(run, folder, doc=None, dry=False):
    J = lambda n: json.load(open(os.path.join(run, 'joined', n))) if os.path.exists(os.path.join(run, 'joined', n)) else {}
    bundle = json.load(open(os.path.join(run, 'bundle.json'))); ident = bundle['identity']
    j02, j03, j08, j09, j10 = (J(f'{n}.json') for n in ('02', '03', '08', '09', '10'))
    merged = {i['item_id']: i for i in j09.get('items', [])}
    log = {'doc': None, 'items': [], 'counts': {}}
    prior = {}
    if doc and os.path.exists(os.path.join(run, 'delivery.json')):
        prev = json.load(open(os.path.join(run, 'delivery.json')))
        if prev.get('doc_id') == doc:
            prior = {i['id']: i for i in prev['items']}; log['doc'] = prev.get('doc'); log['summary_comment'] = prev.get('summary_comment')
            print('retrying only failed items from the previous delivery', file=sys.stderr)
    def done_before(iid):
        i = prior.get(iid)
        return bool(i) and i.get('comment', {}).get('ok') and ('suggest' not in i or i['suggest'].get('ok'))
    if not doc:
        r = gdoc('new', f'{ident["title"]} — review {ident["checked_at"]}', '--file', ident['article_path'], '--folder', folder, dry=dry)
        if not r.get('ok'): sys.exit('doc creation failed: ' + json.dumps(r))
        doc = r.get('id', 'DRY'); log['doc'] = r
    log['doc_id'] = doc; log['doc_url'] = f'https://docs.google.com/document/d/{doc}/edit'
    print('doc', log['doc_url'])

    def comment(anchors, text, resolve=False, msg=None):
        """Anchor on the first quote that works; overflow continues as replies.
        The first line (Problem / Checked / Not retained) is set apart by a blank line,
        and the Why and Sources blocks each start a new paragraph, so the top scans."""
        text = re.sub(r'\n(?=(Why|Sources|Merge|Current URL|Proposed footnote|Suggested replacement):)', '\n\n', text)
        text = re.sub(r'^([^\n]*)\n', r'\1\n\n', text, count=1)
        text = re.sub(r'\n{3,}', '\n\n', text)
        parts = chunks(text); r = None
        for q in [visible(a)[:400] for a in anchors if a and visible(a)] + [None]:
            r = gdoc('comment', doc, parts[0], *(['--quote', q] if q else []), dry=dry)
            if r.get('ok'): r['anchor'] = q; break
            if 'no match' not in json.dumps(r).lower() and 'not found' not in json.dumps(r).lower(): break
        if r.get('ok') and not dry:
            r['replies'] = [gdoc('reply', doc, r['id'], p, dry=dry).get('ok', False) for p in parts[1:]]
            if resolve:
                r['resolved'] = gdoc('resolve', doc, r['id'], '-m', msg or 'No change needed; kept for the record.', dry=dry).get('ok', False)
        return r

    def suggest(old_md, new_md, iid):
        """Suggest only the words that differ; widen the span until the match is unique.
        Returns the gdoc result plus the anchors a comment should use afterwards."""
        pr = prior.get(iid, {}).get('suggest')
        if pr and pr.get('ok'): return pr
        old, new = visible(old_md), keep_links(new_md)
        if not old or new_md.strip() == old_md.strip(): return {'ok': False, 'skipped': 'empty or identical text', 'anchors': [old]}
        if old == visible(new_md):  # URL swap: visible text unchanged, so suggest the whole anchor as a link
            r = gdoc('suggest', doc, old, new, '--normalize', dry=dry); r['old_core'] = old; r['new_core'] = new; r['anchors'] = [old]; return r
        prefix, oc, nc, suffix = minimal_diff(old, visible(new_md))
        # replacement core keeps inline links from the markdown replacement when the whole thing was one link swap
        _, _, nc_links, _ = minimal_diff(old, new)
        nc = nc_links if MDLINK.search(new) and not MDLINK.search(nc) else nc
        pw, sw = prefix.split(' ') if prefix else [], suffix.split(' ') if suffix else []
        take_p, take_s = (1 if not oc else 0), (1 if not oc else 0)  # pure insertion: borrow a neighbouring word
        r = None
        while True:
            ctx_p = ' '.join(pw[len(pw) - take_p:]) if take_p else ''
            ctx_s = ' '.join(sw[:take_s]) if take_s else ''
            o = ' '.join(x for x in (ctx_p, oc, ctx_s) if x); n = ' '.join(x for x in (ctx_p, nc, ctx_s) if x)
            r = gdoc('suggest', doc, o, n, '--normalize', dry=dry)
            if r.get('ok') or 'multiple matches' not in json.dumps(r): break
            if take_p >= len(pw) and take_s >= len(sw): break
            take_p = min(len(pw), take_p + 1); take_s = min(len(sw), take_s + 1)
        r['old_core'] = o if r else oc; r['new_core'] = n if r else nc
        r['anchors'] = [x for x in (n if r.get('ok') else None, ' '.join(pw[-8:]) if len(prefix) >= 20 else None, ' '.join(sw[:8]) if len(suffix) >= 20 else None, old) if x]
        return r

    def retained(iid):
        m = merged.get(iid); return bool(m) and m.get('verdict') in ('accept', 'repaired') and m.get('merge') in ('retained', 'conflict_recorded')

    def deliver_targeted(res, stage_name):
        iid = res['target_id']; v = res.get('verdict'); m = merged.get(iid) or {}; unit = res.get('unit') or {}
        old_anchor = res.get('passage') or unit.get('passage') or unit.get('sentence') or unit.get('anchor_text')
        what = unit.get('fact') or f'link "{unit.get("anchor_text","")}"'
        rec = {'id': iid, 'verdict': v, 'stage': stage_name}
        if v in ('no_change', 'unverifiable') or (v in ('change', 'editorial_escalation') and not retained(iid)):
            head = {'no_change': 'Checked, no change', 'unverifiable': 'Checked, unverifiable'}.get(v, f'Not retained at merge ({m.get("merge") or m.get("verdict")})')
            text = f'{head}: {what}.\n{res.get("reason","")}\n{sources(res.get("evidence"))}'
            if v not in ('no_change', 'unverifiable'): text = f'{head}: {what}.\nProblem: {res.get("problem","")}\nMerge: {m.get("reason","")}\n{sources(res.get("evidence"))}'
            rec['comment'] = comment([old_anchor], text, resolve=True, msg=head); rec['resolved'] = True
        elif v == 'change':
            if stage_name == '02' and res.get('change_type') == 'replace_url':
                rec['suggest'] = suggest(unit.get('anchor_text', ''), f'[{unit.get("anchor_text","")}]({res.get("new_url","")})', iid)
                text = f'Problem: {res.get("problem","")}\nWhy: {res.get("reason","")}\nCurrent URL: {unit.get("url")}\nReplacement URL: {res.get("new_url")}\n{sources(res.get("evidence"))}'
                anchors = [unit.get('anchor_text'), unit.get('sentence')]
            else:
                old_md = (res.get('sentence') or unit.get('sentence', '')) if stage_name == '02' else res.get('passage', '')
                new_md = res.get('replacement_sentence', '') if stage_name == '02' else res.get('replacement_passage', '')
                rec['suggest'] = suggest(old_md, new_md, iid)
                text = f'Problem: {res.get("problem","")}\nWhy: {res.get("reason","")}\n{sources(res.get("evidence"))}'
                if not rec['suggest'].get('ok'): text += f'\nSuggested replacement: {visible(new_md)}'
                anchors = rec['suggest'].get('anchors', []) + [old_anchor]
            rec['comment'] = comment(anchors, text)
        elif v == 'editorial_escalation':
            text = f'Problem: {res.get("comment") or res.get("problem","")}\nWhy: {res.get("reason","")}\n{sources(res.get("evidence"))}'
            rec['comment'] = comment([old_anchor], text)
        else:
            rec['comment'] = comment([old_anchor], f'No verdict returned for {what}.', resolve=True, msg='harness: no verdict'); rec['resolved'] = True
        log['items'].append(rec)

    def deliver_whole(item):
        iid = item['item_id']; m = merged.get(iid) or {}; e = item.get('unit') or {}
        scope = 'editorial_escalation' if item.get('verdict') == 'convert_to_escalation' else e.get('scope')
        anchor = e.get('passage') or e.get('anchor_sentence') or (e.get('unit') or {}).get('anchor_sentence')
        finding = ((e.get('unit') or {}).get('unit') or {}); dev = finding.get('development', ''); ev = finding.get('evidence')
        rec = {'id': iid, 'verdict': item.get('verdict'), 'scope': scope, 'stage': '08'}
        if item.get('verdict') == 'reject' or not retained(iid):
            head = 'Pruned' if item.get('verdict') == 'reject' else f'Not retained at merge ({m.get("merge") or m.get("verdict")})'
            rec['comment'] = comment([anchor], f'{head}: later development.\nProblem: {dev}\nWhy: {item.get("reason","")}\n{sources(ev)}', resolve=True, msg=head); rec['resolved'] = True
        elif scope == 'editorial_escalation':
            rec['comment'] = comment([anchor], f'Problem: {item.get("comment") or e.get("comment") or dev}\nWhy: {item.get("reason","")}\n{sources(ev)}')
        elif scope == 'footnote':
            rec['comment'] = comment([anchor], f'Problem: {dev}\nProposed footnote: {e.get("note_text","")}\nWhy: {item.get("reason","")}\n{sources(ev)}')
        else:
            rec['suggest'] = suggest(e.get('passage', ''), e.get('replacement_passage', ''), iid)
            text = f'Problem: {dev}\nWhy: {item.get("reason","")}\n{sources(ev)}'
            if not rec['suggest'].get('ok'): text += f'\nSuggested replacement: {visible(e.get("replacement_passage",""))}'
            rec['comment'] = comment(rec['suggest'].get('anchors', []) + [anchor], text)
        log['items'].append(rec)

    for r in j02.get('results', []):
        if done_before(r['target_id']): log['items'].append(prior[r['target_id']]); continue
        deliver_targeted(r, '02')
    for r in j03.get('results', []):
        if done_before(r['target_id']): log['items'].append(prior[r['target_id']]); continue
        deliver_targeted(r, '03')
    for it in j08.get('items', []):
        if done_before(it['item_id']): log['items'].append(prior[it['item_id']]); continue
        deliver_whole(it)
    if not (prior and log.get('summary_comment', {}).get('ok')):
        art = j10.get('article') or {}
        n_open = sum(1 for i in log['items'] if not i.get('resolved'))
        summ = (f'Article reviewer run, checked {ident["checked_at"]}. {n_open} open items (tracked suggestions and comments); '
                f'{len(log["items"]) - n_open} further targets were checked and found fine — they are recorded as resolved comments. '
                f'Edit-size grade: {art.get("category","?")}, {art.get("bounded_count",0)} bounded and {art.get("structural_count",0)} structural items.')
        log['summary_comment'] = comment([], summ)
    log['counts'] = {'items': len(log['items']), 'suggested': sum(1 for i in log['items'] if i.get('suggest', {}).get('ok')), 'suggest_failed': sum(1 for i in log['items'] if 'suggest' in i and not i['suggest'].get('ok')),
                     'comments_ok': sum(1 for i in log['items'] if i.get('comment', {}).get('ok')), 'comments_failed': sum(1 for i in log['items'] if not i.get('comment', {}).get('ok')), 'resolved': sum(1 for i in log['items'] if i.get('resolved')),
                     'replies': sum(len(i.get('comment', {}).get('replies', [])) for i in log['items'])}
    json.dump(log, open(os.path.join(run, 'delivery.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(log['counts']))

if __name__ == '__main__':
    a = sys.argv[1:]; run = a[0]
    folder = a[a.index('--folder') + 1] if '--folder' in a else None
    doc = a[a.index('--doc') + 1] if '--doc' in a else None
    main(run, folder, doc, dry='--dry-run' in a)
