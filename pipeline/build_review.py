"""Render a finished run as the Markdown review document required by comparisons/README.md.

Usage: python3 pipeline/build_review.py <run-dir> [--doc-url URL]

Opens with the stage-10 grade line, then every retained item as a full edit unit (edit in
place, finding, verbatim reason, evidence, run), links with full current and replacement
URLs, escalations as anchored comments, then explicit sections for pruned or rejected
items and for every no-change / unverifiable target with its recorded reason.
"""
import json, os, sys, re

def J(run, n):
    p = os.path.join(run, 'joined', f'{n}.json'); return json.load(open(p)) if os.path.exists(p) else {}

def evidence_md(ev):
    return '\n'.join(f'  - <{e.get("url","")}> — "{e.get("quote","")}"' + (f' ({e["date"]})' if e.get('date') else '') for e in ev or []) or '  - none recorded'

def in_place(text, units, start, end, old, new):
    """Paragraph with the edit shown inline as ~~old~~ **new**."""
    if start is None:
        return f'~~{old}~~ **{new}**'
    u = next((u for u in units if u['start_offset'] <= start < u['end_offset']), None)
    if not u: return f'~~{old}~~ **{new}**'
    para = u['text']; s = start - u['start_offset']; e = min(end, u['end_offset']) - u['start_offset']
    return para[:s] + '~~' + para[s:e] + '~~ **' + new + '** ' + para[e:]

