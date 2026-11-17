#!/usr/bin/env python3
"""Export DOCX/PPTX to PDF through the installed Office COM automation.

Usage:
    python docs/tools/office_to_pdf.py input.docx output.pdf
    python docs/tools/office_to_pdf.py input.pptx output.pdf

Requires Microsoft Word/PowerPoint and pywin32 (system Python on this machine).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pythoncom
import win32com.client


def export(src: Path, dst: Path) -> None:
    pythoncom.CoInitialize()
    try:
        if src.suffix.lower() == ".pptx":
            app = win32com.client.Dispatch("PowerPoint.Application")
            deck = app.Presentations.Open(str(src), WithWindow=False)
            try:
                deck.SaveAs(str(dst), 32)  # ppSaveAsPDF
            finally:
                deck.Close()
            app.Quit()
        else:
            app = win32com.client.Dispatch("Word.Application")
            app.Visible = False
            doc = app.Documents.Open(str(src))
            try:
                doc.SaveAs2(str(dst), FileFormat=17)  # wdFormatPDF
            finally:
                doc.Close(False)
            app.Quit()
        print(f"exported {dst}")
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    export(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())