#!/usr/bin/env python3
"""Map each level-2/level-3 heading in the report to its PDF page number.

Usage:
    pip install pymupdf
    python docs/report/extract_toc_pages.py bao-cao-ky-thuat.pdf bao-cao-ky-thuat.md toc-pages.json

The PDF must already contain the TOC section (entries may have blank numbers).
The script skips the TOC pages themselves so headings are matched in the body.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf


def normalize(text: str) -> str:
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def headings(markdown: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for line in markdown.splitlines():
        match = re.match(r"^(#{2,3})\s+(.*)$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = normalize(match.group(2))
        if title.upper() == "MỤC LỤC":
            continue
        result.append((level, title))
    return result


def main(pdf_path: Path, markdown_path: Path, output_path: Path) -> None:
    document = pymupdf.open(pdf_path)
    expected = headings(markdown_path.read_text(encoding="utf-8"))

    # LibreOffice exports every heading as a bookmark, even when the text
    # layer decomposes Vietnamese diacritics. Prefer bookmarks; fall back to
    # text search only if a PDF has no outline.
    bookmarks = {
        normalize(title): page
        for level, title, page in document.get_toc(simple=True)
        if level in (2, 3) and normalize(title).upper() != "MỤC LỤC"
    }
    result: dict[str, int] = {}
    if bookmarks:
        for _level, title in expected:
            if title in bookmarks:
                result[title] = bookmarks[title]
    else:
        pages = [normalize(page.get_text("text")) for page in document]
        toc_last = max((i for i, text in enumerate(pages) if "MỤC LỤC" in text), default=0)
        for _level, title in expected:
            needle = title[:60]
            for index in range(toc_last + 1, len(pages)):
                if needle in pages[index]:
                    result[title] = index + 1
                    break

    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [title for _level, title in expected if title not in result]
    print(f"mapped {len(result)} headings, missing {len(missing)}")
    for title in missing:
        print("MISSING:", title)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
