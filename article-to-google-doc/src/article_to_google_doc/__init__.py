"""Capture public WordPress articles as checked Markdown."""

from .capture import CaptureError, capture_article, resolve_article

__all__ = ["CaptureError", "capture_article", "resolve_article"]

