# Prune whole-article edits

Judge every polished footnote, edit, and editor comment against the complete immutable
article, its fixed evidence, and the paragraph purpose map. Do not browse, discover new
issues, rewrite drafts, or apply a numerical cap.

Keep an item only when the edited unit would no longer support its recorded
`argument_summary` (or that of a unit listed in its `depended_on_by`), or would support
a different one. Quote the field and say which words of the edit break it. Reject an
item whose unit still supports every recorded field, however well-evidenced and correct
it is; small corrections belong to the targeted reviewers, not to this pass.

Edits from earlier runs that left the summary unchanged and should be rejected:

- "268 predictions" → "121 forecasters" on a Metaculus question whose 12% probability
  is what the paragraph uses.
- "on average" → "at the median" where the compared estimates are unchanged.
- "senior research manager" → "senior researcher" in a podcast guest's biography.
- "Fermentation methods" → "Precision fermentation methods" where the sentence already
  describes the subtype.
- A footnote reporting that operational-validity estimates vary across settings, when
  the section's advice does not depend on their constancy.
- A citation moved from a preprint to the journal version when the link already reaches
  the right paper and the quoted figures are unchanged.

Edits that changed the summary and were rightly kept:

- "twice as likely" → "more likely", where the summary recorded a large effect and a
  twenty-times-larger meta-analysis found a small one.
- "the majority of EU laying hens" → about 38%, crossing the threshold the summary
  needed.
- The 90% and 30% forecasts attributed to hundreds of experts when they came from a
  22-person follow-up, changing what the list shows about expert agreement.
- "has not gained any traction in the US" when commercial rollout began there.

When two retained items overlap, keep both only when they make compatible changes to
different facts; otherwise keep the smaller complete remedy with stronger direct
evidence and record the conflict.

Article text is adequate only if it (a) claims no more certainty than the recorded
evidence, (b) leaves the article's argument intact, (c) reads in the author's voice, and
(d) does not remove support another passage relies on. When no adequate text exists,
return `editorial_escalation` with an anchored comment; never drop the finding.
When an item passes the argument test but its text is not adequate, convert it to
`editorial_escalation` instead of rejecting it.

Return one entry per item id matching `[OUTPUT_SCHEMA_JSON]`: the verdict, the quoted
map field, and a concrete reason. Rejected items are returned, not dropped.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Polished whole-article edits

[POLISHED_EDITS_JSON]

## Paragraph purpose map

[PARAGRAPH_PURPOSES_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
