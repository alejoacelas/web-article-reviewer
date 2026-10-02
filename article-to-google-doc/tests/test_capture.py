from __future__ import annotations

from pathlib import Path

import pytest

from article_to_google_doc.capture import (
    CaptureError,
    Response,
    assess_conversion,
    canonical_url,
    html_to_markdown,
    largest_srcset_url,
    prepare_html,
    resolve_article,
)


def article(content: str) -> dict:
    return {
        "id": 42,
        "link": "https://example.org/articles/example/",
        "modified": "2026-08-27T12:00:00",
        "slug": "example",
        "title": {"rendered": "Example &amp; title"},
        "content": {"rendered": content},
    }


def test_canonical_url_preserves_origin_and_drops_tracking():
    assert canonical_url("http://www.example.org/articles/example?x=1#part") == (
        "http://www.example.org/articles/example/"
    )


@pytest.mark.parametrize("url", ["file:///article", "https:///article", "https://user:pass@example.org/article"])
def test_canonical_url_rejects_invalid_urls(url):
    with pytest.raises(CaptureError):
        canonical_url(url)


def test_largest_srcset_uses_width_not_order():
    assert largest_srcset_url(
        "/small.jpg 300w, /large.jpg 1200w, /medium.jpg 600w",
        "https://example.org/articles/example/",
    ) == "https://example.org/large.jpg"


def test_resolver_uses_redirected_canonical_url(monkeypatch):
    final = "https://example.org/problem-profiles/loss-of-control/"
    monkeypatch.setattr(
        "article_to_google_doc.capture.fetch",
        lambda *_args, **_kwargs: Response(b"", "text/html", final),
    )
    monkeypatch.setattr(
        "article_to_google_doc.capture._resolve_rest",
        lambda value: {"link": value},
    )
    assert resolve_article(
        "https://example.org/problem-profiles/risks-from-power-seeking-ai/"
    ) == {"link": final}


def test_html_hard_break_does_not_become_a_visible_backslash():
    markdown = html_to_markdown("<p>First.<br></p><p>Second.</p>")
    assert "First.\\\n" not in markdown
    result = assess_conversion("<p>First.<br></p><p>Second.</p>", markdown)
    assert result["text_exact_after_whitespace_normalization"] is True


def test_prepare_html_preserves_links_images_captions_and_notes(tmp_path: Path):
    notes = [{"href": "#fn-1", "html": '<p>Note <a href="/source/">source</a>.</p>'}]

    def downloader(url: str) -> Response:
        assert url == "https://example.org/large.png"
        return Response(b"png", "image/png", url)

    prepared, images, embeds, omissions, callouts, duplicates = prepare_html(
        article(
            '<h2>Section</h2><p>A <a href="/go/">link</a>.</p>'
            '<figure><img src="/small.png" srcset="/large.png 1000w" alt="Chart">'
            "<figcaption>What it shows.</figcaption></figure>"
        ),
        notes,
        [],
        asset_dir=tmp_path / "images",
        reference_root="images",
        downloader=downloader,
    )
    assert 'href="https://example.org/go/"' in prepared
    assert 'href="https://example.org/source/"' in prepared
    assert 'src="images/01-large.png"' in prepared
    assert "Caption:" in prepared and "What it shows." in prepared
    assert "Notes and references" in prepared
    assert '<span id="fn-1"></span>' in prepared
    assert images[0]["downloaded"] is True
    assert embeds == []
    assert omissions["forms"] == 0
    assert callouts == [] and duplicates == []


def test_quality_gate_accepts_semantically_lossless_markdown():
    source = (
        '<h2>Section</h2><p>A <a href="https://example.com">link</a>.</p>'
        '<ul><li>One</li><li>Two</li></ul><blockquote>Quote</blockquote>'
    )
    markdown = "## Section\n\nA [link](https://example.com).\n\n- One\n- Two\n\n> Quote\n"
    result = assess_conversion(source, markdown)
    assert result["passed"] is True
    assert result["text_exact_after_whitespace_normalization"] is True
    assert result["link_targets_exact"] is True


def test_quality_gate_reports_dropped_link():
    result = assess_conversion('<p><a href="https://example.com">source</a></p>', "source\n")
    assert result["passed"] is False
    assert "link target multiset differs" in result["warnings"]


def test_quality_gate_treats_equivalent_unicode_as_the_same_text():
    result = assess_conversion("<p>Villalo\u0301n</p>", "Villalón\n")
    assert result["passed"] is True


def test_footnote_fragment_survives_markdown_round_trip(tmp_path: Path):
    prepared, _, _, _, _, _ = prepare_html(
        article('<p>Claim.<a href="#fn-1">1</a></p>'),
        [{"href": "#fn-1", "html": "Complete note."}],
        [],
        asset_dir=tmp_path / "images",
        reference_root="images",
        download_images=False,
    )
    markdown = html_to_markdown(prepared)
    assert '<span id="fn-1">' in markdown
    result = assess_conversion(prepared, markdown)
    assert result["internal_fragment_links_resolve"] is True
    assert result["internal_fragment_targets_preserved"] is True
    assert result["passed"] is True


