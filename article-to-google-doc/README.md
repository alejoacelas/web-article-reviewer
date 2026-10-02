# Article to Google Doc

Turn one public WordPress article URL into checked Markdown with local images, then
optionally create a native Google Doc.

The extractor resolves the URL against the site's public WordPress content types. It
uses WordPress `content.rendered` for the article and the public page for content that
WordPress adds only when rendering: inline footnote callouts, full footnote text,
problem-profile summaries, and embeds. It makes links absolute, downloads the largest
declared image variant, collapses responsive duplicates, and converts the result with
Pandoc. It does not scrape navigation, newsletter forms, or other page furniture.

## Run it

```sh
cd article-to-google-doc
uv run article-to-google-doc \
  https://example.org/articles/example/ \
  --output-dir captures/example
```

The output folder contains:

- `article.md` — the reviewable article, source metadata, notes, links and images;
- `images/` — downloaded source assets;
- `source.html` — the cleaned HTML immediately before Markdown conversion;
- `manifest.json` — WordPress identity, hashes, asset records, footnote line mappings,
  represented embeds, deliberate omissions, and conversion checks.

Add `--skip-images` for a quick text-and-structure pass that retains remote image URLs.
Add `--create-doc` to create a native Google Doc after the checks pass:

```sh
uv run article-to-google-doc ARTICLE_URL --create-doc --account you@example.org
```

Select your account with `--account` or `GDOC_ACCOUNT`. Use `--folder DRIVE_FOLDER_ID` to place the
Doc in a particular folder.

## What the checks establish

The manifest compares the cleaned HTML with a Markdown round trip. It requires the
same normalised visible text, link-target multiset, image references and alt text,
heading sequence, list-item count, table count and blockquote count. These checks find
conversion loss. It also requires every unique public-page footnote callout to appear
in Markdown and point to a captured definition, and every public iframe to survive as
an explicit link. These checks do not establish that the article itself is correct.

Footnotes use ordinary internal links: a claim ends in `[3](#fn-3)`, and the third
definition contains `<span id="fn-3"></span>`. `manifest.json` records the Markdown
line for both ends, so a reviewer can map them without guessing.

The REST API must be available at `/wp-json/wp/v2/`. Public-page footnote and
summary extraction uses theme-specific selectors; check the capture against the
rendered page when adapting it to a new theme.

## Test

```sh
uv run --with pytest pytest -q
```
