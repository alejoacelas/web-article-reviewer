---
name: review-article
description: Review a published article URL (or a Google Doc) for evidence-backed updates — broken or superseded links, citations that no longer support their sentence, contradicted facts, later developments — and deliver a Google Doc with minimal suggested edits and anchored comments. Use when asked to review, fact-check, refresh, or update an article.
---

# Review an article

Ten prompts run as one pipeline, then the result becomes a Google Doc with tracked
suggestions and anchored comments. [DESIGN.md](../../DESIGN.md) says what counts as an
edit; the prompts implement it. A mid-length article takes 40–60 minutes and about 40
model calls.

## Where things are

- `ROOT` is this repository's root: `$CLAUDE_PLUGIN_ROOT` when installed as a plugin,
  otherwise the checkout that contains this file. All code and prompts are under `ROOT`.
- Runs are written to `runs/<YYYY-MM-DD-name>/<NN-wpid-slug>/` **in the current working
  directory** (in a checkout of this repository that is `ROOT/runs/`). Never write runs
  into a plugin install directory. `<run-dir>` below is that folder's absolute path.
- Google Docs need either the [`gdoc`](https://github.com/LucaDeLeo/gdoc) CLI
  (`deliver.py` calls it) or the gdoc MCP tools (Claude Tag). Same operations either way:
  create a Doc from Markdown, `suggest`, `comment`, `reply`, `resolve`.
- Before the first run: `cd ROOT/article-to-google-doc && uv sync`; Pandoc on `PATH`
  (`apt-get install -y pandoc` in a fresh sandbox).

## Inputs

- A published URL such as `https://example.org/articles/example/`.
- A Google Doc link: never edit the original. Copy it into the runs Drive folder as
  "<title> — review <date>", export the copy to `<run-dir>/capture/article.md`
  (`gdoc cat DOC_ID > …` or the MCP read tool), and write a minimal
  `<run-dir>/capture/manifest.json` with `wordpress.title`, `wordpress.id` (the Doc id),
  `wordpress.modified`, `canonical_url`, `outputs.markdown`. Skip step 1; all suggestions
  and comments go in the copy.
- A Drive folder id for the delivered Doc; ask if none is configured.

## Steps

1. **Capture.** `cd ROOT/article-to-google-doc && uv run article-to-google-doc URL --output-dir <run-dir>/capture --skip-images`.
   It stops if its checks fail (some problem profiles fail the footnote-callout check);
   pick another article or fix the extractor. Never review an unchecked capture.
2. **Prepare.** `python3 ROOT/pipeline/prepare.py <run-dir>/capture <run-dir>` splits
   structural units, lists every external link with a live HEAD signal, batches links by
   section (≤25 per call), and writes `bundle.json`. Then
   `python3 ROOT/pipeline/build_workflow.py <run-dir>` prints the Workflow args.
3. **Run the ten stages** — try the Workflow tool first, fall back to manual if it is
   not available in your session.
   - *Workflow:* `Workflow({scriptPath: "ROOT/pipeline/run.workflow.js", args: <printed args>})`.
     Stage agents read prompt, article, inputs and schema from disk and save JSON to
     `<run-dir>/stages/`; Haiku relays the two harness commands between stages; a `null`
     return is retried once. If it fails, fix the cause and resume with `resumeFromRunId`
     (same session only — across sessions, rerun; finished stages are on disk).
   - *Manual:* same order as the script — 01 → (02, 03, 04, 07 in parallel) → 05 → 06 →
     08 → 09 → 10. For each stage `NN`: `python3 ROOT/pipeline/harness.py inputs <run-dir> NN`
     prints the batches; for each batch run one agent (the Agent tool, or yourself for a
     single batch) with the wording of `envelope()` in `run.workflow.js`: read
     `ROOT/prompts/NN-*.md`, fill its placeholders from `bundle.json` identity, the article
     file, the batch's input file and `<run-dir>/inputs/NN-schema.json`, save the JSON to
     `<run-dir>/stages/<batch-id>.json`. Then `python3 ROOT/pipeline/harness.py join <run-dir> NN`.
     Only stages 02–04 may use the web.
   - Models: Opus for 01–04, 07, 09; Fable for 05, 06, 08, 10 (fall back to Opus and record
     it in the run's README).
4. **Check the joins.** Each `<run-dir>/joined/NN.json` has a `harness_summary`: `missing`
   must be empty and `located` almost all `exact`. `unlocated` passages mean the reviewer
   paraphrased; they deliver as comments, never as suggestions.
5. **Deliver.** With the CLI: `python3 ROOT/pipeline/deliver.py <run-dir> --folder <id>`
   (`GDOC_ACCOUNT` selects the account; `--doc ID` with an existing `delivery.json` redoes
   only failed items). With the MCP tools, apply the same rules by hand from
   `joined/09.json` and `joined/10.json`: create the Doc from `capture/article.md`; one
   suggested edit per retained `change`, changing only the words that differ, widened until
   the anchor is unique; one plain comment per reviewed unit — `Problem`, `Why`, `Sources`
   as links, no tags or grade labels, overflow continued as a reply — anchored on text that
   survives acceptance; resolve the comment for every `no_change`, `unverifiable`, pruned
   or rejected target so the editor sees only open work.
6. **Record.** `python3 ROOT/pipeline/build_review.py <run-dir> --doc-url <url>` writes
   `review.md`. Add the Doc link, configuration and outcome to the run’s `README.md`.
   Commit the run on the `runs` branch of your own writable repository, never on
   `main` — `main` is what plugin installs download and contains code and documentation.
   In Claude Tag, check out `runs` at step 2 and push `stages/` and `joined/` as
   they finish: the sandbox is released a few minutes after a quiet turn and a later turn
   must be able to resume from the branch.

Report the Doc link and the grade line from `review.md` (`clean`, `bounded`, or
`structural`, with one line on what it means). For a Google Doc input, also offer two
follow-ups: accept the suggestions in the copy and answer relevant comments there, or
carry the accepted edits into the original on request.
