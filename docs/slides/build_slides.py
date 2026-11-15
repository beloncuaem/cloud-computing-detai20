#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sinh bộ slide thuyết trình tiếng Việt (~20 trang) theo UTH theme.

Đọc `noid-dung-slide.json` + `uth-template.pptx` (sinh bởi make_template.py),
xuất `thuyet-trinh-de-tai-20-UTH.pptx`. Chỉ dùng python-pptx + stdlib.

Quy tắc trình bày:
- Title dùng placeholder idx 0; cỡ chữ title để theme quyết định (không đổi).
- Bullets vào placeholder content; bullet con (prefix "– ") đặt level 1.
- Font chữ kế thừa theme (không đổi typeface); body chỉ chỉnh cỡ 20–22 pt
  khi ước lượng tràn, nếu vẫn tràn thì in cảnh báo ra stdout.
- Slide ảnh: layout 5 (Title Only), ảnh vùng phải/giữa, rộng ≤ 8.5 in, giữ tỉ lệ;
  caption là textbox 12 pt dưới ảnh; bullets (nếu có) đặt textbox trái 20 pt.
- Slide bảng (S14, S15): layout 5 + native table, font 14–16 pt,
  header nền teal 008080 chữ trắng.

Cách chạy (system python có python-pptx):
    python -X utf8 docs/slides/build_slides.py [json] [template] [out]
