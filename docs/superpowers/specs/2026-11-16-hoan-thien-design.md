# Thiết kế: hoàn thiện Đề tài 20 + báo cáo tổng hợp UTH + slide + kịch bản

Ngày: 2026-11-16 · Tác giả: SV3 (Bùi Ngô Anh Quang, MSSV 066206019831) · Nhánh: `feat/t13-benchmark-bao-cao-uth` (worktree `wt-hoanthien`, nền `origin/main` = `dd287d1`)

## 0. Quyết định đã duyệt với người dùng

1. Phạm vi: **đóng thật cả T13 và benchmark** (không risk-accepted cho T13/D').
2. Hình thức bảo vệ: **thuyết trình trực tiếp bằng slide**, không làm video. Giữ nguyên quyết định "không nộp video" của repo.
3. Thời hạn: nộp trong 1–2 ngày; **chạy lab trước, tài liệu sau**.
4. Bìa: lấy bố cục từ `066206019831_BUINGOANHQUANG.docx`; **tên viện và GVHD để trống placeholder** cho người dùng tự điền. Năm học 2026–2027, HK1.
5. Phương án 1: lab → tài liệu, một worktree tích hợp, **2 PR**.
6. Ownership: infra T13 ưu tiên commit mang tên SV1 nếu Thiên Phú commit kịp; nếu không SV3 commit và báo cáo ghi "SV3 hỗ trợ hạ tầng". Bench/docs mang tên SV3.
7. BitLocker: probe ổ C:. Nếu `Protection On` → đo cấu hình C. Nếu tắt → **risk-accepted có văn bản**, không tự bật BitLocker.
8. MSSV SV3 dùng `066206019831` (theo file bìa chính thức), không dùng `0662060198831` trong lời nhắn.

## 1. Nhánh và PR (mục 1 đã duyệt)

- Worktree `../wt-hoanthien`, nhánh `feat/t13-benchmark-bao-cao-uth`. Clone chính và nhánh PR #14 không đụng.
- PR 1 `feat/t13-va-benchmark`: hạ tầng TLS + kết quả B/C/D/D'/E + `analyze.py`.
- PR 2 `docs/bao-cao-slide-kich-ban`: báo cáo, slide, kịch bản, đồng bộ sơ đồ/demo/infra doc.
- Secret: `certs/` gitignored, chỉ commit script sinh cert; kết quả k6 không chứa API key.
- Deliverable: `docs/report/bao-cao-tong-hop.docx` + `.pdf`, `docs/slides/de-tai-20.pptx`, `docs/slides/kich-ban-thuyet-trinh.md`.

## 2. T13 (mục 2 đã duyệt)

- `infrastructure/certs/gen-certs.sh`: openssl sinh CA lab + cert server `vault`, `nginx`, `postgres`; SAN `localhost,127.0.0.1,vault,api,postgres`; 365 ngày.
- Vault: dev mode + `-dev-tls -dev-tls-cert-dir` → `https://vault:8200`. Giữ nguyên AppRole/Transit. `infrastructure/vault/config/vault.hcl` sửa cert path, giữ làm biến thể production-intent (file storage), ghi rõ chưa nghiệm thu.
- nginx: service mới trong stack gốc, `8443` TLS → `api:8000`, `8444` TLS → `baseline:8001`. Sửa `infrastructure/nginx/conf.d/default.conf`; compose SV1 thêm service `api` + PG16.
- PostgreSQL: `ssl=on` với cert mount; API `sslmode=require`.
- Nghiệm thu: 5 lệnh T13 (test-plan L498–503) + check secret-không-trong-image (L511–512); transcript vào `docs/evidence/T13_2026-11-16.md`; `openssl s_client` chứng minh TLS 1.2+.

## 3. Benchmark (mục 3)

- Sau khi có TLS, đo nhãn **thật**: B (TLS, plaintext baseline), C (TLS + volume, chỉ nếu BitLocker on), D (TLS + envelope), D' (D + `DEK_CACHE_TTL_SECONDS=120`), E (D + rotation). A giữ kết quả cũ.
- Mỗi cấu hình: warm-up 60 s, rồi **5 lần × {10, 50, 100} VU × 3 phút**, restart stack trước mỗi cấu hình. D' đặt cache 120; các cấu hình khác cache 0.
- Orchestrator chạy nền ghi `bench/results/<cfg>_<vus>_run<N>.csv` + `_summary.json`; không chạy song song hai cấu hình.
- `bench/analyze.py`: mở rộng tập target so sánh overhead từ `("D","D-lab")` sang `("B","C","D","D'","E")`; giữ nhãn `D-lab`/`E-lab` cũ trong bảng lịch sử, không ghi đè.
- Nếu BitLocker tắt: không đo C; báo cáo ghi C là risk-accepted và T14 vẫn "đạt một phần" cho C.
- Kết quả đưa vào Chương 4 + biểu đồ `bench/plot_results.py`; mọi khẳng định H1/H2 cập nhật theo số liệu mới.

## 4. Báo cáo tổng hợp (mục 4)

- Nâng cấp `docs/report/bao-cao-ky-thuat.md` (516 dòng, PDF 31 trang) thành `bao-cao-tong-hop`:
  - Thêm: TÓM TẮT, DANH MỤC TỪ VIẾT TẮT, DANH MỤC HÌNH ẢNH, DANH MỤC BẢNG BIỂU.
  - Tham khảo chuyển IEEE, đánh số `[n]` và trích dẫn trong thân bài.
  - Đánh số mọi bảng; hình giữ số hiện có + hình mới.
  - Sửa mâu thuẫn: 1 worker → 2 worker, pool 5+10 → 20+20, `vault_admin` SUPERUSER → NOSUPERUSER + `SET FALSE`; cập nhật `make_diagrams.py`.
  - Chương 4 thay số liệu `D-lab` bằng B/C/D/D'/E thật; thêm mục T13 và at-rest.
  - Đồng bộ `docs/demo/kich-ban-demo-truc-tiep.md`, `docs/infra/local-stack.md` sang 2 worker/NOSUPERUSER; điền nhật ký rehearsal.
- Bìa UTH theo bố cục file docx: 3 dòng BỘ XÂY DỰNG / TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI TP.HCM / `[TÊN VIỆN — tự điền]`, logo, tên đề tài, khối 3 SV + MSSV, `GIẢNG VIÊN HƯỚNG DẪN: ………`, năm học. Times New Roman.
- Xuất DOCX (pandoc + reference-doc bìa) và PDF (Word COM); **kiểm soát 20–35 trang**, cắt phụ lục nếu vượt.
- Phụ lục nhúng nội dung thật (không chỉ trỏ đường dẫn).

## 5. Slide + kịch bản (mục 5)

- `.thmx` → `template.pptx`: thêm `ppt/presentation.xml` + rels + content-types vào gói theme; giữ nguyên slideMaster/11 layout/logo/màu `008080`/`C00000`/`15848B`.
- ~20 slide, 15 phút: mở đầu (1–3), hạ tầng SV1 (4–7), ứng dụng + envelope SV2 (8–12), DevSecOps + benchmark SV3 (13–18), kết luận + phản biện (19–20).
- `docs/slides/kich-ban-thuyet-trinh.md`: lời nói từng slide, thời lượng, phân vai, cue demo trực tiếp (nối từ kịch bản demo, rút gọn còn ~4 phút), Q&A dự kiến.
- Kiểm chứng: mở .pptx bằng python-pptx đếm slide/layout; render PDF bằng Word COM để soát tràn chữ.

## 6. Kiểm chứng cuối

`pytest -q` 16/16; gitleaks 0 leak trên cả 2 PR; CI `security-gate` xanh đúng head; PDF 20–35 trang; slide mở được; `docker compose down -v && up -d --build` dựng lại được từ mã đã commit (D-09).