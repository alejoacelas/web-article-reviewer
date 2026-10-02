export const meta = {
  name: 'article-review-ten-stage',
  description: 'Run prompts 01-10 of the article reviewer over one captured article',
  phases: [
    { title: '01 target', detail: 'list narrow factual claims (Opus)' },
    { title: '02-04, 07 review', detail: 'links, facts, later developments, purpose map in parallel (Opus)' },
    { title: '05-06 draft', detail: 'draft and polish later-development edits (Fable)' },
    { title: '08 prune', detail: 'prune whole-article items against the map (Fable)' },
    { title: '09 validate', detail: 'validate and merge (Opus)' },
    { title: '10 grade', detail: 'grade edit size (Fable)' },
  ],
}
// args: { project, run, article_path, identity, prompt_files: {'01': 'prompts/01-...md', ...} }
const A = args
const INPUTS_SCHEMA = { type: 'object', required: ['stage', 'batches'], properties: { stage: { type: 'string' }, batches: { type: 'array', items: { type: 'object', required: ['id', 'count'], properties: { id: { type: 'string' }, path: { type: ['string', 'null'] }, count: { type: 'integer' }, section: { type: 'string' }, map_path: { type: 'string' } }, additionalProperties: false } }, error: { type: 'string' } }, additionalProperties: false }
const JOIN_SCHEMA = { type: 'object', required: ['entries'], properties: { entries: { type: 'integer' }, expected: { type: ['integer', 'null'] }, missing: { type: 'array', items: { type: 'string' } }, located: { type: 'object', additionalProperties: { type: 'integer' } }, problems: { type: 'object', additionalProperties: { type: 'integer' } }, verdicts: { type: 'object', additionalProperties: { type: 'integer' } }, files: { type: 'array', items: { type: 'string' } }, error: { type: 'string' } }, additionalProperties: false }
const fix = v => { if (typeof v === 'string') { try { return JSON.parse(v) } catch (e) { return v } } return v }
const MODEL = { '01': 'opus', '02': 'opus', '03': 'opus', '04': 'opus', '05': 'fable', '06': 'fable', '07': 'opus', '08': 'fable', '09': 'opus', '10': 'fable' }
const INPUT_KEY = { '02': 'LINK_TARGETS_JSON', '03': 'FACTUAL_TARGETS_JSON', '05': 'DEVELOPMENT_FINDINGS_JSON', '06': 'DRAFTED_EDITS_JSON', '07': 'STRUCTURAL_UNITS_JSON', '08': 'POLISHED_EDITS_JSON', '09': 'TARGETED_CORRECTIONS_JSON and WHOLE_ARTICLE_ITEMS_JSON (two keys in one file)', '10': 'MERGED_ITEMS_JSON' }
const WEB = new Set(['02', '03', '04'])
const summary = { stages: {}, retries: [] }

async function harness(cmd, stage, phase) {
  const prompt = `Run exactly this command and nothing else:\n\ncd ${A.project} && python3 pipeline/harness.py ${cmd} ${A.run} ${stage}\n\nReturn the JSON object printed on the last line of stdout as your structured output, verbatim. If the command fails, return {"error": "<stderr>"}.`
  const r = await agent(prompt, { label: `harness:${cmd}:${stage}`, phase, model: 'haiku', effort: 'low', schema: cmd === 'inputs' ? INPUTS_SCHEMA : JOIN_SCHEMA })
  if (!r || r.error) throw new Error(`harness ${cmd} ${stage} failed: ${r && r.error}`)
  for (const k of Object.keys(r)) r[k] = fix(r[k])
  return r
}

