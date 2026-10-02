# Current prompts

These prompts implement the [edit design](../DESIGN.md).

## Delta contract

Every stage after the first receives units keyed by id and returns one entry per id
containing only the fields that stage adds: a verdict, a draft, a polished draft, a
prune reason, a repair. The harness joins each delta onto the immutable unit record, so
no prompt asks the model to preserve, copy, or refrain from overwriting earlier fields;
the model cannot drop what it never re-emits. Field lists live in the output schemas,
and the prompts carry only the judgment each stage must make.

## Targeted review

1. The harness lists every link from the article's Markdown (one unit per occurrence,
   with offsets and any automated signal) and one stage
   [targets every narrow factual claim](01-target-factual-claims.md).
2. [Review links and citations](02-review-links-and-citations.md) and
   [review atomic facts](03-review-atomic-facts.md) independently with the full
   article as context, batched by section (about 25 targets per call at most). Both go
   straight to validation.

## Whole-article review

1. [Discover later developments](04-discover-later-developments.md) that would make a
   careful reader read a passage differently, and collect their evidence.
2. [Draft each finding](05-draft-later-developments.md) as the scope that disturbs the
   main text least: footnote, bounded edit, or anchored editor comment. One definition
   of adequate article text is shared by the drafter, polisher, and pruner; a finding
   with no adequate text is escalated, never dropped.
3. [Polish the drafts](06-polish-whole-article-edits.md).
4. [Map each paragraph's purpose and argument summary](07-map-paragraph-purposes.md)
   from the article alone (only prompts 08 and 10 see the map), then [prune the polished items](08-prune-whole-article-edits.md)
   by keeping only those that change a recorded purpose or summary, with no numerical
   cap.

## Merge

[Validate and merge](09-validate-and-merge.md) the targeted corrections and retained
whole-article items without discovering new issues.

## Grade

[Grade edit size](10-grade-edit-size.md) classifies each retained item as bounded or
structural with a blast radius, then the article as clean, bounded, or structural, by
the criteria in [edit size](../docs/edit-size.md). It is the only stage that applies
the pruner's argument-summary test to targeted corrections.
