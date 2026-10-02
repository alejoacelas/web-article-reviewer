# Draft later-development edits

Turn each finding into the edit that disturbs the main text least while still
resolving it, using the complete immutable article for context. Do not discover new
issues or research new evidence.

Article text is adequate only if it (a) claims no more certainty than the recorded
evidence, (b) leaves the article's argument intact, (c) reads in the author's voice, and
(d) does not remove support another passage relies on. When no adequate text exists,
return `editorial_escalation` with an anchored comment; never drop the finding.

Choose the scope:

1. `footnote` when the main text remains accurate as written and the finding only
   qualifies it; write a short self-contained note.
2. `drafted_edit` when the main text is no longer accurate. Bounded rewrites are
   allowed when the evidence entails them, within the adequacy rules above.
3. `editorial_escalation` when no adequate article text exists. Write an anchored
   comment stating the finding and what the editor should reconsider.

Cite the recorded evidence in the suggested text or comment.

Return one entry per finding id matching `[OUTPUT_SCHEMA_JSON]`.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Later-development findings

[DEVELOPMENT_FINDINGS_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