def test_iframe_becomes_a_readable_source_link(tmp_path: Path):
    prepared, _, embeds, _, _, _ = prepare_html(
        article('<p>Chart follows.</p><iframe src="https://ourworldindata.org/grapher/example"></iframe>'),
        [],
        [],
        asset_dir=tmp_path / "images",
        reference_root="images",
        download_images=False,
    )
    assert "iframe" not in prepared
    assert 'href="https://ourworldindata.org/grapher/example"' in prepared
    assert embeds == [
        {
            "source_url": "https://ourworldindata.org/grapher/example",
            "label": "Embedded content from ourworldindata.org",
        }
    ]


def test_public_callout_is_merged_into_matching_rest_block(tmp_path: Path):
    block = {
        "tag": "p",
        "text_without_callouts": "Claim.",
        "html": '<p>Claim.<a id="fn-ref-1" href="#fn-1"><sup>1</sup></a></p>',
        "callouts": [{"reference_id": "fn-ref-1", "target": "#fn-1", "label": "1"}],
    }
    prepared, _, _, _, callouts, _ = prepare_html(
        article("<p>Claim.</p>"),
        [{"href": "#fn-1", "html": "Evidence."}],
        [block],
        asset_dir=tmp_path / "images",
        reference_root="images",
        download_images=False,
    )
    markdown = html_to_markdown(prepared)
    assert "[1](#fn-1)" in markdown
    assert callouts[0]["reference_id"] == "fn-ref-1"


def test_duplicate_sidebar_callout_uses_the_matching_article_block(tmp_path: Path):
    callout = {"reference_id": "fn-ref-1", "target": "#fn-1", "label": "1"}
    blocks = [
        {
            "tag": "li",
            "text_without_callouts": "Sidebar summary.",
            "html": '<li>Sidebar summary.<a id="fn-ref-1" href="#fn-1">1</a></li>',
            "callouts": [callout],
        },
        {
            "tag": "p",
            "text_without_callouts": "Article claim.",
            "html": '<p>Article claim.<a id="fn-ref-1" href="#fn-1" title="note text"><sup>1</sup></a></p>',
            "callouts": [callout],
        },
    ]
    prepared, _, _, _, callouts, _ = prepare_html(
        article("<p>Article claim.</p>"),
        [{"href": "#fn-1", "html": "Evidence."}],
        blocks,
        asset_dir=tmp_path / "images",
        reference_root="images",
        download_images=False,
    )
    markdown = html_to_markdown(prepared)
    assert markdown.count("[1](#fn-1)") == 1
    assert "note text" not in markdown
    assert len(callouts) == 1


def test_duplicate_responsive_image_and_empty_caption_are_removed(tmp_path: Path):
    prepared, images, _, _, _, duplicates = prepare_html(
        article(
            '<figure><img src="/same.png" alt="Chart"><figcaption> </figcaption></figure>'
            '<noscript><img src="/same.png" alt="Chart"></noscript>'
        ),
        [],
        [],
        asset_dir=tmp_path / "images",
        reference_root="images",
        download_images=False,
    )
    assert prepared.count("same.png") == 1
    assert "Caption:" not in prepared
    assert len(images) == 1 and len(duplicates) == 1


def test_source_broken_fragment_is_reported_without_blame_on_conversion():
    result = assess_conversion('<p><a href="#missing">Section</a></p>', '[Section](#missing)\n')
    assert result["internal_fragment_links_resolve"] is False
    assert result["source_unresolved_fragment_links"] == ["#missing"]
    assert result["source_warnings"]
    assert result["passed"] is True


@pytest.mark.parametrize("origin", ["https://example.org", "http://www.example.net:8080"])
def test_rest_resolution_uses_requested_site(monkeypatch, origin):
    from article_to_google_doc.capture import _resolve_rest

    requested = f"{origin}/articles/example/"
    calls = []

    def fetch_json(url):
        calls.append(url)
        if url == f"{origin}/wp-json/wp/v2/types":
            return {"post": {"rest_base": "posts"}}
        assert url.startswith(f"{origin}/wp-json/wp/v2/posts?")
        return [{**article("<p>Example.</p>"), "link": requested}]

    monkeypatch.setattr("article_to_google_doc.capture.fetch_json", fetch_json)
    assert _resolve_rest(requested)["link"] == requested
    assert len(calls) == 2


def test_doc_creation_requires_account_before_capture(monkeypatch):
    from article_to_google_doc.cli import capture_command, parser

    monkeypatch.delenv("GDOC_ACCOUNT", raising=False)
    monkeypatch.setattr(
        "article_to_google_doc.cli.capture_article",
        lambda *args, **kwargs: pytest.fail("capture must not start without an account"),
    )
    args = parser().parse_args(["https://example.org/articles/example/", "--create-doc"])
    with pytest.raises(CaptureError, match="Set --account or GDOC_ACCOUNT"):
        capture_command(args)


def test_doc_account_can_be_configured_or_overridden(monkeypatch):
    from article_to_google_doc.cli import parser

    monkeypatch.setenv("GDOC_ACCOUNT", "configured@example.org")
    assert parser().parse_args(["https://example.org/article/"]).account == "configured@example.org"
    args = parser().parse_args([
        "https://example.org/article/", "--account", "explicit@example.org"
    ])
    assert args.account == "explicit@example.org"


def test_pipeline_delivery_requires_account_before_subprocess(monkeypatch):
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "pipeline" / "deliver.py"
    spec = importlib.util.spec_from_file_location("deliver", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ACCOUNT", None)
    monkeypatch.setattr(
        module.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("gdoc must not run without an account"),
    )
    with pytest.raises(ValueError, match="Set GDOC_ACCOUNT"):
        module.gdoc("new", "Example")