function envelope(stage, batch) {
  const lines = [
    `You are one stage of the article-review pipeline (stage ${stage}, batch ${batch.id}). Your final text is machine-read; return only the structured output.`,
    ``,
    `1. Read your instructions in full: \`cat ${A.project}/${A.prompt_files[stage]}\`. Follow them exactly. They contain placeholders in square brackets; their values are:`,
    `   - [ARTICLE_IDENTITY_JSON] = ${JSON.stringify(A.identity)}`,
    `   - [ARTICLE_TEXT] = the complete immutable article in the file ${A.article_path}. Read the whole file (it is long; use cat, not a truncated view).`,
  ]
  if (batch.path) lines.push(`   - [${INPUT_KEY[stage]}] = the JSON file ${batch.path.startsWith('/') ? batch.path : A.project + '/' + batch.path}. Read it in full; it holds exactly the items assigned to you.`)
  if (batch.map_path) lines.push(`   - [PARAGRAPH_PURPOSES_JSON] = the JSON file ${batch.map_path}.`)
  lines.push(`   - [OUTPUT_SCHEMA_JSON] = the JSON file ${A.run}/inputs/${stage}-schema.json.`)
  if (WEB.has(stage)) lines.push(`2. You have live web access (WebFetch, WebSearch, curl). Use it wherever the instructions say to open a destination or find a source; record what you opened. The date today is ${A.identity.checked_at}.`)
  else lines.push(`2. Do not browse the web; this stage works from the article and its inputs only.`)
  lines.push(`3. Produce the complete JSON output required by the instructions and schema. Save it verbatim to ${A.run}/stages/${batch.id}.json (write the file with python or a heredoc; create no other files), then return the identical JSON as your structured output.`)
  lines.push(`4. Return one entry per assigned id, no more and no fewer. Copy every quoted passage character-for-character from the article file, including curly quotes.`)
  return lines.join('\n')
}

async function runStage(stage, batch, phase, schema) {
  const opts = { label: `${batch.id}`, phase, model: MODEL[stage], schema }
  let r = await agent(envelope(stage, batch), opts)
  if (r === null) {
    summary.retries.push(batch.id)
    log(`${batch.id} returned null; retrying once`)
    r = await agent(envelope(stage, batch) + `\n\n(Retry attempt 2.)`, { ...opts, label: `${batch.id}-retry` })
  }
  return r
}

async function stage(stageNo, phase, schema) {
  const inp = await harness('inputs', stageNo, phase)
  const results = await parallel(inp.batches.map(b => () => runStage(stageNo, b, phase, schema)))
  const nulls = results.filter(r => r === null).length
  const j = await harness('join', stageNo, phase)
  summary.stages[stageNo] = { batches: inp.batches.length, null_agents: nulls, ...j }
  log(`stage ${stageNo}: ${inp.batches.length} call(s), ${JSON.stringify(j.verdicts || j.located || {})}, problems ${JSON.stringify(j.problems || {})}`)
  return j
}

