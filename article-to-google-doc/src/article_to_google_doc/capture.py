"""Resolve a public article URL through WordPress and preserve its article content."""

from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import re
import urllib.error
import urllib.request
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote, urlencode, urljoin, urlparse, urlunparse

import pypandoc
from bs4 import BeautifulSoup, Tag

USER_AGENT = "article-to-google-doc/0.1"
FIELDS = "id,link,modified,slug,title,content"
EXCLUDED_REST_BASES = {
    "media",
    "menu-items",
    "blocks",
    "font-families",
    "global-styles",
    "navigation",
    "templates",
    "template-parts",
}
TYPE_PRIORITY = {
    name: index
    for index, name in enumerate(
        (
            "article",
            "careerguidepage",
            "ai_career_guide_page",
            "problem_profile",
            "posts",
            "pages",
            "career_profile",
            "case_study",
            "career_report",
            "skill_set",
            "definition",
            "series",
            "podcast",
            "podcast_after_hours",
            "video",
        )
    )
}
SAFE_STEM = re.compile(r"[^a-z0-9]+")


class CaptureError(RuntimeError):
    """The supplied page could not be captured without guessing."""


@dataclass(frozen=True)
class Response:
    body: bytes
    content_type: str
    final_url: str


def fetch(url: str, *, accept: str = "*/*", timeout: int = 45) -> Response:
    encoded = quote(url, safe=":/%?&=#[]!$&'()*+,;@")
    request = urllib.request.Request(
        encoded, headers={"Accept": accept, "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return Response(
                response.read(), response.headers.get_content_type(), response.geturl()
            )
    except urllib.error.HTTPError as error:
        raise CaptureError(f"{url} returned HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise CaptureError(f"could not fetch {url}: {error.reason}") from None


def fetch_json(url: str) -> Any:
    response = fetch(url, accept="application/json")
    try:
        return json.loads(response.body)
    except json.JSONDecodeError as error:
        raise CaptureError(f"{url} did not return JSON") from error


def canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    if not host or parsed.username or parsed.password:
        raise CaptureError("URL must have a hostname and no embedded credentials")
    if parsed.scheme not in {"http", "https"}:
        raise CaptureError("URL must use HTTP or HTTPS")
    path = re.sub(r"/{2,}", "/", unquote(parsed.path))
    path = "/" if path == "/" else path.rstrip("/") + "/"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))


def url_slug(value: str) -> str:
    path = urlparse(canonical_url(value)).path.rstrip("/")
    if not path:
        raise CaptureError("the site homepage is not an article")
    return path.rsplit("/", 1)[-1]


def _candidate(site: str, rest_base: str, slug: str) -> list[dict[str, Any]]:
    query = urlencode({"slug": slug, "per_page": 100, "_fields": FIELDS})
    url = f"{site}/wp-json/wp/v2/{rest_base}?{query}"
    try:
        result = fetch_json(url)
    except CaptureError:
        return []
    if not isinstance(result, list):
        return []
    return [{**record, "rest_base": rest_base, "rest_url": url} for record in result]


def _resolve_rest(value: str) -> dict[str, Any]:
    requested = canonical_url(value)
    slug = url_slug(requested)
    parsed = urlparse(requested)
    site = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    types = fetch_json(f"{site}/wp-json/wp/v2/types")
    if not isinstance(types, dict):
        raise CaptureError("WordPress types endpoint returned an unexpected response")
    rest_bases = sorted(
        {
            str(record.get("rest_base"))
            for record in types.values()
            if record.get("rest_base")
            and str(record["rest_base"]) not in EXCLUDED_REST_BASES
            and "(?P<" not in str(record["rest_base"])
        },
        key=lambda name: (TYPE_PRIORITY.get(name, 10_000), name),
    )
    if not rest_bases:
        raise CaptureError("WordPress exposes no supported article content types")
    matches: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(10, len(rest_bases))) as pool:
        futures = {pool.submit(_candidate, site, rest_base, slug): rest_base for rest_base in rest_bases}
        for future in as_completed(futures):
            matches.extend(future.result())
    exact = [record for record in matches if canonical_url(record["link"]) == requested]
    if len(exact) != 1:
        candidates = sorted({record.get("link", "") for record in matches})
        detail = f"; slug candidates: {candidates}" if candidates else ""
        raise CaptureError(f"could not uniquely resolve {requested}{detail}")
    return exact[0]


