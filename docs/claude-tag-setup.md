Setup guide · August 2026
# Web Article Reviewer on Claude Tag

How to make `@Claude review https://example.org/…` in a Slack channel produce a Google Doc with tracked suggestions and anchored comments, using the ten-stage article reviewer. Written for an Owner of the Claude Team plan.

## What you are wiring together

A Claude Tag thread runs in a fresh Ubuntu VM — the same engine as Claude Code on the web — with Python, `uv`, Node and `gh` preinstalled. It clones a GitHub repository you have granted, loads that repo's `CLAUDE.md` and `.claude/skills/`, and runs code. Every outbound request crosses Agent Proxy, which blocks hosts nobody allowed and injects credentials for the hosts a connection covers, so the sandbox never holds a key.
The reviewer needs four things from that environment, and each has one place to be configured:

| Need | Where it is set | Who |
|---|---|---|
| Pandoc, and the freedom to open any cited URL | An organization-shared **cloud environment** pinned on the channel | Owner |
| The pipeline code and prompts | A **repository grant** on the channel's Access bundle | Owner |
| Creating Docs, suggestions and comments | The **gdoc remote MCP**, connected on the channel's Access bundle | Owner |
| Knowing to do all this when someone pastes a URL | The repo's **skill** and `CLAUDE.md`, plus a short **custom instruction** on the channel naming the repo | Owner or channel member |

## Before you start: two checks in Slack

Both run in a fresh thread in the channel you will use. They perform an action rather than asking Claude to describe itself, so the answer is verifiable.

### Check 1 — is the Workflow (ultracode) tool available?

The pipeline script is written for Claude Code's `Workflow` tool. Nothing in the Claude Tag docs says whether the sandbox exposes it. Paste this:

```
@Claude Call the tool named Workflow — not the Agent tool, not Bash — with this exact script:

export const meta = { name: 'probe', description: 'probe', phases: [{ title: 'Probe' }] }
phase('Probe')
const r = await parallel([
  () => agent('Run `hostname` and return only its output.', { label: 'a', model: 'opus' }),
  () => agent('Run `date -u +%s` and return only its output.', { label: 'b', model: 'haiku' }),
])
return { hosts: r, ok: true }

Post the tool's raw result including the run ID (it starts with wf_) and the phases it reported.
If no tool named Workflow exists in this session, say exactly that and list the names of the tools you do have.
```

A `wf_…` run ID proves the tool exists and that per-agent model selection works. A tool list without `Workflow` means the pipeline driver must be ported to plain Python before it can run in Tag (see *Open items*).

### Check 2 — can it open an arbitrary page?

```
@Claude Using curl from your sandbox (not web search), fetch https://www.bls.gov/oes/ and https://www.nature.com/ and paste the HTTP status code and the  of each. If a host is blocked, quote the exact blocked-host message.
```

The link reviewer opens every cited destination; a blocked host here means the environment's network level must be raised (step 1).

## Setup

- ### Create the environment and pin it on the channel

**claude.ai/admin-settings** → Cloud environments → Add cloud environment (organization-shared). Then **claude.ai/admin-settings/claude-tag** → Claude Tag's access → Slack → the channel → Advanced → Environment.
Name it `web-article-reviewer`. Network access: **Full** (any domain) — the reviewer must open cited pages, and the default Trusted level reaches only package registries and GitHub. Setup script:

```
apt-get update && apt-get install -y pandoc
```

The script runs once, then the filesystem is snapshotted and reused for about seven days, so Pandoc is already on disk when later sessions start. Keep it under five minutes; add nothing secret — environment variables and scripts are readable by every session.
If your organization cannot use Full, add the Domains you expect on the bundle's **Domains** tab (e.g. `example.org`, `*.example.org`, `web.archive.org`) and accept that unlisted sources are checked through web search only. When a request is blocked, Claude names the host in the thread; add it and retry in the same thread after a minute.

- ### Grant the repository

**claude.ai/admin-settings/claude-tag** → Access bundles → the channel's bundle → **Repositories** → add `YOUR_ORG/web-article-reviewer` (your own writable copy; a grant lets Claude push run branches back). Requires the Claude GitHub App to be linked at **claude.ai/admin-settings/github** by someone who is both a GitHub org owner and a Claude Owner.
Granting makes the repo available; it is cloned only when a message names it (the skill and custom instructions below do that). After the clone, the repo's `CLAUDE.md`, `.claude/rules/*.md`, `.claude/skills/` and `.claude/settings.json` hooks load. The repo's `.mcp.json` is never loaded — MCP servers come only from plugins.
The repository's `CLAUDE.md` points to `AGENTS.md`, which carries the install steps as preconditions of the work ("before running the reviewer, run `uv sync` in `article-to-google-doc/`"); the sandbox is fresh each session, so they run every time.

