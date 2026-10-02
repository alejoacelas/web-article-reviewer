# Article refresh

Find evidence-backed ways a published article should be updated — broken or superseded
links, citations that no longer support their sentence, narrow facts a current primary
source contradicts, and later developments that change how a passage reads — and deliver
them as a Google Doc with minimal tracked suggestions and anchored comments an editor can
accept or reject one by one.

The prompts and pipeline are site-agnostic; the capture step uses WordPress.

## What you get

Give it a URL; it returns a Doc. Each retained change is a suggested edit covering only the
words that differ, with a comment beside it: `Problem`, `Why`, `Sources`. Other checked
targets are recorded as resolved comments, so the history is kept without cluttering review.

## What it will and won't change

[DESIGN.md](DESIGN.md) is the contract. In short: it repairs a link only when the
destination is demonstrably broken, wrong, or superseded; corrects a citation when the
source does not support the sentence; corrects a narrow fact when a current primary source
contradicts it; and raises a later development only when verified evidence would make a
careful reader read a passage differently. It never suggests style, tone, structure, or
fresher-but-equivalent sources, and it never decides that an edit should be published.

## Run it

Prerequisites: [Claude Code](https://code.claude.com), `uv`, Pandoc, and one way to write
Google Docs — an authenticated [`gdoc`](https://github.com/LucaDeLeo/gdoc) CLI, or the gdoc
remote MCP (what Claude Tag uses). The Workflow tool (ultracode) runs the ten stages in
parallel; without it the skill runs them one agent at a time.

Install as a plugin, from any project:

```
/plugin marketplace add alejoacelas/web-article-reviewer
/plugin install review-article@web-article-reviewer
/review-article https://example.org/articles/example/
```

or clone this repository and run the same command inside it. Runs are written to `runs/`
in the current directory. A mid-length article takes 40–60 minutes and about 40 model
calls: Opus for targeting, link and fact review, discovery, the purpose map, and merge;
Fable (or Opus) for drafting, polishing, pruning, and grading. To run it from Slack, see
[docs/claude-tag-setup.md](docs/claude-tag-setup.md).

## How it works

Ten prompts ([`prompts/`](prompts/README.md)), one Workflow per article
([`pipeline/`](pipeline/README.md)):

1. The harness lists every link; prompt 01 lists every narrow factual claim.
2. Prompts 02 (links and citations) and 03 (facts) review each target with the full
   article as context, batched by section, opening every source live.
3. Prompt 04 discovers later developments; 05 drafts the smallest honest fix; 06 polishes;
   07 maps what each paragraph argues; 08 prunes anything that does not change that map.
4. Prompt 09 validates spans and evidence mechanically and merges overlaps; prompt 10
   grades each item's blast radius and the article as clean, bounded, or structural.

Every stage returns only the fields it adds, keyed by unit id; the harness joins them onto
the immutable unit and locates every quoted passage in the article, so nothing is
paraphrased into the Doc.

## Adapt it to your site

- `article-to-google-doc/` resolves a public article URL through WordPress and the public
  page and checks the Markdown against the rendered text. The REST API must be
  available at `/wp-json/wp/v2/`.
  Theme-specific footnotes and summaries may need adjustments in `capture.py`.
  For another CMS, produce `article.md` and a
  `manifest.json` with `wordpress.title`, `wordpress.id`, `wordpress.modified`,
  `canonical_url`, and `outputs.markdown` any way you like.
- Prompts, schemas, and harness need no change. Configuration is the Drive folder id and,
  for delivery, `GDOC_ACCOUNT`.

## Repository map

| Path | What |
|---|---|
| `DESIGN.md` | The edits we want and don't, and the review flow |
| `docs/` | Conceptual units, edit-size grading, Claude Tag setup |
| `prompts/` | The ten stage prompts |
| `pipeline/` | Harness, schemas, Workflow script, delivery, review builder |
| `article-to-google-doc/` | URL → checked Markdown (its own `uv` project) |
| `skills/review-article/` | The skill: the whole procedure from URL to Doc (`.claude/skills/` symlinks here) |
| `.claude-plugin/` | Plugin and marketplace manifests, so the repository installs as a Claude Code plugin |
