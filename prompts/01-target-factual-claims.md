# Target narrow factual claims

Read the complete immutable article, footnotes included, and list the factual claims the
fact reviewer will check. Do not research, judge whether an edit is needed, or suggest
wording. Links are not your job; the harness lists every link from the article's
Markdown.

List every narrow factual claim: dates, numbers, names, titles, policies, statuses,
units, and short factual clauses. Exclude opinions, forecasts, hypotheticals, and
compound arguments. Claims inside link anchor text, table cells, figure captions, image
alt text, blockquotes, and footnotes all count.

The unit is the claim located in its passage, not a span. For each target give:

- `passage`: the exact text of the unit that contains the claim — a sentence, a table
  cell with its row and column labels, a caption, an alt text, or a footnote sentence.
  The reviewer proposes a replacement for this passage.
- `fact`: a few words naming what to check, such as "share of new code written by AI",
  "release date of o3", or "Steve Newman's title".
- `role`: `current_state` when the passage tells the reader how things stand now,
  `record` when it reports what happened or what someone said, `fixed` when it cannot
  change (a definition, a name, an attribution). The tag is for reporting yield by
  class; the reviewer checks every target regardless.

One passage may hold several claims; list each as its own target with the same
passage. Return JSON matching `[OUTPUT_SCHEMA_JSON]`.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
