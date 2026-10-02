# Validate and merge edits

Validate the targeted corrections and retained whole-article items against the complete
immutable article. Do not discover new issues, browse, improve wording, or reconsider
an evidence judgment.

Repair a mechanical defect when the intended unit and change are unambiguous:
recompute an offset, replace a slightly inexact quotation with the exact article text,
or recover an identifier already present in the lineage. Record the original value,
repaired value, and repair method. Reject an item when a repair would require choosing
among several passages, changing the finding or wording, or inventing evidence.
Your checks are mechanical, and only these: every schema field is present; the quoted
span matches the article at its offsets; the patch operation is valid for its type (a
URL swap names an existing link occurrence, a span replacement has non-empty
replacement text, a footnote has an insertion offset, an escalation has an anchor and
no replacement); the item stays within its reviewer's scope (the link reviewer changes
URLs or trims sentences, the fact reviewer replaces its quoted span); and each `change`
records a dated source. You cannot browse, so never judge whether the evidence is
right, only whether it is recorded. Targeted corrections have not passed through
pruning; do not apply the pruning rule to them.

When items overlap, retain both only when they make compatible changes to different
facts. Otherwise retain the smaller complete remedy with stronger direct evidence and
record the conflict. An `editorial_escalation` stays an anchored comment and is never
rendered as article text.

Return one entry per item id matching `[OUTPUT_SCHEMA_JSON]`: the verdict, any repairs,
and any merge decision. Rejected items are returned, not dropped.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Targeted corrections

[TARGETED_CORRECTIONS_JSON]

## Retained whole-article items

[WHOLE_ARTICLE_ITEMS_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