- ### Connect the gdoc remote MCP

Bundle → **Credentials** → Connect → Custom tool → credential type **MCP Connector**, Allowed websites = the gdoc MCP host, and declare the server so the channel's sessions see its tools. The repository's own `.mcp.json` would not load — a granted repo's MCP config never does — so this is bundle configuration, not repository content. Then share the review Drive folder with the account the MCP acts as.
Verify in a new thread: `@Claude using the gdoc tools, create a Doc titled "gdoc probe" in folder <ID>, add one suggested edit and one anchored comment, and post the link.` The credential row switches from **Never used** after the first call.

- ### Add the channel instruction

Everything Claude needs to know is in the repository and loads when it clones it: `skills/review-article/SKILL.md` is the procedure, and `AGENTS.md` has an *In Claude Tag* section (reply at once, keep a checklist, gdoc tools only, push stages to a branch, tag the requester with the grade). Keep it there so a change is one commit, not an admin edit. The channel's custom instructions carry only what the repository can't: when to trigger, which repository, and channel configuration such as the Drive folder.
**claude.ai/admin-settings/claude-tag** → Slack → the channel → Custom instructions (or the **Configure** link in any Claude reply footer).

```
When someone posts a link to a published example.org article or to a Google Doc, clone
the web-article-reviewer repository and follow its review-article skill and CLAUDE.md.
Deliver into the Drive folder "Article reviewer" (id YOUR_DRIVE_FOLDER_ID).
```

- ### Pre-approve the routine actions

Channel → Advanced → **Auto mode allow rules** → Add rule (one plain sentence each, up to 50).

```
Running the web-article-reviewer pipeline from its repository, including installing its
dependencies with uv and apt, is an approved workflow in this channel.

Creating Google Docs in the "Article reviewer" Drive folder and adding suggested edits
and comments to Docs Claude created there is an approved workflow in this channel.
```

Sessions run in auto mode; without these, the permission checker may stop a long run mid-way.

- ### Set the model and test

Channel → Advanced → **Default model**: the most capable Opus your organization allows. Effort is not configurable in Tag.
Start a new thread (configuration never reaches a running one):

```
@Claude review https://example.org/articles/example/ with the web-article-reviewer
repository and post the Google Doc link when the review is delivered.
```

A first run takes 40–60 minutes for a mid-length article and posts a checklist it edits in place, so a quiet thread is normal. Ask "how's it going?" in the thread to get a status reply. The sandbox is released a few minutes after the turn ends, so the run must finish within one turn or push its intermediate files to the repo as a branch.

## Open items

Decided by Check 1
**Workflow tool.** If absent, `pipeline/run.workflow.js` has to become a Python driver that calls the Claude API directly with the same prompts, schemas and harness. Half a day; it also makes the pipeline runnable from a routine or a cron.
Model availability
**Stage models.** The channel model list is "Opus and Sonnet models" filtered by the org's Claude Code policy. Fable, used for drafting, polishing, pruning and grading, may not be selectable in Tag; if not, those stages fall back to Opus and the run config records it.
Decided by step 3's probe
**Suggested edits through the gdoc MCP.** Suggestion mode uses a Docs API developer preview; the remote MCP already has that function, and the probe confirms it works under the connection's account. If it does not, the fallback is a `.docx` with tracked changes uploaded once through Drive with conversion — Google turns tracked changes into suggestions and comments into anchored comments.
Duration
**Session length.** The docs enforce no session limit but release the sandbox after a quiet period. A run that spans several turns should write `stages/` and `joined/` to a branch as it goes, as the good-habits page recommends for long tasks.

## Reference

- [Claude Tag for Claude Code users](https://claude.com/docs/claude-tag/concepts/for-claude-code-users) — what loads from a repo, hooks in the sandbox, no per-session effort setting
- [Configure the environment for a scope](https://claude.com/docs/claude-tag/admins/customize#configure-the-environment-for-a-scope) — setup script, network level, pinning
- [Cloud environments](https://code.claude.com/docs/en/cloud-environments) — preinstalled tools, Trusted allowlist, five-minute setup script, seven-day cache
- [Configure GitHub access](https://claude.com/docs/claude-tag/admins/configure-github) — repository grants, install steps in CLAUDE.md
- [Add a custom MCP server](https://claude.com/docs/claude-tag/admins/connections/custom#add-a-custom-mcp-server) — how a remote MCP reaches a channel
- [Give Claude access](https://claude.com/docs/claude-tag/admins/add-connections) — Domains, Full access, allow-all egress
- [How agent identity works](https://claude.com/docs/claude-tag/concepts/agent-identity) — Agent Proxy and the search/fetch split

Companion to the web-article-reviewer repository's review-article skill. Facts reflect the Claude Tag docs as read on 28 August 2026; the product is in public beta and numbers may change.