def resolve_article(value: str) -> dict[str, Any]:
    """Follow a public URL, then resolve its canonical WordPress REST record."""
    response = fetch(canonical_url(value), accept="text/html")
    return _resolve_rest(response.final_url)


def _block_text_without_callouts(block: Tag) -> str:
    clone_soup = BeautifulSoup(str(block), "lxml")
    clone = clone_soup.find(block.name)
    assert clone is not None
    for callout in clone.select('a[id^="fn-ref-"][href^="#fn-"]'):
        callout.decompose()
    return normalized_match_text(clone.get_text(" ", strip=True))


def public_callout_blocks(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Collect the smallest public-page blocks containing rendered note callouts."""
    content = soup.select_one("main") or soup.select_one("article")
    if content is None:
        raise CaptureError("public page has no recognisable article body")
    parents: dict[int, Tag] = {}
    for callout in content.select('a[id^="fn-ref-"][href^="#fn-"]'):
        block = callout.find_parent(
            ["p", "li", "h2", "h3", "h4", "h5", "h6", "blockquote", "td", "th"]
        )
        if block is None:
            raise CaptureError(f"footnote callout {callout.get('id')} has no text block")
        parents[id(block)] = block
    records = []
    for block in parents.values():
        callouts = [
            {
                "reference_id": str(anchor.get("id")),
                "target": str(anchor.get("href")),
                "label": anchor.get_text(" ", strip=True),
            }
            for anchor in block.select('a[id^="fn-ref-"][href^="#fn-"]')
        ]
        records.append(
            {
                "tag": block.name,
                "text_without_callouts": _block_text_without_callouts(block),
                "html": str(block),
                "callouts": callouts,
            }
        )
    return records


def public_page(
    url: str,
) -> tuple[
    bytes,
    str,
    list[dict[str, str]],
    list[dict[str, Any]],
    list[str],
    list[str],
]:
    response = fetch(url, accept="text/html")
    soup = BeautifulSoup(response.body, "lxml")
    notes: list[dict[str, str]] = []
    seen: set[str] = set()
    for element in soup.select('li[id^="fn-"]'):
        anchor = f"#{element.get('id')}"
        if anchor in seen:
            raise CaptureError(f"duplicate public footnote {anchor}")
        seen.add(anchor)
        for backlink in element.select("a.fn-return"):
            backlink.decompose()
        body = element.decode_contents().strip()
        if not body:
            raise CaptureError(f"empty public footnote {anchor}")
        notes.append({"href": anchor, "html": body})
    supplements = [str(element) for element in soup.select(".problem-profile__summary")]
    main = soup.select_one("main") or soup.select_one("article")
    public_embeds: list[str] = []
    if main:
        for frame in main.select("iframe"):
            source = str(frame.get("src") or frame.get("data-src") or "")
            source = absolute_url(source, response.final_url)
            if source and source not in public_embeds:
                public_embeds.append(source)
    return (
        response.body,
        response.final_url,
        notes,
        public_callout_blocks(soup),
        supplements,
        public_embeds,
    )


def merge_public_callouts(body: Tag, blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Replace matching REST blocks with their public-page callout-bearing versions."""
    candidates: dict[tuple[str, str], list[Tag]] = {}
    for tag in ("p", "li", "h2", "h3", "h4", "h5", "h6", "blockquote", "td", "th"):
        for element in body.find_all(tag):
            key = (tag, normalized_match_text(element.get_text(" ", strip=True)))
            candidates.setdefault(key, []).append(element)
    merged: list[dict[str, str]] = []
    used: set[int] = set()
    expected_reference_ids = {
        item["reference_id"] for record in blocks for item in record["callouts"]
    }
    placed_reference_ids: set[str] = set()
    for record in blocks:
        active_callouts = [
            item
            for item in record["callouts"]
            if item["reference_id"] not in placed_reference_ids
        ]
        if not active_callouts:
            continue
        key = (record["tag"], record["text_without_callouts"])
        target = next(
            (candidate for candidate in candidates.get(key, []) if id(candidate) not in used),
            None,
        )
        if target is None:
            continue
        fragment = BeautifulSoup(record["html"], "lxml").find(record["tag"])
        assert fragment is not None
        for anchor in fragment.select('a[href^="#fn-"]'):
            if str(anchor.get("id")) in placed_reference_ids:
                anchor.decompose()
                continue
            anchor.attrs = {"href": anchor["href"]}
            for superscript in anchor.select("sup"):
                superscript.unwrap()
        used.add(id(target))
        target.replace_with(fragment)
        merged.extend(active_callouts)
        placed_reference_ids.update(item["reference_id"] for item in active_callouts)
    missing = sorted(expected_reference_ids - placed_reference_ids)
    if missing:
        raise CaptureError(f"could not place public footnote callouts {missing}")
    return merged


def absolute_url(value: str, base_url: str) -> str:
    value = html.unescape(value.strip())
    if not value or value.startswith(("#", "mailto:", "tel:", "data:")):
        return value
    return urljoin(base_url, value)


def largest_srcset_url(value: str, base_url: str) -> str | None:
    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(value.split(",")):
        fields = part.strip().rsplit(maxsplit=1)
        if not fields:
            continue
        score = 0.0
        if len(fields) == 2:
            descriptor = fields[1].lower()
            try:
                if descriptor.endswith("w"):
                    score = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    score = float(descriptor[:-1]) * 10_000
            except ValueError:
                score = 0.0
        candidates.append((score, index, absolute_url(fields[0], base_url)))
    return max(candidates, default=(0, 0, ""))[2] or None


def image_source(image: Tag, base_url: str) -> str | None:
    srcset = image.get("srcset") or image.get("data-srcset")
    if srcset:
        selected = largest_srcset_url(str(srcset), base_url)
        if selected:
            return selected
    for attribute in ("src", "data-src", "data-lazy-src"):
        value = image.get(attribute)
        if value and not str(value).startswith("data:"):
            return absolute_url(str(value), base_url)
    return None


def safe_image_name(index: int, source_url: str, content_type: str) -> str:
    stem = Path(unquote(urlparse(source_url).path)).stem.lower()
    stem = SAFE_STEM.sub("-", stem).strip("-")[:60] or "image"
    suffix = Path(unquote(urlparse(source_url).path)).suffix.lower()
    if not suffix or len(suffix) > 6:
        suffix = mimetypes.guess_extension(content_type) or ".bin"
    if suffix == ".jpe":
        suffix = ".jpg"
    return f"{index:02d}-{stem}{suffix}"


def image_caption(image: Tag) -> str:
    figure = image.find_parent("figure")
    if figure:
        caption = figure.find("figcaption")
        if caption:
            return caption.get_text(" ", strip=True)
    return ""


def prepare_html(
    article: dict[str, Any],
    notes: list[dict[str, str]],
    callout_blocks: list[dict[str, Any]],
    *,
    asset_dir: Path,
    reference_root: str,
    download_images: bool = True,
    downloader: Callable[[str], Response] = fetch,
) -> tuple[
    str,
    list[dict[str, Any]],
    list[dict[str, str]],
    dict[str, int],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    base_url = article["link"]
    soup = BeautifulSoup(article["content"]["rendered"], "lxml")
    body = soup.body or soup
    callouts = merge_public_callouts(body, callout_blocks)
    if notes:
        heading = soup.new_tag("h2", id="notes-and-references")
        heading.string = "Notes and references"
        body.append(heading)
        ordered = soup.new_tag("ol", attrs={"data-capture-section": "footnotes"})
        for note in notes:
            item = soup.new_tag("li")
            item["id"] = note["href"].removeprefix("#")
            fragment = BeautifulSoup(note["html"], "lxml")
            fragment_body = fragment.body or fragment
            for child in list(fragment_body.contents):
                item.append(child.extract())
            ordered.append(item)
        body.append(ordered)
    embeds: list[dict[str, str]] = []
    for frame in list(body.select("iframe")):
        source_url = absolute_url(
            str(frame.get("src") or frame.get("data-src") or ""), base_url
        )
        if source_url:
            domain = urlparse(source_url).hostname or "source"
            label = str(frame.get("title") or f"Embedded content from {domain}")
            paragraph = soup.new_tag("p")
            linked = soup.new_tag("a", href=source_url)
            linked.string = label
            paragraph.append(linked)
            frame.replace_with(paragraph)
            embeds.append({"source_url": source_url, "label": label})
        else:
            frame.decompose()
    intentional_omissions = {
        "scripts": len(body.select("script")),
        "styles": len(body.select("style")),
        "forms": len(body.select("form")),
        "buttons": len(body.select("button")),
        "navigation": len(body.select("nav")),
        "audio_players": len(body.select("#audio-player")),
        "tables_of_contents": len(body.select("#toc_container")),
    }
    for unwanted in body.select(
        "script, style, form, button, nav, #audio-player, #toc_container"
    ):
        unwanted.decompose()
    for fallback in body.find_all("noscript"):
        fallback.unwrap()
    for linked in body.select("a[href]"):
        linked["href"] = absolute_url(str(linked["href"]), base_url)

    asset_dir.mkdir(parents=True, exist_ok=True)
    images: list[dict[str, Any]] = []
    source_images: list[Tag] = []
    duplicate_images: list[dict[str, Any]] = []
    seen_images: set[tuple[str, str, str]] = set()
    for image in body.find_all("img"):
        source_url = image_source(image, base_url)
        if source_url:
            key = (
                source_url,
                normalized_label(str(image.get("alt") or "")),
                normalized_label(image_caption(image)),
            )
            if key in seen_images:
                duplicate_images.append(
                    {"source_url": source_url, "alt": key[1], "caption": key[2]}
                )
                figure = image.find_parent("figure")
                if figure and len(figure.find_all("img")) == 1:
                    figure.decompose()
                else:
                    image.decompose()
                continue
            seen_images.add(key)
            source_images.append(image)
        else:
            image.decompose()
    for index, image in enumerate(source_images, 1):
        source_url = image_source(image, base_url)
        assert source_url is not None
        record: dict[str, Any] = {
            "position": index,
            "section": "notes" if image.find_parent(attrs={"data-capture-section": "footnotes"}) else "article",
            "source_url": source_url,
            "alt": str(image.get("alt") or ""),
            "caption": image_caption(image),
            "downloaded": False,
        }
        if download_images:
            try:
                result = downloader(source_url)
                name = safe_image_name(index, source_url, result.content_type)
                destination = asset_dir / name
                destination.write_bytes(result.body)
                reference = f"{reference_root}/{name}"
                image["src"] = reference
                record.update(
                    {
                        "downloaded": True,
                        "local_path": str(destination),
                        "markdown_reference": reference,
                        "content_type": result.content_type,
                        "bytes": len(result.body),
                        "sha256": hashlib.sha256(result.body).hexdigest(),
                    }
                )
            except CaptureError as error:
                image["src"] = source_url
                record.update({"markdown_reference": source_url, "error": str(error)})
        else:
            image["src"] = source_url
            record["markdown_reference"] = source_url
        for attribute in (
            "srcset", "sizes", "data-src", "data-srcset", "data-lazy-src", "loading", "decoding"
        ):
            image.attrs.pop(attribute, None)
        images.append(record)

    for caption in list(body.find_all("figcaption")):
        if not normalized_label(caption.get_text(" ", strip=True)):
            caption.decompose()
            continue
        caption.name = "p"
        prefix = soup.new_tag("em")
        prefix.string = "Caption: "
        caption.insert(0, prefix)
    # Preserve every in-article destination that the article actually links to.
    # Pandoc drops HTML ids on headings and paragraphs, but retains an explicit
    # empty span in GFM. Put list anchors inside their item to keep valid list HTML.
    fragment_targets = {
        str(linked.get("href"))[1:]
        for linked in body.select('a[href^="#"]')
        if len(str(linked.get("href"))) > 1
    }
    fragment_targets.update(
        str(item.get("id")) for item in body.select('li[id^="fn-"]')
    )
    for target in sorted(fragment_targets):
        destination = body.find(id=target)
        if destination is None:
            continue
        anchor = soup.new_tag("span", id=target)
        if destination.name == "li":
            destination.insert(0, anchor)
        else:
            destination.insert_before(anchor)
    for wrapper in body.find_all(
        ["div", "section", "aside", "main", "article", "figure", "span", "small"]
    ):
        if wrapper.name == "span" and wrapper.get("id"):
            continue
        wrapper.unwrap()
    for element in body.find_all(True):
        if element.name == "a":
            element.attrs = {key: element.attrs[key] for key in ("href", "title") if key in element.attrs}
        elif element.name == "img":
            element.attrs = {key: element.attrs[key] for key in ("src", "alt", "title") if key in element.attrs}
        elif element.name == "span" and element.get("id"):
            element.attrs = {"id": element["id"]}
        else:
            element.attrs = {}
    return (
        body.decode_contents(),
        images,
        embeds,
        intentional_omissions,
        callouts,
        duplicate_images,
    )


def html_to_markdown(value: str) -> str:
    markdown = pypandoc.convert_text(
        value,
        "gfm",
        format="html",
        extra_args=["--wrap=none", "--markdown-headings=atx"],
    )
    # Pandoc's GFM writer emits a terminal backslash for an HTML hard break, but
    # its own GFM reader treats that backslash literally. Two trailing spaces are
    # the interoperable GFM representation of the same break.
    markdown = re.sub(r"\\(?=\n)", "  ", markdown)
    return markdown.strip() + "\n"


def render_markdown(article: dict[str, Any], body_markdown: str) -> str:
    title = html.unescape(article["title"]["rendered"]).replace("\xa0", " ")
    return (
        f"# {title}\n\n"
        f"Source: [{article['link']}]({article['link']})  \n"
        f"WordPress ID: {article['id']}  \n"
        f"WordPress modified: {article['modified']}\n\n"
        f"{body_markdown.strip()}\n"
    )


def normalized_text(value: str) -> str:
    soup = BeautifulSoup(value, "lxml")
    text = unicodedata.normalize("NFC", soup.get_text(" ", strip=True))
    return re.sub(r"\s+", " ", text).strip()


def normalized_url(value: str) -> str:
    return unquote(html.unescape(value))


def normalized_label(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def normalized_match_text(value: str) -> str:
    """Normalize whitespace introduced at inline-element boundaries for matching."""
    value = normalized_label(value)
    value = re.sub(r"\s+([,.;:!?%)\]])", r"\1", value)
    return re.sub(r"([(\[])\s+", r"\1", value)


def html_inventory(value: str) -> dict[str, Any]:
    soup = BeautifulSoup(value, "lxml")
    return {
        "links": [normalized_url(str(a.get("href"))) for a in soup.select("a[href]")],
        "images": [
            (normalized_url(str(i.get("src"))), normalized_label(str(i.get("alt") or "")))
            for i in soup.select("img[src]")
        ],
        "headings": [
            (h.name, normalized_label(h.get_text(" ", strip=True)))
            for h in soup.select("h1,h2,h3,h4,h5,h6")
        ],
        "list_items": len(soup.select("li")),
        "tables": len(soup.select("table")),
        "blockquotes": len(soup.select("blockquote")),
        "fragment_links": [
            str(a.get("href")) for a in soup.select('a[href^="#"]')
        ],
        "fragment_targets": sorted(
            {str(element.get("id")) for element in soup.select("[id]")}
        ),
    }


def assess_conversion(source_html: str, markdown: str) -> dict[str, Any]:
    roundtrip_html = pypandoc.convert_text(
        markdown,
        "html",
        format="gfm-autolink_bare_uris+raw_html",
        extra_args=["--wrap=none"],
    )
    source_plain = normalized_text(source_html)
    markdown_plain = normalized_text(roundtrip_html)
    source = html_inventory(source_html)
    converted = html_inventory(roundtrip_html)
    exact_links = Counter(source["links"]) == Counter(converted["links"])
    exact_images = Counter(source["images"]) == Counter(converted["images"])
    exact_headings = source["headings"] == converted["headings"]
    converted_targets = set(converted["fragment_targets"])
    source_targets = set(source["fragment_targets"])
    fragments_resolve = all(
        target.removeprefix("#") in converted_targets
        for target in source["fragment_links"]
    )
    source_unresolved_fragments = sorted(
        {
            target
            for target in source["fragment_links"]
            if target.removeprefix("#") not in source_targets
        }
    )
    existing_targets_preserved = all(
        target in converted_targets for target in source_targets
    )
    checks = {
        "text_exact_after_whitespace_normalization": source_plain == markdown_plain,
        "text_similarity": round(SequenceMatcher(None, source_plain, markdown_plain).ratio(), 6),
        "source_text_characters": len(source_plain),
        "markdown_text_characters": len(markdown_plain),
        "link_targets_exact": exact_links,
        "image_references_and_alt_exact": exact_images,
        "headings_exact": exact_headings,
        "internal_fragment_links_resolve": fragments_resolve,
        "internal_fragment_targets_preserved": existing_targets_preserved,
        "source_unresolved_fragment_links": source_unresolved_fragments,
        "source": {key: len(value) if isinstance(value, list) else value for key, value in source.items()},
        "markdown": {key: len(value) if isinstance(value, list) else value for key, value in converted.items()},
    }
    warnings = []
    if not checks["text_exact_after_whitespace_normalization"]:
        warnings.append("text differs after whitespace normalization")
    if not exact_links:
        warnings.append("link target multiset differs")
    if not exact_images:
        warnings.append("image source or alt-text multiset differs")
    if not exact_headings:
        warnings.append("heading sequence differs")
    if not existing_targets_preserved:
        warnings.append("one or more source fragment targets were lost")
    for key in ("list_items", "tables", "blockquotes"):
        if source[key] != converted[key]:
            warnings.append(f"{key.replace('_', ' ')} count differs")
    checks["warnings"] = warnings
    checks["source_warnings"] = (
        ["source article contains unresolved internal fragment links"]
        if source_unresolved_fragments
        else []
    )
    checks["passed"] = not warnings
    return checks


def capture_article(
    url: str,
    output_dir: Path,
    *,
    download_images: bool = True,
) -> dict[str, Any]:
    (
        public_html,
        final_url,
        notes,
        callout_blocks,
        supplements,
        public_embeds,
    ) = public_page(canonical_url(url))
    article = _resolve_rest(final_url)
    if canonical_url(final_url) != canonical_url(article["link"]):
        raise CaptureError("public page redirected away from the resolved WordPress record")
    if supplements:
        cleaned_supplements = []
        for supplement in supplements:
            fragment = BeautifulSoup(supplement, "lxml")
            for callout in fragment.select('a[id^="fn-ref-"][href^="#fn-"]'):
                callout.decompose()
            container = fragment.body or fragment
            cleaned_supplements.append(container.decode_contents())
        article = {
            **article,
            "content": {
                **article["content"],
                "rendered": "".join(cleaned_supplements)
                + article["content"]["rendered"],
            },
        }
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = output_dir / "images"
    prepared, images, embeds, intentional_omissions, callouts, duplicate_images = prepare_html(
        article,
        notes,
        callout_blocks,
        asset_dir=asset_dir,
        reference_root="images",
        download_images=download_images,
    )
    body_markdown = html_to_markdown(prepared)
    markdown = render_markdown(article, body_markdown)
    markdown_path = output_dir / "article.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    (output_dir / "source.html").write_text(prepared, encoding="utf-8")
    quality = assess_conversion(prepared, body_markdown)
    failed_image_downloads = [
        image["source_url"] for image in images if download_images and not image["downloaded"]
    ]
    if failed_image_downloads:
        quality["warnings"].append("one or more source images could not be downloaded")
    quality["image_downloads"] = {
        "requested": download_images,
        "failed": failed_image_downloads,
    }
    captured_embed_urls = [embed["source_url"] for embed in embeds]
    missing_public_embeds = [
        source for source in public_embeds if source not in captured_embed_urls
    ]
    if missing_public_embeds:
        quality["warnings"].append(
            "one or more public-page embeds were not represented in Markdown"
        )
    quality["public_embeds"] = {
        "public": public_embeds,
        "captured": captured_embed_urls,
        "missing": missing_public_embeds,
    }
    quality["passed"] = not quality["warnings"]
    markdown_lines = markdown.splitlines()
    footnotes = []
    for number, note in enumerate(notes, 1):
        identifier = note["href"].removeprefix("#")
        marker = f'<span id="{identifier}"></span>'
        line = next(
            (index for index, value in enumerate(markdown_lines, 1) if marker in value),
            None,
        )
        footnotes.append(
            {
                "number": number,
                "source_anchor": note["href"],
                "markdown_target": identifier,
                "markdown_line": line,
                "preview": normalized_label(
                    BeautifulSoup(note["html"], "lxml").get_text(" ", strip=True)
                )[:160],
            }
        )
    for callout in callouts:
        target = callout["target"]
        link_markers = (f"]({target})", f'href="{target}"')
        callout["markdown_line"] = next(
            (
                index
                for index, value in enumerate(markdown_lines, 1)
                if any(marker in value for marker in link_markers)
            ),
            None,
        )
    callout_targets = Counter(callout["target"] for callout in callouts)
    footnote_targets = {note["href"] for note in notes}
    missing_callout_lines = [
        callout["reference_id"]
        for callout in callouts
        if callout["markdown_line"] is None
    ]
    orphaned_callouts = sorted(set(callout_targets) - footnote_targets)
    if missing_callout_lines:
        quality["warnings"].append(
            "one or more public footnote callouts were not found in Markdown"
        )
    if orphaned_callouts:
        quality["warnings"].append(
            "one or more public footnote callouts have no captured definition"
        )
    quality["footnote_callouts"] = {
        "public_callouts": len(callouts),
        "markdown_callouts": len(callouts) - len(missing_callout_lines),
        "missing_markdown_reference_ids": missing_callout_lines,
        "orphaned_targets": orphaned_callouts,
    }
    quality["passed"] = not quality["warnings"]
    manifest = {
        "schema_version": "1",
        "requested_url": canonical_url(url),
        "canonical_url": canonical_url(article["link"]),
        "wordpress": {
            "id": article["id"],
            "rest_base": article["rest_base"],
            "rest_url": article["rest_url"],
            "slug": article["slug"],
            "modified": article["modified"],
            "title": html.unescape(article["title"]["rendered"]),
        },
        "outputs": {
            "markdown": str(markdown_path),
            "source_html": str(output_dir / "source.html"),
            "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "public_page_sha256": hashlib.sha256(public_html).hexdigest(),
        },
        "counts": {
            "footnotes": len(notes),
            "footnote_callouts": len(callouts),
            "images": len(images),
            "images_downloaded": sum(bool(image["downloaded"]) for image in images),
        },
        "images": images,
        "embeds": embeds,
        "footnote_callouts": callouts,
        "deduplicated_images": duplicate_images,
        "intentional_omissions": intentional_omissions,
        "footnotes": footnotes,
        "quality": quality,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest
