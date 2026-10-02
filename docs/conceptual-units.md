# Conceptual units

> **2026-08-27 update.** The atomic unit is now a *claim located in a passage* (a
> sentence, table cell with labels, caption, alt text, or footnote sentence), and a fact
> correction is a full replacement of that passage, changing only what the evidence
> requires. Targeting no longer quotes spans or offsets; the validator recovers exact
> offsets by matching the passage. This makes atomic and whole-article edits the same
> shape: a contiguous before/after passage. The text below predates this change.


The reviewer follows stable editorial objects instead of exposing a different JSON
shape at each pipeline stage.

## Source units

- A link consists of its anchor text, current URL, and exact article location.
- A passage consists of its exact text and article location.
- The source unit keeps one identity as it moves through the pipeline.

## Attached layers

- The concern states why the source unit merits checking.
- The finding states whether the evidence confirmed a problem.
- The change is exactly one patch operation:
  - `replace_url {occurrence_id, old_url, new_url}` — anchor text unchanged.
  - `replace_span {start, end, quoted_text, replacement}` — a sentence trim, factual
    correction, or bounded edit.
  - `insert_footnote {offset, note_text}` — main text unchanged.
  - `editor_comment {anchor_start, anchor_end, comment}` — no article text.
  Overlap detection, validation, and rendering read these coordinates and nothing else.
- One worker may create several layers in one call without collapsing their meanings.

## Link presentation

- Show the linked excerpt and anchor text as they appear in the article.
- Show the complete current URL.
- Show the complete replacement URL when a change is proposed.
- Show the concern, confirmed problem, evidence, and reason for changing the link.
- Show “checked — no change” when investigation clears the concern.

## Passage presentation

- Lead with the suggested edit applied in place, using a Google Docs-like inline
  presentation.
- Show the original and revised passages separately when an inline diff becomes hard
  to read.
- Keep the exact source passage and offsets available for audit.
- Put the evidence and its source directly below the edit.
- Preserve the model's problem statement and reason for the edit verbatim.

## Continuity

- A stage records what it added, confirmed, changed, normalised, excluded, or passed
  against the stable source unit.
- The viewer, Markdown comparison, validator, and eventual Google Docs output derive
  from the same source, concern, finding, and change fields.
- Nothing reaches Google Docs unless its exact review item and lineage can be shown.
- Interface labels or summaries may supplement recorded reasons but must not silently
  replace them.

The underlying workers do not need to emit presentation-oriented data. An adapter may
map their recorded outputs into these units as long as it preserves exact values and
records every transformation.