// Output schemas, generated from pipeline/schemas/*.schema.json by pipeline/build_workflow.py
const S = {"01": {"title": "Factual targets", "type": "object", "required": ["factual_targets"], "properties": {"factual_targets": {"type": "array", "items": {"type": "object", "required": ["id", "passage", "fact", "role", "section"], "properties": {"id": {"type": "string", "description": "F001, F002, ... in article order"}, "passage": {"type": "string", "description": "exact text of the unit containing the claim, copied verbatim from the article: a sentence, a table cell with its row and column labels, a caption, an alt text, or a footnote sentence"}, "fact": {"type": "string", "description": "a few words naming what to check"}, "role": {"enum": ["current_state", "record", "fixed"]}, "section": {"type": "string", "description": "nearest preceding heading text, or 'Notes and references' for footnotes, or 'Preamble' before the first heading"}}, "additionalProperties": false}}}, "additionalProperties": false}, "02": {"title": "Link and citation review", "type": "object", "required": ["results"], "properties": {"results": {"type": "array", "items": {"type": "object", "required": ["target_id", "verdict", "reading", "problem", "reason", "evidence", "checked_date"], "properties": {"target_id": {"type": "string"}, "verdict": {"enum": ["change", "editorial_escalation", "no_change", "unverifiable"]}, "reading": {"type": "string", "description": "the reading a careful reader takes of the cited claim today"}, "change_type": {"enum": ["replace_url", "trim_sentence"], "description": "for change only"}, "new_url": {"type": "string", "description": "for replace_url: the complete canonical replacement URL"}, "sentence": {"type": "string", "description": "for trim_sentence: the exact current sentence copied from the article"}, "replacement_sentence": {"type": "string", "description": "for trim_sentence: the trimmed sentence"}, "comment": {"type": "string", "description": "for editorial_escalation: the anchored comment for the editor"}, "problem": {"type": "string", "description": "what is wrong, or empty for no_change"}, "reason": {"type": "string", "description": "2-4 sentences; for no_change/unverifiable say what you opened and checked, or what you tried"}, "evidence": {"type": "array", "items": {"type": "object", "required": ["url", "quote"], "properties": {"url": {"type": "string"}, "quote": {"type": "string", "description": "verbatim words from the source that settle the point"}, "date": {"type": "string", "description": "publication or access date, YYYY-MM-DD when known"}}, "additionalProperties": false}}, "checked_date": {"type": "string"}}, "additionalProperties": false}}}, "additionalProperties": false}, "03": {"title": "Atomic fact review", "type": "object", "required": ["results"], "properties": {"results": {"type": "array", "items": {"type": "object", "required": ["target_id", "verdict", "problem", "reason", "evidence", "checked_date"], "properties": {"target_id": {"type": "string"}, "verdict": {"enum": ["change", "editorial_escalation", "no_change", "unverifiable"]}, "passage": {"type": "string", "description": "for change: the exact current passage being replaced, copied from the article; may extend to adjacent sentences within the same paragraph, cell, caption, or footnote when the same fact anchors them"}, "replacement_passage": {"type": "string", "description": "for change: the full replacement passage, changing only what the evidence requires"}, "comment": {"type": "string", "description": "for editorial_escalation: the anchored comment, including your best attempted draft marked as such and the evidence"}, "problem": {"type": "string", "description": "what the article's value was anchored to and any text beyond the passage now dated with it; empty for no_change"}, "reason": {"type": "string", "description": "2-4 sentences; for no_change say what you checked, for unverifiable what you searched for"}, "evidence": {"type": "array", "items": {"type": "object", "required": ["url", "quote"], "properties": {"url": {"type": "string"}, "quote": {"type": "string", "description": "verbatim words from the source that settle the point"}, "date": {"type": "string", "description": "publication or access date, YYYY-MM-DD when known"}}, "additionalProperties": false}}, "checked_date": {"type": "string"}}, "additionalProperties": false}}}, "additionalProperties": false}, "04": {"title": "Later-development findings", "type": "object", "required": ["findings", "abstention_note"], "properties": {"findings": {"type": "array", "items": {"type": "object", "required": ["id", "anchor_sentence", "section", "development", "evidence", "reason", "reason_to_leave", "other_affected_passages", "published_after_update"], "properties": {"id": {"type": "string", "description": "D01, D02, ..."}, "anchor_sentence": {"type": "string", "description": "the exact sentence whose reading changes, copied verbatim from the article"}, "section": {"type": "string"}, "development": {"type": "string", "description": "what happened and how it changes what the passage establishes"}, "evidence": {"type": "array", "items": {"type": "object", "required": ["url", "quote"], "properties": {"url": {"type": "string"}, "quote": {"type": "string", "description": "verbatim words from the source that settle the point"}, "date": {"type": "string", "description": "publication or access date, YYYY-MM-DD when known"}}, "additionalProperties": false}}, "reason": {"type": "string", "description": "why this clears the threshold; record any doubt here"}, "reason_to_leave": {"type": "string", "description": "the strongest reason an editor might reasonably leave the passage as it is"}, "other_affected_passages": {"type": "array", "items": {"type": "string"}, "description": "exact sentences elsewhere whose reading also changes; empty for a single-sentence qualification"}, "published_after_update": {"type": "boolean"}}, "additionalProperties": false}}, "abstention_note": {"type": "string", "description": "if no findings, what you looked for and why nothing cleared the threshold; otherwise empty"}}, "additionalProperties": false}, "05": {"title": "Drafted whole-article edits", "type": "object", "required": ["edits"], "properties": {"edits": {"type": "array", "items": {"type": "object", "required": ["finding_id", "scope", "anchor_sentence", "reason"], "properties": {"finding_id": {"type": "string"}, "scope": {"enum": ["footnote", "drafted_edit", "editorial_escalation"]}, "anchor_sentence": {"type": "string", "description": "exact sentence from the article the edit, footnote, or comment attaches to"}, "passage": {"type": "string", "description": "for drafted_edit: the exact current passage being replaced, copied from the article"}, "replacement_passage": {"type": "string", "description": "for drafted_edit: the replacement"}, "note_text": {"type": "string", "description": "for footnote: the short self-contained note, citing the evidence"}, "comment": {"type": "string", "description": "for editorial_escalation: the anchored editor comment stating the finding and what to reconsider"}, "reason": {"type": "string", "description": "why this scope and why the text is adequate, or why none is"}}, "additionalProperties": false}}}, "additionalProperties": false}, "06": {"title": "Polished whole-article edits", "type": "object", "required": ["edits"], "properties": {"edits": {"type": "array", "items": {"type": "object", "required": ["edit_id", "scope", "polish_note"], "properties": {"edit_id": {"type": "string"}, "scope": {"enum": ["footnote", "drafted_edit", "editorial_escalation"], "description": "unchanged unless the item had to be converted to editorial_escalation"}, "passage": {"type": "string", "description": "for drafted_edit: exact current passage (may be corrected to the exact article text)"}, "replacement_passage": {"type": "string"}, "note_text": {"type": "string"}, "comment": {"type": "string"}, "polish_note": {"type": "string", "description": "what changed in the wording and why, or 'unchanged'"}}, "additionalProperties": false}}}, "additionalProperties": false}, "07": {"title": "Paragraph purpose map", "type": "object", "required": ["units"], "properties": {"units": {"type": "array", "items": {"type": "object", "required": ["id", "purpose", "argument_summary", "depended_on_by"], "properties": {"id": {"type": "string"}, "purpose": {"type": "string"}, "argument_summary": {"type": "string"}, "depended_on_by": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": false}}}, "additionalProperties": false}, "08": {"title": "Pruned whole-article edits", "type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["item_id", "verdict", "map_field_quoted", "reason"], "properties": {"item_id": {"type": "string"}, "verdict": {"enum": ["keep", "reject", "convert_to_escalation"]}, "map_field_quoted": {"type": "string", "description": "the purpose or argument_summary text judged against, quoted"}, "reason": {"type": "string", "description": "which words of the edit break (or fail to break) the quoted field"}, "comment": {"type": "string", "description": "for convert_to_escalation: the anchored editor comment"}, "conflict_with": {"type": "array", "items": {"type": "string"}, "description": "ids of overlapping items and how the conflict was resolved"}}, "additionalProperties": false}}}, "additionalProperties": false}, "09": {"title": "Validated and merged items", "type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["item_id", "verdict", "repairs", "merge", "reason"], "properties": {"item_id": {"type": "string"}, "verdict": {"enum": ["accept", "repaired", "reject"]}, "repairs": {"type": "array", "items": {"type": "object", "required": ["field", "original", "repaired", "method"], "properties": {"field": {"type": "string"}, "original": {"type": "string"}, "repaired": {"type": "string"}, "method": {"type": "string"}}, "additionalProperties": false}}, "merge": {"enum": ["retained", "superseded", "conflict_recorded"]}, "superseded_by": {"type": "string"}, "reason": {"type": "string"}}, "additionalProperties": false}}}, "additionalProperties": false}, "10": {"title": "Edit size grade", "type": "object", "required": ["items", "article"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["item_id", "edit_class", "blast_radius", "justification"], "properties": {"item_id": {"type": "string"}, "edit_class": {"enum": ["bounded", "structural"]}, "blast_radius": {"enum": ["span", "sentence", "adjacent", "paragraph", "section"]}, "map_field_quoted": {"type": ["string", "null"], "description": "The purpose or argument_summary text that the edit breaks; null for bounded items"}, "justification": {"type": "string", "minLength": 1, "description": "Quote the reviewer prose or map words that justify the class and radius"}}, "additionalProperties": false}}, "article": {"type": "object", "required": ["category", "max_blast_radius", "bounded_count", "structural_count", "targets_checked", "reason"], "properties": {"category": {"enum": ["clean", "bounded", "structural"]}, "max_blast_radius": {"enum": ["span", "sentence", "adjacent", "paragraph", "section", null]}, "bounded_count": {"type": "integer", "minimum": 0}, "structural_count": {"type": "integer", "minimum": 0}, "targets_checked": {"type": "integer", "minimum": 0}, "reason": {"type": "string", "minLength": 1}}, "additionalProperties": false}}, "additionalProperties": false}}

phase('01 target')
await stage('01', '01 target', S['01'])

phase('02-04, 07 review')
await parallel([
  () => stage('02', '02-04, 07 review', S['02']),
  () => stage('03', '02-04, 07 review', S['03']),
  () => stage('04', '02-04, 07 review', S['04']),
  () => stage('07', '02-04, 07 review', S['07']),
])

const findings = summary.stages['04'] && summary.stages['04'].entries
if (findings > 0) {
  phase('05-06 draft')
  await stage('05', '05-06 draft', S['05'])
  await stage('06', '05-06 draft', S['06'])
  phase('08 prune')
  await stage('08', '08 prune', S['08'])
} else {
  log('stage 04 returned no findings; skipping 05, 06, 08')
}

phase('09 validate')
await stage('09', '09 validate', S['09'])
phase('10 grade')
await stage('10', '10 grade', S['10'])
return summary
