#!/usr/bin/env python3
"""Apply the report's print formatting to the Pandoc-generated DOCX.

Usage:
    pip install python-docx
    python docs/report/format_docx.py docs/report/bao-cao-ky-thuat.docx
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_LINE_SPACING,
    WD_TAB_ALIGNMENT,
    WD_TAB_LEADER,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


def set_font(style, name: str, size: float, bold: bool | None = None, italic: bool | None = None) -> None:
    style.font.name = name
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def read_headings(markdown_path: Path) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{2,3})\s+(.*)$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = re.sub(r"[`*_]", "", match.group(2)).strip()
        if title.upper() == "MỤC LỤC":
            continue
        headings.append((level, title))
    return headings


def populate_toc(document, markdown_path: Path, pages: dict[str, int]) -> None:
    marker = next((p for p in document.paragraphs if p.text.strip() == "[[TOC]]"), None)
    if marker is None:
        print("warning: [[TOC]] marker not found; skipping table of contents")
        return

    for level, title in read_headings(markdown_path):
        paragraph = marker.insert_paragraph_before()
        paragraph.style = document.styles["Normal"]
        # Keep the whole TOC on one page: 38 entries at 12 pt.
        paragraph.paragraph_format.space_after = Pt(2 if level == 3 else 5)
        paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Cm(0)
        paragraph.paragraph_format.left_indent = Cm(0.7) if level == 3 else Cm(0)
        paragraph.paragraph_format.tab_stops.add_tab_stop(
            Cm(15.9), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
        )
        title_run = paragraph.add_run(title)
        title_run.font.name = "Times New Roman"
        title_run.font.size = Pt(12.5 if level == 2 else 12)
        title_run.font.bold = level == 2
        number_run = paragraph.add_run("\t" + str(pages.get(title, "")))
        number_run.font.name = "Times New Roman"
        number_run.font.size = Pt(12.5 if level == 2 else 12)
        number_run.font.bold = level == 2

    marker._element.getparent().remove(marker._element)


def main(path: Path, pages_path: Path | None) -> None:
    document = Document(path)

    # A4 with Vietnamese thesis margins: 3 cm left, 2 cm elsewhere.
    for section in document.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(2.0)
        section.different_first_page_header_footer = True
        footer = section.footer.paragraphs[0]
        add_page_number(footer)

    styles = document.styles
    normal = styles["Normal"]
    set_font(normal, "Times New Roman", 13)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    style_specs = {
        "Title": (20, True, WD_ALIGN_PARAGRAPH.CENTER),
        "Heading 1": (18, True, WD_ALIGN_PARAGRAPH.CENTER),
        "Heading 2": (16, True, WD_ALIGN_PARAGRAPH.LEFT),
        "Heading 3": (14, True, WD_ALIGN_PARAGRAPH.LEFT),
        "Heading 4": (13, True, WD_ALIGN_PARAGRAPH.LEFT),
    }
    for name, (size, bold, align) in style_specs.items():
        if name not in styles:
            continue
        style = styles[name]
        set_font(style, "Times New Roman", size, bold=bold)
        style.paragraph_format.space_before = Pt(12 if name != "Title" else 0)
        style.paragraph_format.space_after = Pt(8)
        style.paragraph_format.alignment = align
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE

    # Lists inherit justified text; long file paths then stretch spaces badly.
    if "Compact" in styles:
        styles["Compact"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Start each level-2 heading on a new page. Putting page_break_before on the
    # heading itself avoids the blank page left by a separate break paragraph.
    for paragraph in document.paragraphs:
        if paragraph.style.name == "Heading 2" and paragraph.text.strip():
            paragraph.paragraph_format.page_break_before = True

    # Code blocks should not be justified; keep them compact and monospaced.
    if "Verbatim Char" in styles:
        set_font(styles["Verbatim Char"], "Consolas", 9.5)
    if "Source Code" in styles:
        style = styles["Source Code"]
        set_font(style, "Consolas", 9.5)
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Compact table text, bold header row, repeat header on every page.
    for table in document.tables:
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True
        for row_index, row in enumerate(table.rows):
            if row_index == 0:
                repeat_header(row)
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(2)
                    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                    paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    for run in paragraph.runs:
                        run.font.name = "Times New Roman"
                        run.font.size = Pt(10.5)
                        if row_index == 0:
                            run.font.bold = True

    pages: dict[str, int] = {}
    if pages_path and pages_path.exists():
        pages = json.loads(pages_path.read_text(encoding="utf-8"))
    populate_toc(document, path.parent / "bao-cao-ky-thuat.md", pages)

    document.core_properties.title = "Báo cáo kỹ thuật — Đề tài 20: Bảo vệ dữ liệu bằng mã hóa, quản lý khóa và vòng đời bí mật"
    document.core_properties.author = "Bùi Ngô Anh Quang; hothienphu; Nguyễn Minh Hiếu"
    document.core_properties.subject = "Điện toán đám mây — Trường Đại học Giao thông vận tải TP.HCM"

    document.save(path)
    print(f"formatted {path} ({len(pages)} TOC page numbers)")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/report/bao-cao-ky-thuat.docx")
    pages_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    main(target, pages_arg)
