# Polish whole-article edits

Polish each drafted footnote, edit, or editor comment against the complete immutable
article. Do not discover new issues, browse for new evidence, or change a finding's
factual basis or scope.

Make each suggestion clear, self-contained, and consistent with the surrounding
article. Change meaning and confidence only where the recorded finding requires it;
elsewhere preserve the author's meaning, voice, and level of confidence exactly. Prefer
the shortest wording that completely resolves the recorded finding.

Article text is adequate only if it (a) claims no more certainty than the recorded
evidence, (b) leaves the article's argument intact, (c) reads in the author's voice, and
(d) does not remove support another passage relies on. When no adequate text exists,
return `editorial_escalation` with an anchored comment; never drop the finding.
Convert a `footnote` or `drafted_edit` that cannot be made adequate into an
`editorial_escalation` with an anchored comment. Polish an existing escalation as a
comment without inventing article text.

Return one entry per edit id matching `[OUTPUT_SCHEMA_JSON]`.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Drafted whole-article edits

[DRAFTED_EDITS_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
