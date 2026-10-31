# Bằng chứng thực thi (Evidence)

Ảnh chụp trong thư mục này dùng cho Chương 3–4 của báo cáo và video demo. Đặt tên theo mẫu `<chủ_đề>_<nội_dung>.png` và ghi ngày chụp khi thêm ảnh mới.

| Tệp | Chứng minh điều gì | Ngày chụp | Trạng thái |
|---|---|---|---|
| `ruleset_active.png` | Ruleset `main-1` đang bật, 4 rule, áp lên 1 nhánh (`main`) | 31/10/2026 | Hợp lệ |
| `ruleset_rules.png` | Chi tiết 4 rule: chặn xóa nhánh, yêu cầu PR, yêu cầu status check, chặn force push | 31/10/2026 | Hợp lệ |
| `push_blocked_main.png` | Push trực tiếp lên `main` bị từ chối: `GH013 ... Changes must be made through a pull request` | 31/10/2026 | Hợp lệ |
| `pr_review_merged.png` | PR #3 được `beloncuaem` approve và merge vào `main` (27 tệp, +1.496 dòng) | 31/10/2026 | Hợp lệ |
| `T16_alert_2026-10-31.md` | T16: tải nền 10 phút không báo nhầm; burst 200 decrypt bị phát hiện trong 0,4 giây | 31/10/2026 | Bản ghi terminal; cần ảnh chụp |
| `T03_T04_tamper_2026-10-31.md` | T03/T04: sửa ciphertext và tráo payload đều trả 503, audit ghi `decrypt_failed` | 31/10/2026 | Bản ghi terminal; cần ảnh chụp |
| `T09_T10_db_credentials_2026-10-31.md` | T09/T10: xoay credential DB dưới tải 0 lỗi; gia hạn/thu hồi lease hoạt động | 31/10/2026 | Bản ghi terminal; cần ảnh chụp |
| `T01_T05_T07_2026-10-31.md` | T01: round-trip đúng, DEK `vault:v1`, nonce 12 byte; T05: 401/401/403; T07: audit có decrypt + database creds, 0 plaintext | 31/10/2026 | Bản ghi terminal; cần ảnh chụp |
| `T11_T12_2026-10-31.md` | T11: 14 commit 0 leak, secret giả bị bắt; T12: ruleset `main-1` bắt buộc PR + 1 approval + `gitleaks`/`unit-tests` | 31/10/2026 | Bản ghi terminal; cần ảnh chụp |
| `T13_partial_2026-10-31.md` | T13: image không chứa secret; PostgreSQL `ssl=off`, chưa có TLS → **chưa đạt**, chờ SV1 | 31/10/2026 | Bản ghi một phần; cần ảnh chụp |
| `T06_T08_2026-10-31.md` | T06: checker FAIL do D-01 (policy còn rotate/read metadata); T08: chưa có rewrap/min version (D-03) → **chưa đạt** | 31/10/2026 | Bản ghi defect; cần ảnh chụp |

## Ghi chú

- Hai ảnh cũ `branch_protection.png` và `git_log.png` đã xóa ngày 31/10/2026 vì không chứng minh được trạng thái cuối (một ảnh chỉ là hộp thoại trước khi tạo ruleset, một ảnh mới có 1 tác giả và tag `v0.1`).
- `ruleset_rules.png` chưa mở rộng mục "Require a pull request before merging" nên chưa thấy số approval yêu cầu (1). Khi tiện, chụp thêm ảnh đã mở rộng mục này.
- Ruleset `main-1` đã gán hai required checks `gitleaks` và `unit-tests` ngày 31/10/2026 (xác nhận qua API, xem `T11_T12_2026-10-31.md`). Cần chụp lại màn hình Settings → Rules → `main-1` với mục status checks mở rộng.
- Ảnh lỗi PowerShell (`Set-Location ... 'liệu'`) là lỗi thao tác cục bộ, không phải bằng chứng kỹ thuật, không đưa vào báo cáo.

## Cần chụp bổ sung

- [ ] PR có CI check xanh (sau khi thêm workflow Gitleaks)
- [ ] Git log cuối dự án: đủ 3 tác giả, tag `v1.0.0`
- [ ] Bảng `sensitive_records` chỉ có `ciphertext`/`nonce`/`encrypted_dek`, không có plaintext
- [ ] `pg_dump` hoặc tìm kiếm plaintext trả 0 kết quả
- [ ] Log rotation KEK/DEK và thu hồi lease
- [ ] Kết quả k6: p50/p95/p99, RPS, error rate
- [ ] Audit log của Vault ghi nhận truy cập Transit/Database
- [ ] Ảnh chụp terminal T16 (dùng kèm `T16_alert_2026-10-31.md`)
