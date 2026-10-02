# Review links and citations

Review only the assigned link targets, using the complete immutable article for
context. Open every destination on the live web and answer two questions: does the link
still reach the intended page, and does that page support the claim the citation is
attached to (usually the anchor text or the clause it sits in)?

Ask what the cited claim is for. If it tells the reader how things stand now, a source
whose figure the same publisher has since superseded no longer supports it, whatever
the sentence's tense; if it records what happened or what someone said, the original
source still supports it.

First state the reading a careful reader would take of that claim today. Then judge only
that reading by one standard:

- `change` when the destination is broken, wrong, or superseded and a canonical
  replacement is supported; or when the page does not support the claim and the
  smallest honest fix is a URL swap or a trim of the sentence to what the source
  establishes. Prefer changing only the URL and keep the visible anchor text. A
  destination is superseded only when it no longer serves as the cited source; a newer
  edition, journal version, or fresher dataset whose relevant content is unchanged is
  `no_change`.
- `editorial_escalation` when the source fails to support the claim and no URL swap
  or trim honestly fixes it. Write an anchored comment for the editor; suggest no
  article text.
- `no_change` when the destination and its support are fine, or when the article's
  wording is accurate under the stated reading. A redirect that lands on the intended
  page is `no_change`; never change a URL only to follow a redirect.
- `unverifiable` only after you have actually tried: timeouts, bot blocks, paywalls, or
  sources you could not locate. Say what you tried.

Do not review links outside the assigned list and do not propose factual, contextual,
stylistic, or structural changes. There is no proposal cap and no later pruning pass;
return every change that meets the standard.

Return one entry per assigned target id matching `[OUTPUT_SCHEMA_JSON]`.

## Article identity

[ARTICLE_IDENTITY_JSON]

## Assigned link targets

[LINK_TARGETS_JSON]

## Full immutable article

[ARTICLE_TEXT]

## Output schema

[OUTPUT_SCHEMA_JSON]
