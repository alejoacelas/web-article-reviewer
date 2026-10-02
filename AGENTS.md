# Web article reviewer

This repository contains a public WordPress article capture tool and a ten-stage
review pipeline that delivers suggested edits to Google Docs.

- To review an article, follow the `review-article` skill
  ([skills/review-article/SKILL.md](skills/review-article/SKILL.md)); it is the whole
  procedure. Before running, `cd article-to-google-doc && uv sync`; Pandoc must be on
  `PATH` (`apt-get install -y pandoc` in a fresh sandbox).
- To change what counts as an edit, read [DESIGN.md](DESIGN.md) first; prompts implement it.
- Every run writes to `runs/<YYYY-MM-DD-name>/<NN-wpid-slug>/` and is committed on the branch
  `runs`, not `main`; record the configuration and outcome in the run’s `README.md`.
- `.claude/skills/review-article` is a symlink to `skills/review-article` so the same file
  serves a checkout and a plugin install. Edit the skill in `skills/`.

## In Claude Tag (Slack)

- Reply in the thread at once: the review takes about an hour and you will tag the
  requester when the Doc is ready. Post a checklist of the six steps and edit it as stages
  finish; answer "how's it going?" from it.
- Use the gdoc MCP tools for everything in Google Docs — reading, creating, suggestions,
  comments — never the Drive connector.
- Work on the `runs` branch from the start and push `<run-dir>/stages/`
  and `joined/` as they complete; never commit runs to `main`. The sandbox is released a
  few minutes after a quiet turn and a later turn must be able to resume from the branch.
- When done, post the Doc link and the grade (`clean`, `bounded`, or `structural`) with one
  line on what it means, and tag the requester.
