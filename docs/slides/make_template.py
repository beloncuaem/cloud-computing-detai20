#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sinh template PowerPoint chuẩn UTH từ file theme .thmx.

File .thmx là package OPC nhưng dùng tiền tố part `theme/` thay vì `ppt/`.
Script này (chỉ stdlib + zipfile) đổi tên part và sửa [Content_Types].xml,
_rels/.rels để python-pptx mở được như một presentation bình thường.

Cách chạy (system python, có python-pptx để kiểm tra nếu muốn):
    python -X utf8 docs/slides/make_template.py [duong-dan.thmx] [dau-ra.pptx]

Mặc định:
    đầu vào : docs/slides/UTH-Slide-Theme.thmx (kèm repo)
    đầu ra  : docs/slides/uth-template.pptx (cạnh script này)
"""

import sys
import zipfile
from pathlib import Path

DEFAULT_THMX = str(Path(__file__).resolve().parent / "UTH-Slide-Theme.thmx")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = SCRIPT_DIR / "uth-template.pptx"

OLD_PREFIX = "theme/"
NEW_PREFIX = "ppt/"


def convert(thmx_path: Path, out_path: Path) -> int:
    """Đổi tiền tố part theme/ -> ppt/ và sửa 2 file khai báo. Trả về số part."""
    thmx_path = Path(thmx_path)
    out_path = Path(out_path)
    if not thmx_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file theme: {thmx_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(thmx_path, "r") as zin:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                name = info.filename
                data = zin.read(name)

                # Đổi tên part: theme/... -> ppt/...
                new_name = name
                if name.startswith(OLD_PREFIX):
                    new_name = NEW_PREFIX + name[len(OLD_PREFIX):]

                if name == "[Content_Types].xml":
                    data = data.replace(b"/theme/", b"/ppt/")
                elif name == "_rels/.rels":
                    data = data.replace(
                        b'Target="theme/theme/themeManager.xml"',
                        b'Target="ppt/presentation.xml"',
                    )

                zout.writestr(new_name, data)
                count += 1
    return count


def main(argv) -> int:
    thmx = Path(argv[1]) if len(argv) > 1 else Path(DEFAULT_THMX)
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    n = convert(thmx, out)
    print(f"Đã sinh template: {out}")
    print(f"Số part: {n} (nguồn: {thmx})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))