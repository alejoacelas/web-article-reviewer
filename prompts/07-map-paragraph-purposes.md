# Map paragraph purposes

Read the complete immutable article and record, for every assigned unit (paragraph,
list item, footnote, or caption, each keyed by id with its exact text and offsets), what
the rest of the article relies on it for. Do not research,
judge any edit, or suggest wording. Only the pruning and grading passes read this map; discovery and
drafting passes never see it.

For each unit record:

- `purpose`: the job the unit does in its section's argument, in one sentence, such as
  "shows that expert and superforecaster estimates of AI extinction risk differ by an
  order of magnitude". Record more than one purpose only when the unit clearly does
  distinct jobs, such as making a claim and establishing the credibility of its source.
- `argument_summary`: what a reader is meant to believe or do after reading the unit,
  stated only as precisely as the argument uses it. Omit figures, names, dates,
  statistic types, publication venues, and qualifiers unless a later passage, a
  recommendation, or the section's conclusion depends on them. Where a figure matters,
  record the threshold the argument needs it to clear, such as "a small but non-trivial
  probability" or "most laying hens in the EU", rather than the number.
- `depended_on_by`: the ids of other units, earlier or later, that use this unit's
  content, or none.

Return one entry per assigned unit id, no more and no fewer; repeated headings,
captions, and references are distinct units. Match `[OUTPUT_SCHEMA_JSON]`.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Assigned structural units

[STRUCTURAL_UNITS_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