"""

import json
import math
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_JSON = SCRIPT_DIR / "noid-dung-slide.json"
DEFAULT_TEMPLATE = SCRIPT_DIR / "uth-template.pptx"
DEFAULT_OUT = SCRIPT_DIR / "thuyet-trinh-de-tai-20-UTH.pptx"

SLIDE_W_IN = 13.333
SLIDE_H_IN = 7.5
TEAL = RGBColor(0x00, 0x80, 0x80)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BAND_LIGHT = RGBColor(0xEE, 0xF3, 0xF3)
CHAR_W_FACTOR = 0.5  # bề rộng ký tự trung bình ~ 0.5 * cỡ chữ (pt)

WARNINGS = []

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}

# Placeholder ngày/footer/số trang là thành phần có chủ đích của theme.
THEME_PH_TYPES = {13, 15, 16}  # SLIDE_NUMBER, FOOTER, DATE (PP_PLACEHOLDER)


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"[CẢNH BÁO] {msg}")


def theme_body_defaults(template_path: Path):
    """Đọc cỡ chữ body mặc định + line spacing + space before từ slideMaster.

    Trả về (base_pt, lnspc, spc_bef_pt). Fallback an toàn nếu không đọc được.
    """
    base, lnspc, spc_bef = 24.0, 1.0, 6.0
    try:
        with zipfile.ZipFile(template_path) as z:
            for name in z.namelist():
                if name.startswith("ppt/slideMasters/slideMaster") and name.endswith(".xml"):
                    root = ET.fromstring(z.read(name))
                    lvl1 = root.find(".//p:txStyles/p:bodyStyle/a:lvl1pPr", NS)
                    if lvl1 is None:
                        continue
                    defrpr = lvl1.find("a:defRPr", NS)
                    if defrpr is not None and defrpr.get("sz"):
                        base = int(defrpr.get("sz")) / 100.0
                    pct = lvl1.find("a:lnSpc/a:spcPct", NS)
                    if pct is not None:
                        lnspc = int(pct.get("val")) / 100000.0
                    pts = lvl1.find("a:spcBef/a:spcPts", NS)
                    if pts is not None:
                        spc_bef = int(pts.get("val")) / 100.0
                    break
    except Exception as exc:  # không để lỗi đọc theme chặn việc build
        warn(f"Không đọc được body default từ master ({exc}); dùng fallback 24 pt.")
    return base, lnspc, spc_bef


def estimate_height_pt(items, width_in, size_pt, lnspc, spc_bef, indent=True):
    """Ước lượng chiều cao cần (pt) cho danh sách (text, level)."""
    total = 0.0
    for text, level in items:
        mar_l = (0.25 if level == 0 else 0.75) if indent else 0.05
        usable_w = max(1.0, width_in - mar_l)
        cpl = max(8, int((usable_w * 72.0) / (CHAR_W_FACTOR * size_pt)))
        lines = max(1, math.ceil(len(text) / cpl))
        total += lines * size_pt * lnspc
    total += len(items) * spc_bef
    return total


def fit_font_size(items, width_in, height_in, base_pt, lnspc, spc_bef,
                  candidates=None, indent=True):
    """Chọn cỡ chữ vừa khung. Trả về (size_pt, overflow?).

    Nếu base_pt vừa khung thì giữ nguyên kế thừa theme. Ngược lại thử các cỡ
    trong candidates (mặc định 22, 20). Vẫn tràn -> cỡ nhỏ nhất + cảnh báo.
    """
    if candidates is None:
        candidates = [22.0, 20.0]
    options = sorted({base_pt, *candidates}, reverse=True)
    avail = height_in * 72.0
    for size in options:
        if estimate_height_pt(items, width_in, size, lnspc, spc_bef, indent) <= avail:
            return size, False
    return options[-1], True


def set_runs_size(text_frame, size_pt):
    for para in text_frame.paragraphs:
        for run in para.runs:
            run.font.size = Pt(size_pt)


def fill_bullets_tf(tf, bullets, base_pt, lnspc, spc_bef, width_in, height_in,
                    slide_no, candidates=None, indent=True):
    """Đổ bullets vào text frame, chọn cỡ chữ chống tràn. Trả về số bullet."""
    tf.word_wrap = True
    items = []
    for i, text in enumerate(bullets):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = text
        para.level = 1 if text.startswith("– ") else 0
        items.append((text, para.level))
    size, overflow = fit_font_size(items, width_in, height_in, base_pt,
                                   lnspc, spc_bef, candidates, indent)
    if size != base_pt:
        set_runs_size(tf, size)
    if overflow:
        warn(f"Slide {slide_no}: ước lượng TRÀN khung chữ ngay cả ở {size:g} pt "
             f"(cần ~{estimate_height_pt(items, width_in, size, lnspc, spc_bef, indent):.0f} pt, "
             f"khung {height_in * 72:.0f} pt). Nên tách bullet hoặc rút gọn.")
    return len(bullets)


def remove_unintended_empty_placeholders(slide):
    for ph in list(slide.placeholders):
        ph_type = ph.placeholder_format.type
        if ph_type in THEME_PH_TYPES:
            continue
        if ph.has_text_frame and not ph.text_frame.text.strip():
            ph._element.getparent().remove(ph._element)


def add_image_with_caption(slide, img_path: Path, caption, area, slide_no):
    """Thêm ảnh vào vùng (x, y, w, h) inch, giữ tỉ lệ, caption 12 pt bên dưới."""
    ax, ay, aw, ah = area
    pic = slide.shapes.add_picture(str(img_path), Inches(ax), Inches(ay),
                                   width=Inches(aw))
    max_h = Inches(ah)
    if pic.height > max_h:
        ratio = max_h / pic.height
        pic.height = int(max_h)
        pic.width = int(pic.width * ratio)
    # căn giữa ngang trong vùng ảnh
    pic.left = int(Inches(ax) + (Inches(aw) - pic.width) / 2)
    pic.top = Inches(ay)
    if caption:
        cap_top = pic.top + pic.height + Inches(0.08)
        box = slide.shapes.add_textbox(Inches(ax), cap_top, Inches(aw), Inches(0.55))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = caption
        p.alignment = PP_ALIGN.CENTER
        for run in p.runs:
            run.font.size = Pt(12)
        if cap_top + Inches(0.55) > Inches(SLIDE_H_IN - 0.15):
            warn(f"Slide {slide_no}: caption ảnh có thể sát mép dưới slide.")


def build_table(slide, table_spec, slide_no):
    headers = table_spec["headers"]
    rows = table_spec["rows"]
    ncols = len(headers)
    nrows = len(rows) + 1
    font_pt = 16 if ncols == 2 else 14

    left, top, total_w = 0.92, 2.3, 11.5
    if ncols == 2:
        col_w = [2.6, 8.9]
        header_h, row_h = 0.5, 0.5
    else:
        col_w = [1.9, 1.0, 3.0, 3.0, 2.6]
        header_h, row_h = 0.4, 0.35
    total_h = header_h + row_h * len(rows)
    if top + total_h > 6.9:
        warn(f"Slide {slide_no}: bảng ước lượng chạm vùng footer "
             f"({top + total_h:.2f} in > 6.9 in).")

    shape = slide.shapes.add_table(nrows, ncols, Inches(left), Inches(top),
                                   Inches(total_w), Inches(total_h))
    table = shape.table
    table.first_row = True
    table.horz_banding = False
    for i, w in enumerate(col_w):
        table.columns[i].width = Inches(w)
    table.rows[0].height = Inches(header_h)
    for r in range(1, nrows):
        table.rows[r].height = Inches(row_h)

    def style_cell(cell, text, is_header, r, c):
        cell.margin_left = Inches(0.08)
        cell.margin_right = Inches(0.08)
        cell.margin_top = Inches(0.02)
        cell.margin_bottom = Inches(0.02)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        if is_header:
            p.alignment = PP_ALIGN.CENTER
        elif ncols == 2:
            p.alignment = PP_ALIGN.LEFT if c == 1 else PP_ALIGN.CENTER
        else:
            p.alignment = PP_ALIGN.CENTER
        cell.fill.solid()
        if is_header:
            cell.fill.fore_color.rgb = TEAL
        else:
            cell.fill.fore_color.rgb = WHITE if r % 2 == 1 else BAND_LIGHT
        for run in p.runs:
            run.font.size = Pt(font_pt)
            if is_header:
                run.font.bold = True
                run.font.color.rgb = WHITE

    for c, h in enumerate(headers):
        style_cell(table.cell(0, c), h, True, 0, c)
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            style_cell(table.cell(r, c), str(val), False, r, c)
    return nrows, ncols


def build_slide(prs, spec, slide_no, base_pt, lnspc, spc_bef):
    layout_idx = spec["layout"]
    layout = prs.slide_layouts[layout_idx]
    slide = prs.slides.add_slide(layout)

    # Title (placeholder 0) — giữ nguyên cỡ chữ/font của theme.
    title_ph = slide.shapes.title
    if title_ph is None:
        raise RuntimeError(f"Slide {slide_no}: layout {layout_idx} không có title placeholder.")
    title_ph.text_frame.word_wrap = True
    title_ph.text_frame.text = spec["title"]

    n_bullets = 0
    has_image = False
    has_table = False

    if layout_idx == 0:
        if spec.get("subtitle"):
            sub = slide.placeholders[1]
            sub.text_frame.word_wrap = True
            sub.text_frame.text = spec["subtitle"]
    elif spec.get("table"):
        build_table(slide, spec["table"], slide_no)
        has_table = True
    elif spec.get("image"):
        img_path = REPO_ROOT / spec["image"]
        if not img_path.is_file():
            raise FileNotFoundError(f"Slide {slide_no}: thiếu ảnh {img_path}")
        bullets = spec.get("bullets") or []
        if bullets:
            # bullets trái + ảnh phải
            box = slide.shapes.add_textbox(Inches(0.5), Inches(2.3),
                                           Inches(4.3), Inches(4.5))
            n_bullets = fill_bullets_tf(box.text_frame, bullets, 20.0, 0.9, 6.0,
                                        4.3, 4.5, slide_no,
                                        candidates=[20.0], indent=False)
            # textbox thường không kế thừa body style của theme -> ép 20 pt
            set_runs_size(box.text_frame, 20.0)
            area = (5.0, 2.3, 7.83, 4.0)
        else:
            area = ((SLIDE_W_IN - 8.5) / 2, 2.3, 8.5, 4.0)
        add_image_with_caption(slide, img_path, spec.get("image_caption"),
                               area, slide_no)
        has_image = True
    elif spec.get("columns") and layout_idx == 3:
        for idx, col in zip((1, 2), spec["columns"]):
            ph = slide.placeholders[idx]
            w = ph.width / 914400
            h = ph.height / 914400
            n_bullets += fill_bullets_tf(ph.text_frame, col, base_pt, lnspc,
                                         spc_bef, w, h, slide_no)
    elif spec.get("bullets"):
        ph = slide.placeholders[1]
        w = ph.width / 914400
        h = ph.height / 914400
        n_bullets = fill_bullets_tf(ph.text_frame, spec["bullets"], base_pt,
                                    lnspc, spc_bef, w, h, slide_no)

    remove_unintended_empty_placeholders(slide)

    if spec.get("notes"):
        slide.notes_slide.notes_text_frame.text = spec["notes"]

    return {
        "no": slide_no,
        "layout": layout_idx,
        "title": spec["title"],
        "bullets": n_bullets,
        "image": has_image,
        "table": has_table,
    }


def validate(out_path: Path, specs, summaries):
    prs = Presentation(str(out_path))
    n = len(prs.slides._sldIdLst)
    assert len(specs) == 20, f"Số slide trong JSON != 20 ({len(specs)})"
    assert n == 20, f"Số slide trong pptx != 20 ({n})"
    problems = []
    for i, slide in enumerate(prs.slides, start=1):
        title = slide.shapes.title
        if title is None or not title.text_frame.text.strip():
            problems.append(f"Slide {i}: thiếu title.")
        for ph in slide.placeholders:
            if ph.placeholder_format.type in THEME_PH_TYPES:
                continue
            if ph.has_text_frame and not ph.text_frame.text.strip():
                problems.append(f"Slide {i}: placeholder idx "
                                f"{ph.placeholder_format.idx} bỏ trống.")
    for spec in specs:
        if spec.get("image"):
            p = REPO_ROOT / spec["image"]
            if not p.is_file():
                problems.append(f"Ảnh không tồn tại: {p}")
    if problems:
        for msg in problems:
            warn(msg)
        raise SystemExit("Kiểm tra thất bại.")
    print("Kiểm tra OK: đủ 20 slide, mọi slide có title, không placeholder trống "
          "ngoài ý muốn, ảnh tồn tại.")


def main(argv):
    json_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_JSON
    template_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_TEMPLATE
    out_path = Path(argv[3]) if len(argv) > 3 else DEFAULT_OUT

    specs = json.loads(json_path.read_text(encoding="utf-8"))["slides"]
    if len(specs) != 20:
        raise SystemExit(f"JSON phải có đúng 20 slide, hiện có {len(specs)}.")
    if not template_path.is_file():
        raise SystemExit(f"Thiếu template {template_path}; hãy chạy make_template.py trước.")

    base_pt, lnspc, spc_bef = theme_body_defaults(template_path)
    print(f"Body mặc định của theme: {base_pt:g} pt (lnSpc {lnspc:g}, "
          f"spcBef {spc_bef:g} pt).")

    prs = Presentation(str(template_path))
    # bỏ slide mẫu có sẵn (nếu có) để chỉ giữ slide của bộ nội dung
    from pptx.oxml.ns import qn
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst):
        prs.part.drop_rel(sldId.get(qn("r:id")))
        sldIdLst.remove(sldId)

    summaries = []
    for i, spec in enumerate(specs, start=1):
        summaries.append(build_slide(prs, spec, i, base_pt, lnspc, spc_bef))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    print(f"Đã xuất: {out_path}")

    validate(out_path, specs, summaries)

    print("\nTóm tắt bộ slide:")
    print(f"{'Slide':>5} | {'Layout':>6} | {'Bullets':>7} | {'Ảnh':>3} | "
          f"{'Bảng':>4} | Title")
    print("-" * 100)
    for s in summaries:
        title = s["title"] if len(s["title"]) <= 52 else s["title"][:49] + "..."
        print(f"{s['no']:>5} | {s['layout']:>6} | {s['bullets']:>7} | "
              f"{'x' if s['image'] else '-':>3} | {'x' if s['table'] else '-':>4} | {title}")

    if WARNINGS:
        print(f"\nTổng cộng {len(WARNINGS)} cảnh báo (xem ở trên).")
    else:
        print("\nKhông có cảnh báo tràn.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))