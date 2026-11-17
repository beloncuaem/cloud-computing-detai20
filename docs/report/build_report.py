#!/usr/bin/env python3
"""Build the UTH-covered report DOCX (and optionally PDF) from the markdown.

Pipeline:
  1. pandoc markdown -> body DOCX (temp)
  2. prepend UTH cover (frame + logo + editable text) and front matter
  3. format_docx.py styles + populate [[TOC]]
  4. with --pdf: Word COM export -> extract_toc_pages -> re-format -> re-export

Usage (system python has python-docx? use the project venv for docx):
    ../wt-apikeys/.venv/Scripts/python.exe -X utf8 docs/report/build_report.py
    ../wt-apikeys/.venv/Scripts/python.exe -X utf8 docs/report/build_report.py --pdf

The venv lacks pywin32; run the --pdf step with system python instead, or run
docs/tools/office_to_pdf.py separately. Cover assets live in docs/report/assets.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

REPORT_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPORT_DIR.parent.parent
sys.path.insert(0, str(REPORT_DIR))
import format_docx  # noqa: E402

MD = REPORT_DIR / "bao-cao-ky-thuat.md"
OUT_DOCX = REPORT_DIR / "bao-cao-tong-hop.docx"
OUT_PDF = REPORT_DIR / "bao-cao-tong-hop.pdf"
FRAME = REPORT_DIR / "assets" / "cover_frame.jpeg"
LOGO = REPORT_DIR / "assets" / "cover_logo.png"
PANDOC = Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe"

EMU_PER_CM = 360000
FRAME_ASPECT = 912 / 1483  # width / height of the baked UTH frame

NSDECL = (
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)


def cm(v: float) -> int:
    return int(v * EMU_PER_CM)


def cover_frame_anchor(doc, rid: str) -> object:
    height_cm = 28.7
    width_cm = height_cm * FRAME_ASPECT
    x_cm = (21.0 - width_cm) / 2
    y_cm = 0.5
    w, h = cm(width_cm), cm(height_cm)
    xml = (
        f'<wp:anchor {NSDECL} distT="0" distB="0" distL="0" distR="0" simplePos="0" '
        f'relativeHeight="0" behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1">'
        f'<wp:simplePos x="0" y="0"/>'
        f'<wp:positionH relativeFrom="page"><wp:posOffset>{cm(x_cm)}</wp:posOffset></wp:positionH>'
        f'<wp:positionV relativeFrom="page"><wp:posOffset>{cm(y_cm)}</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="{w}" cy="{h}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:wrapNone/><wp:docPr id="900" name="CoverFrame"/>'
        f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="900" name="cover_frame.jpeg"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        f'</a:graphicData></a:graphic></wp:anchor>'
    )
    return parse_xml(xml)


def new_para(doc, text="", size=13, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER,
             space_after=6, space_before=0, recenter=False):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    if recenter:
        # thesis margins are 3/2 cm; shift the centering box back to page centre
        pf.left_indent = Cm(-0.5)
        pf.right_indent = Cm(0.5)
    if text:
        run = p.add_run(text)
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)
        run.font.bold = bold
    return p


def build_cover(doc) -> list:
    els = []
    # frame behind everything on page 1
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run()
    rid, _image = doc.part.get_or_add_image(str(FRAME))
    drawing = parse_xml(f'<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
    drawing.append(cover_frame_anchor(doc, rid))
    run._r.append(drawing)
    els.append(p._element)

    els.append(new_para(doc, space_after=2, recenter=True)._element)
    for line in ("BỘ XÂY DỰNG",
                 "TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI TP.HCM",
                 "VIỆN …………………………………………"):
        els.append(new_para(doc, line, 13, True, space_after=2, recenter=True)._element)
    els.append(new_para(doc, space_after=10, recenter=True)._element)

    lp = doc.add_paragraph()
    lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lp.paragraph_format.space_after = Pt(10)
    lp.paragraph_format.left_indent = Cm(-0.5)
    lp.paragraph_format.right_indent = Cm(0.5)
    lp.add_run().add_picture(str(LOGO), width=Cm(12))
    els.append(lp._element)

    els.append(new_para(doc, "ĐỒ ÁN HỌC PHẦN ĐIỆN TOÁN ĐÁM MÂY", 14, True,
                        space_after=10, recenter=True)._element)
    els.append(new_para(doc, "Đề tài 20:", 14, True, space_after=2, recenter=True)._element)
    els.append(new_para(doc, "BẢO VỆ DỮ LIỆU BẰNG MÃ HÓA, QUẢN LÝ KHÓA "
                             "VÀ VÒNG ĐỜI BÍ MẬT", 18, True, space_after=16,
                        recenter=True)._element)

    els.append(new_para(doc, "SINH VIÊN THỰC HIỆN", 14, True, space_after=4,
                        recenter=True)._element)
    for line in ("1. Hồ Thiên Phú — MSSV: 052205010238",
                 "2. Nguyễn Minh Hiếu — MSSV: 075206006264",
                 "3. Bùi Ngô Anh Quang — MSSV: 066206019831"):
        els.append(new_para(doc, line, 14, False, space_after=2, recenter=True)._element)
    els.append(new_para(doc, space_after=10, recenter=True)._element)
    els.append(new_para(doc, "GIẢNG VIÊN HƯỚNG DẪN: …………………………………………",
                        14, True, space_after=16, recenter=True)._element)
    els.append(new_para(doc, "TP. HỒ CHÍ MINH — HỌC KỲ 1, NĂM HỌC 2026–2027",
                        13, True, space_after=0, recenter=True)._element)

    brk = doc.add_paragraph()
    brk.paragraph_format.space_after = Pt(0)
    brk.add_run().add_break(WD_BREAK.PAGE)
    els.append(brk._element)
    return els


def front_matter(doc, md_text: str) -> list:
    els = []

    def h1(text):
        p = doc.add_paragraph(text, style="Heading 1")
        els.append(p._element)
        return p

    def body(text, size=13):
        p = new_para(doc, text, size, False, WD_ALIGN_PARAGRAPH.JUSTIFY,
                     space_after=6)
        p.paragraph_format.left_indent = Cm(0)
        p.paragraph_format.right_indent = Cm(0)
        els.append(p._element)
        return p

    def pagebreak():
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.add_run().add_break(WD_BREAK.PAGE)
        els.append(p._element)

    h1("TÓM TẮT")
    body("Đồ án xây dựng một nguyên mẫu dịch vụ lưu trữ bản ghi nhạy cảm trên đám mây "
         "riêng (Docker Compose) để trả lời câu hỏi: mã hóa chỉ bảo vệ được đến đâu nếu "
         "khóa, secret ứng dụng và quyền giải mã không được quản lý tách biệt. Kiến trúc "
         "đích dùng mã hóa phong bì AES-256-GCM với KEK nằm trong HashiCorp Vault "
         "(Transit), DEK sinh per-record và bọc bởi KEK; credential PostgreSQL cấp động "
         "qua Database secrets engine; workload identity bằng AppRole; xoay vòng KEK và "
         "credential không gián đoạn. Toàn bộ kênh client–server và API–PostgreSQL chạy "
         "TLS thật (nginx terminator, PostgreSQL ssl=on). Đo lường k6 trên bốn cấu hình "
         "B/D/D'/E qua TLS cho thấy chi phí overhead của envelope và lợi ích của cache "
         "DEK có kiểm soát, đồng thời chứng minh xoay vòng không gây lỗi. At-rest cấp "
         "volume được chấp nhận rủi ro bằng văn bản do BitLocker tắt trên máy cá nhân.")
    h1("ABSTRACT")
    body("This project builds a prototype sensitive-record storage service on a private "
         "cloud (Docker Compose) to answer: how far does encryption protect data if keys, "
         "application secrets and decryption rights are not managed separately? The "
         "target architecture uses AES-256-GCM envelope encryption with the KEK held in "
         "HashiCorp Vault Transit, per-record DEKs wrapped by the KEK, dynamic PostgreSQL "
         "credentials, AppRole workload identity, and zero-downtime key/credential "
         "rotation. All client–server and API–PostgreSQL channels run real TLS. k6 "
         "measurements over TLS across configurations B/D/D'/E quantify envelope "
         "overhead and the benefit of controlled DEK caching, and show rotation causes "
         "no errors. Volume-level at-rest encryption is risk-accepted in writing because "
         "BitLocker is off on the personal machine.", size=12)
    pagebreak()

    h1("DANH MỤC TỪ VIẾT TẮT")
    abbrev = [
        ("AAD", "Additional Authenticated Data"),
        ("AES", "Advanced Encryption Standard"),
        ("API", "Application Programming Interface"),
        ("AppRole", "Vault authentication method cho workload"),
        ("CA", "Certificate Authority"),
        ("CI/CD", "Continuous Integration / Continuous Delivery"),
        ("DEK", "Data Encryption Key"),
        ("GCM", "Galois/Counter Mode"),
        ("HSM", "Hardware Security Module"),
        ("KEK", "Key Encryption Key"),
        ("KMS", "Key Management Service"),
        ("k6", "Công cụ tải kiểm thử hiệu năng"),
        ("p50/p95/p99", "Phân vị trễ thứ 50/95/99"),
        ("RPS", "Requests Per Second"),
        ("SAN", "Subject Alternative Name"),
        ("TLS", "Transport Layer Security"),
        ("UTH", "University of Transport Ho Chi Minh City"),
        ("VU", "Virtual User (k6)"),
    ]
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Từ viết tắt"
    table.rows[0].cells[1].text = "Ý nghĩa"
    for term, meaning in abbrev:
        row = table.add_row()
        row.cells[0].text = term
        row.cells[1].text = meaning
    els.append(table._element)
    pagebreak()

    h1("DANH MỤC HÌNH ẢNH")
    for cap in re.findall(r"^!\[(Hình \d+\.[^\]]*)\]", md_text, re.M):
        body(cap, size=12)
    h1("DANH MỤC BẢNG BIỂU")
    for cap in re.findall(r"^\*\*(Bảng \d+\.[^*]*)\*\*", md_text, re.M):
        body(cap, size=12)
    pagebreak()

    h1("MỤC LỤC")
    marker = doc.add_paragraph("[[TOC]]")
    els.append(marker._element)
    return els


def main() -> None:
    want_pdf = "--pdf" in sys.argv
    md_text = MD.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as td:
        body_docx = Path(td) / "body.docx"
        subprocess.run(
            [str(PANDOC), str(MD), "-f", "markdown", "-t", "docx",
             "--resource-path", str(REPORT_DIR), "-o", str(body_docx)],
            check=True,
        )
        doc = Document(str(body_docx))
        body_el = doc.element.body
        first = body_el[0]
        for el in build_cover(doc) + front_matter(doc, md_text):
            first.addprevious(el)
        doc.save(str(OUT_DOCX))

    format_docx.main(OUT_DOCX, None)
    print(f"built {OUT_DOCX}")

    if want_pdf:
        sys.path.insert(0, str(REPO_ROOT / "docs" / "tools"))
        import office_to_pdf
        import extract_toc_pages
        office_to_pdf.export(OUT_DOCX, OUT_PDF)
        pages_json = REPORT_DIR / "toc-pages.json"
        extract_toc_pages.main(OUT_PDF, MD, pages_json)
        format_docx.main(OUT_DOCX, pages_json)
        office_to_pdf.export(OUT_DOCX, OUT_PDF)
        print(f"built {OUT_PDF} (2-pass TOC)")


if __name__ == "__main__":
    main()