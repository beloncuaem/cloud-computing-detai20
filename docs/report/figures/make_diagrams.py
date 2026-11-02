#!/usr/bin/env python3
"""Draw the two architecture figures used in the report.

Usage:
    pip install matplotlib
    python docs/report/figures/make_diagrams.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent
BLUE = "#DCE9F7"
GREEN = "#DFF0D8"
ORANGE = "#FCE5CD"
GREY = "#EEEEEE"
EDGE = "#555555"


def box(ax, x, y, w, h, text, face=GREY, fontsize=9):
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.0, edgecolor=EDGE, facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize)
    return patch


def arrow(ax, start, end, text="", color=EDGE, style="-|>", offset=(0, 0.1)):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle=style, mutation_scale=12,
            linewidth=1.2, color=color, shrinkA=4, shrinkB=4,
        )
    )
    if text:
        mx = (start[0] + end[0]) / 2 + offset[0]
        my = (start[1] + end[1]) / 2 + offset[1]
        ax.text(mx, my, text, ha="center", va="bottom", fontsize=7.5, color="#333333")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    # Docker network boundary
    boundary = FancyBboxPatch(
        (2.25, 0.35), 7.55, 5.25, boxstyle="round,pad=0.02,rounding_size=0.1",
        linewidth=1.0, linestyle="--", edgecolor="#888888", facecolor="#FAFAFA",
    )
    ax.add_patch(boundary)
    ax.text(9.7, 0.5, "Docker network detai20_default", ha="right", fontsize=8, color="#666666")

    box(ax, 0.15, 2.45, 1.55, 1.0, "Client\n(dữ liệu giả)", face=GREY)
    box(ax, 2.65, 2.3, 2.25, 1.55, "FastAPI\n1 Uvicorn worker\nX-API-Key", face=BLUE, fontsize=9)
    box(
        ax, 6.15, 3.55, 3.25, 1.55,
        "Vault 1.20 (dev mode)\nAppRole · Transit (KEK)\nDatabase secrets engine",
        face=ORANGE, fontsize=9,
    )
    box(ax, 6.15, 1.15, 3.25, 1.45, "PostgreSQL 16\nsensitive_records · audit_events", face=GREEN, fontsize=9)

    # Client -> API, label above the gap between the boxes.
    arrow(ax, (1.7, 2.95), (2.65, 2.95))
    ax.text(2.42, 3.08, "HTTP", ha="center", va="bottom", fontsize=7.5, color="#333333")

    # API -> Vault (auth + transit).
    arrow(ax, (4.9, 3.45), (6.15, 4.25))
    ax.text(5.02, 4.05, "AppRole login\nTransit: datakey / decrypt", ha="right", va="center", fontsize=7.5, color="#333333")

    # Vault -> PostgreSQL (create a temporary role).
    arrow(ax, (7.75, 3.55), (7.75, 2.6))
    ax.text(7.88, 3.08, "tạo role tạm", ha="left", va="center", fontsize=7.5, color="#333333")

    # API -> PostgreSQL (query with the dynamic credential).
    arrow(ax, (4.9, 2.65), (6.15, 2.05))
    ax.text(5.35, 1.9, "SQL với credential động\n(lease 1 giờ)", ha="center", va="top", fontsize=7.5, color="#333333")

    ax.text(2.65, 1.25, "Không giữ root token;\nkhông lưu plaintext", fontsize=8, color="#444444")
    ax.set_title("Kiến trúc target D-lab: ứng dụng, Vault và PostgreSQL", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "fig_architecture.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def envelope() -> None:
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    box(ax, 0.2, 3.15, 1.55, 0.75, "Plaintext\n+ AAD", face=GREY, fontsize=9)
    box(ax, 2.25, 3.15, 1.95, 0.75, "AES-256-GCM", face=BLUE, fontsize=9)
    box(ax, 4.7, 3.15, 1.7, 0.75, "Ciphertext\n+ nonce", face=GREEN, fontsize=8.5)

    box(ax, 2.25, 1.35, 1.55, 0.75, "DEK ngẫu nhiên", face=BLUE, fontsize=8.5)
    box(ax, 4.15, 1.35, 1.65, 0.75, "Vault Transit\nwrap DEK", face=ORANGE, fontsize=8.5)
    box(ax, 6.15, 1.35, 1.75, 0.75, "encrypted_dek\nvault:vN:...", face=ORANGE, fontsize=8.5)

    box(
        ax, 8.6, 1.5, 2.2, 2.6,
        "Một dòng trong\nsensitive_records\n\nciphertext · nonce\nencrypted_dek\nkek_name\nkek_version",
        face=GREEN, fontsize=8.5,
    )

    arrow(ax, (1.75, 3.52), (2.25, 3.52))
    arrow(ax, (4.2, 3.52), (4.7, 3.52), "mã hóa", offset=(0, 0.06))

    # DEK is used by AES-GCM and then wrapped by Transit.
    arrow(ax, (3.05, 2.1), (3.05, 3.15), "dùng DEK", offset=(0.5, 0.05))
    arrow(ax, (3.8, 1.72), (4.15, 1.72))
    arrow(ax, (5.8, 1.72), (6.15, 1.72))

    arrow(ax, (6.4, 3.5), (8.6, 3.5), "lưu", offset=(0, 0.06))
    arrow(ax, (7.9, 1.9), (8.6, 1.9), "lưu", offset=(0, 0.06))

    ax.text(3.0, 0.55, "KEK chỉ nằm trong Vault; DB chỉ thấy bản DEK đã bọc", fontsize=8.5, color="#333333")
    ax.set_title("Mã hóa phong bì: DEK mã hóa dữ liệu, KEK bọc DEK", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "fig_envelope.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    architecture()
    envelope()
    print(f"wrote {OUT / 'fig_architecture.png'}")
    print(f"wrote {OUT / 'fig_envelope.png'}")


if __name__ == "__main__":
    main()
