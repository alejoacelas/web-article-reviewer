"""Command-line interface for URL capture and optional Google Doc creation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .capture import CaptureError, capture_article, url_slug

def create_google_doc(
    manifest: dict[str, Any], *, account: str, folder: str | None = None
) -> dict[str, Any]:
    title = manifest["wordpress"]["title"]
    command = [
        "gdoc", "new", title,
        "--file", manifest["outputs"]["markdown"],
        "--account", account,
        "--json",
    ]
    if folder:
        command.extend(["--folder", folder])
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode:
        raise CaptureError(f"gdoc failed: {process.stderr.strip() or process.stdout.strip()}")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise CaptureError("gdoc succeeded but did not return JSON") from error


def capture_command(args: argparse.Namespace) -> int:
    if args.create_doc and not args.account:
        raise CaptureError("Set --account or GDOC_ACCOUNT before creating a Google Doc")
    destination = args.output_dir
    if destination is None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
        destination = Path("captures") / f"{stamp}-{url_slug(args.url)}"
    manifest = capture_article(
        args.url, destination, download_images=not args.skip_images
    )
    if args.create_doc:
        if not manifest["quality"]["passed"]:
            raise CaptureError("capture checks failed; Google Doc was not created")
        manifest["google_doc"] = create_google_doc(
            manifest, account=args.account, folder=args.folder
        )
        (destination / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["quality"]["passed"] else 2


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Capture one public WordPress article as checked Markdown."
    )
    result.add_argument("url")
    result.add_argument("--output-dir", type=Path)
    result.add_argument("--skip-images", action="store_true", help="Keep remote image URLs for a fast capture")
    result.add_argument("--create-doc", action="store_true", help="Create a native Google Doc with gdoc after capture")
    result.add_argument("--account", default=os.environ.get("GDOC_ACCOUNT"), help="Google account for --create-doc (or set GDOC_ACCOUNT)")
    result.add_argument("--folder", help="Google Drive folder ID for --create-doc")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return capture_command(args)
    except (CaptureError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
