# Review atomic facts

Review only the assigned factual targets, using the complete immutable article for
context. For each target, find the best current primary source and compare it with the
passage.

For every target ask one question: would the author, writing this passage today, still
write it this way? Judge against today whatever the passage's tense and even if it
names its own date or the old value remains a true lower bound. A claim that records
what happened or what someone said is still checked: if the record is wrong, or a later
event supersedes what the passage uses it for, propose the update. The `role` tag from
targeting is a hint, never a reason to skip a check.

Decide each target by one standard:

- `change` when a current primary source contradicts the passage or supersedes what it
  tells the reader. Return the full replacement passage, changing only what the
  evidence requires; the replacement may reach into adjacent sentences when the same
  fact anchors them, but not past the paragraph, table cell, caption, or footnote.
  Include small corrections; a wrong year, figure, or title is a real error even when
  minor. Keep or update any date alongside the value. Record in `problem` what the
  article's value was anchored to and any text beyond the passage that is now dated with
  it. Record the source and its date.
- `editorial_escalation` when the passage is outdated but no honest replacement fits
  within the boundary — the example, framing, or argument would have to change. Still
  attempt a draft first and include your best attempt in the comment, marked as such,
  with the evidence; the editor decides. Never drop a found problem because the wording
  is hard.
- `no_change` when a primary source confirms the passage as the author would write it
  today. Say what you checked.
- `unverifiable` only after you have actually searched and found no source that
  settles the claim. Say what you searched for.

Do not review claims outside the assigned list and do not propose link, citation,
stylistic, or structural changes.

There is no proposal cap and no later pruning pass; return every correction that meets
the standard.

Return one entry per assigned target id matching `[OUTPUT_SCHEMA_JSON]`.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Assigned factual targets

[FACTUAL_TARGETS_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
