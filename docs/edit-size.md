# Ranking articles by edit size

Once the pipeline has merged an article's edits, how big is the job it implies? This
note fixes the criteria so a future grading pass can apply them. It reuses distinctions
the current prompts already make; it adds no field to any reviewer.

## Why count and length fail

Four corrections to misspelt names may be quick to accept, while one corrected
premise may require rewriting a section. The useful measure is how far a correction
propagates, not how many corrections there are.

## Two edit classes, from fields the pipeline already returns

- **Bounded** — a `change` from the link or fact reviewer. Prompt 03 defines it as a
  replacement that stays inside its paragraph, table cell, caption, or footnote and
  changes only what the evidence requires. Misspellings, refreshed figures and dates,
  and one-sentence reframings all land here; the prompts do not distinguish them and
  the ranking does not need to.
- **Structural** — anything that changes what a passage argues. The pipeline already
  names this in two places: prompt 03's `editorial_escalation` ("the example, framing,
  or argument would have to change" before an honest replacement fits), and every
  whole-article item retained by prompt 08, which survives only if the edited unit
  "would no longer support its recorded `argument_summary`". A premise reversal can
  fit within a paragraph and still change its argument.
  Prompt 03 can return it as `change`, and prompt 09 does not apply the pruning
  rule to targeted corrections. [Prompt 10](../prompts/10-grade-edit-size.md) closes that gap.

The drafter's and pruner's `editorial_escalation` can also mean "no text in the
author's voice" (adequacy rule c), which is a wording problem, not a size problem. Read
its comment before counting it as structural.

## Blast radius

The largest unit a correction disturbs, in increasing order:

1. `span` — the quoted words only.
2. `sentence` — the sentence has to be rewritten.
3. `adjacent` — neighbouring sentences in the same paragraph are dated with it (prompt
   03 already asks the reviewer to record this in `problem`).
4. `paragraph` — the paragraph's recorded `purpose` or `argument_summary` changes
   (the prompt 08 test).
5. `section` — a unit listed in `depended_on_by`, or the section's conclusion, changes.

This is graded after merge by [prompt 10](../prompts/10-grade-edit-size.md), which reads each retained item, its `problem`
and reason prose, and the paragraph purpose map, and returns a level per item. The
reviewers are not asked for a second span list; the prose they already write is the
input. The harness sets `structural_unit_id` on each retained item by offset
containment over the units from `pipeline/split_units.py`.

## Article categories

Score an article by its worst edit, not by summing:

| Category | Rule |
|---|---|
| **Clean** | no retained items |
| **Bounded** | only bounded items, all at radius `span`–`adjacent` |
| **Structural** | at least one structural item, or any item at radius `paragraph` or `section`; report the maximum radius |

Within Structural, a higher maximum radius is worse. Report the count of bounded items
alongside as the editor's mechanical workload, normalised by targets checked when a
run sampled.

## Traffic stays a separate axis

Keep pageviews separate from edit size. Present the queue as category first,
pageviews second within category: high-traffic Structural articles need an author;
Bounded articles can be accepted in a batch whatever their traffic.