def main(run, doc_url=None):
    b = json.load(open(os.path.join(run, 'bundle.json'))); ident = b['identity']; units = b['units']
    text = open(ident['article_path']).read()
    j02, j03, j08, j09, j10 = (J(run, n) for n in ('02', '03', '08', '09', '10'))
    merged = {i['item_id']: i for i in j09.get('items', [])}; grade = {i['item_id']: i for i in j10.get('items', [])}
    art = j10.get('article') or {}
    run_label = os.path.relpath(run, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if run_label.startswith('..'): run_label = os.path.join(*os.path.abspath(run).split(os.sep)[-3:])
    retained = lambda iid: merged.get(iid, {}).get('verdict') in ('accept', 'repaired') and merged[iid].get('merge') in ('retained', 'conflict_recorded')
    out = [f'# Review: {ident["title"]}', '',
           f'**Grade:** {art.get("category","?")} · max blast radius `{art.get("max_blast_radius")}` · {art.get("bounded_count",0)} bounded, {art.get("structural_count",0)} structural · {art.get("targets_checked",0)} targets checked · checked {ident["checked_at"]}', '',
           f'Article: <{ident["url"]}> (WordPress {ident["wordpress_id"]}, modified {ident["wordpress_modified"]}). Run: `{run_label}`.' + (f' Review Doc: <{doc_url}>' if doc_url else ''), '']
    if art.get('reason'): out += [f'Grade reason: {art["reason"]}', '']
    counts = {'links': len(j02.get('results', [])), 'facts': len(j03.get('results', [])), 'whole': len(j08.get('items', []))}
    out += [f'Targets: {counts["links"]} links, {counts["facts"]} factual claims, {counts["whole"]} later-development items drafted. Merge verdicts: {json.dumps(j09.get("harness_summary",{}).get("verdicts",{}))}.', '']
    out += ['## Retained edits', '']
    n = 0
    def g(iid):
        gr = grade.get(iid); return f' — `{gr["edit_class"]}` / `{gr["blast_radius"]}`' if gr else ''
    for r in j02.get('results', []):
        iid = r['target_id']
        if r.get('verdict') not in ('change', 'editorial_escalation') or not retained(iid): continue
        n += 1; u = r.get('unit', {}); h = r.get('harness', {})
        out += [f'### {iid} · link{g(iid)}', '', f'- **Article excerpt:** {u.get("sentence","")}', f'- **Anchor text:** {u.get("anchor_text","")}', f'- **Current URL:** <{u.get("url","")}>']
        if r.get('change_type') == 'replace_url': out += [f'- **Replacement URL:** <{r.get("new_url","")}>']
        if r.get('change_type') == 'trim_sentence': out += [f'- **Trimmed sentence:** {r.get("replacement_sentence","")}']
        if r.get('verdict') == 'editorial_escalation': out += [f'- **Editor comment:** {r.get("comment","")}']
        out += [f'- **Reading:** {r.get("reading","")}', f'- **Finding:** {r.get("problem","")}', f'- **Why this edit:** {r.get("reason","")}', '- **Evidence:**', evidence_md(r.get('evidence')), f'- **Run:** stage 02 · `{run_label}/stages` · merge: {merged.get(iid,{}).get("reason","")}', '']
    for r in j03.get('results', []):
        iid = r['target_id']
        if r.get('verdict') not in ('change', 'editorial_escalation') or not retained(iid): continue
        n += 1; u = r.get('unit', {}); h = r.get('harness', {}); off = h.get('passage_offsets') or [None, None]
        out += [f'### {iid} · fact: {u.get("fact","")}{g(iid)}', '']
        if r.get('verdict') == 'change':
            out += ['- **Edit in place:**', '', '  > ' + in_place(text, units, off[0], off[1], r.get('passage', ''), r.get('replacement_passage', '')).replace('\n', '\n  > '), '']
        else:
            out += [f'- **Affected passage:** {u.get("passage","")}', f'- **Editor comment:** {r.get("comment","")}']
        out += [f'- **Finding:** {r.get("problem","")}', f'- **Why this edit:** {r.get("reason","")}', '- **Evidence:**', evidence_md(r.get('evidence')), f'- **Run:** stage 03 · `{run_label}/stages` · merge: {merged.get(iid,{}).get("reason","")}', '']
    for it in j08.get('items', []):
        iid = it['item_id']
        if it.get('verdict') == 'reject' or not retained(iid): continue
        n += 1; e = it.get('unit', {}); f = (e.get('unit') or {}).get('unit') or {}
        h = it.get('harness', {}); off = h.get('passage_offsets') or h.get('anchor_sentence_offsets') or [None, None]
        scope = 'editorial_escalation' if it.get('verdict') == 'convert_to_escalation' else e.get('scope')
        out += [f'### {iid} · later development · {scope}{g(iid)}', '']
        if scope == 'drafted_edit':
            out += ['- **Edit in place:**', '', '  > ' + in_place(text, units, off[0], off[1], e.get('passage', ''), e.get('replacement_passage', '')).replace('\n', '\n  > '), '']
        elif scope == 'footnote':
            out += [f'- **Anchor passage:** {e.get("anchor_sentence","")}', f'- **Proposed note:** {e.get("note_text","")}']
        else:
            out += [f'- **Affected passage:** {e.get("anchor_sentence","")}', f'- **Editor comment:** {it.get("comment") or e.get("comment","")}']
        out += [f'- **Finding:** {f.get("development","")}', f'- **Why this edit:** {it.get("reason","")}', f'- **Map field:** {it.get("map_field_quoted","")}', '- **Evidence:**', evidence_md(f.get('evidence')), f'- **Run:** stages 04–08 · `{run_label}/stages` · merge: {merged.get(iid,{}).get("reason","")}', '']
    if n == 0:
        out += ['No edits were retained. Abstention reasons are recorded per target below.', '']
    out += ['## Not retained', '']
    for it in j08.get('items', []):
        if it.get('verdict') == 'reject' or not retained(it['item_id']):
            out += [f'- **{it["item_id"]}** later development ({it.get("verdict")}; merge {merged.get(it["item_id"],{}).get("verdict","—")}): {it.get("reason","")}']
    for r in j02.get('results', []) + j03.get('results', []):
        iid = r['target_id']
        if r.get('verdict') in ('change', 'editorial_escalation') and not retained(iid):
            out += [f'- **{iid}** {r.get("verdict")} rejected at merge: {merged.get(iid,{}).get("reason","")}']
    out += ['', '## Checked, no change', '']
    for r in j02.get('results', []) + j03.get('results', []):
        if r.get('verdict') in ('no_change', 'unverifiable', 'missing'):
            u = r.get('unit', {}); what = u.get('fact') or f'{u.get("anchor_text","")} → {u.get("url","")}'
            out += [f'- **{r["target_id"]}** `{r.get("verdict")}` {what}: {r.get("reason","")}']
    open(os.path.join(run, 'review.md'), 'w').write('\n'.join(out) + '\n')
    print(os.path.join(run, 'review.md'), n, 'retained')

if __name__ == '__main__':
    a = sys.argv[1:]; main(a[0], a[a.index('--doc-url') + 1] if '--doc-url' in a else None)
