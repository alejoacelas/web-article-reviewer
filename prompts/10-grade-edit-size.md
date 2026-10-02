# Grade edit size

Grade every retained item from the merge against the complete immutable article and the
paragraph purpose map, then classify the article. Do not browse, re-judge evidence,
improve wording, or discover new issues. The reviewers have already written what each
correction disturbs in their `problem` and reason prose; that prose, the item's
replacement or comment, and the map are your only inputs. Each retained item carries
its joined unit record, the merge verdict, and a `structural_unit_id` that the harness
set by offset containment; read that unit's map entry and the entries it lists in
`depended_on_by`.

For each item return:

- `edit_class`:
  - `bounded` when the replacement changes only what the evidence requires and every
    unit it touches still supports its recorded `purpose` and `argument_summary`.
  - `structural` when the item is an `editorial_escalation` whose comment says the
    example, framing, or argument has to change, or when applying the replacement or
    footnote would leave its unit, or a unit in its `depended_on_by`, no longer
    supporting a recorded `argument_summary` or supporting a different one. Quote the
    map field and say which words break it. Targeted corrections have not been through
    this test before; apply it to them exactly as the pruner applies it to
    whole-article items.
  - An escalation whose comment says only that no wording in the author's voice was
    found is `bounded`; it is a wording problem, not a size problem. Say so.
- `blast_radius`, the largest unit the item disturbs:
  - `span` — only the quoted words.
  - `sentence` — the sentence is rewritten.
  - `adjacent` — the reviewer's prose names other sentences in the same paragraph, cell,
    caption, or footnote that are dated with it.
  - `paragraph` — the unit's `purpose` or `argument_summary` changes.
  - `section` — a unit in `depended_on_by` or the section's conclusion changes.
  Quote the words from the reviewer's prose or the map that justify the level.

Then classify the article:

- `clean` when no items were retained.
- `bounded` when every item is `bounded` at radius `span`, `sentence`, or `adjacent`.
- `structural` otherwise; report `max_blast_radius`.

Also report `bounded_count`, `structural_count`, and `targets_checked` (from the run
metadata) so a sampled run can be read as a rate.

Return one entry per item id and one article entry matching `[OUTPUT_SCHEMA_JSON]`.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Retained items after merge

[MERGED_ITEMS_JSON]

## Paragraph purpose map

[PARAGRAPH_PURPOSES_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
