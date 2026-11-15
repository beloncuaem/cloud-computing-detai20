# Chạy thật `scripts/smoke-test.ps1` và bằng chứng ảnh 14/11/2026

Người ghi: SV3 — Bùi Ngô Anh Quang (`beloncuaem`). Mọi lệnh dưới đây chạy thật trên clone cục bộ ngày 14/11/2026 (máy Windows 11, Docker Desktop daemon 29.7.2), trên `main` sau khi PR #10 merge (`c69d124`). Ảnh chụp là ảnh terminal thật / trang GitHub công khai, đặt trong `docs/evidence/`.

## 1. Vì sao có biên bản này

Biên bản 11/11 (`T06_T08_T15_2026-11-11.md`, mục 8.3) phải chạy smoke bằng **bản sao Python** của `smoke-test.ps1` vì phiên tự động bị execution policy chặn chạy `.ps1`. Biên bản này đóng khoảng trống đó: chạy **đúng tệp `.ps1` thật**, ghi nguyên nhân gốc của việc chặn, chứng minh không nới policy máy, và bổ sung đủ bộ ảnh thật cho checklist `README.md`.

## 2. Nguyên nhân gốc: execution policy Restricted, không phải lỗi tệp

- `Get-ExecutionPolicy -List` cho **mọi scope = Undefined** ⇒ policy hiệu lực = **Restricted**, chặn mọi `.ps1` kể cả trong shell tương tác. Đây là cấu hình máy, không phải lỗi của kịch bản.
- Tệp `scripts/smoke-test.ps1` **không** có `Zone.Identifier` (không bị Mark-of-the-Web), nên không phải do tải từ internet.
- Cách chạy được người dùng phê duyệt: **Bypass phạm vi tiến trình** cho đúng một lần chạy, không đổi policy máy/người dùng:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

- Sau khi chạy, kiểm tra lại `Get-ExecutionPolicy -List` vẫn mọi scope Undefined và `Get-ExecutionPolicy` = **Restricted** (in trong ảnh `smoke_ps1_2026-11-14.png`). Không sửa registry, không `Set-ExecutionPolicy`.

## 3. Dựng stack sạch và hai lần chạy smoke thật

- Dựng lại sạch: `docker compose down -v` rồi `up -d --build` (22:08:07 → 22:08:17); `vault-init` ExitCode = 0; api/postgres/vault healthy.
- **Lần 1 (22:17:30, chế độ credential DB tĩnh):** smoke thật 9/9 PASS. Lần này phát hiện `.env` đang để `USE_VAULT_DB_CREDS=false` (mặc định của `.env.example` bị giữ lại khi dựng lại), nên API dùng credential tĩnh và audit **không** có dòng `database/creds`.
- Khôi phục `USE_VAULT_DB_CREDS=true` trong `.env` (chế độ đúng cho T09/T10 và demo), `docker compose up -d api` dựng lại api (healthy sau 6s), xác nhận `settings.use_vault_db_creds = True`.
- **Lần 2 (22:36:11, chế độ credential DB động):** smoke thật 9/9 PASS, policy sau chạy vẫn Restricted. Ảnh commit là lần 2 (`smoke_ps1_2026-11-14.png`); ảnh lần 1 bị thay thế vì cùng nội dung 9/9 nhưng chế độ cũ.

Bản ghi 9/9 (nguyên văn từ ảnh lần 2):

```text
PASS  health endpoint
PASS  ready endpoint (DB + Vault)
PASS  create encrypted record
PASS  read back plaintext
PASS  metadata exposes ciphertext size
PASS  missing API key rejected
PASS  wrong API key rejected
PASS  record key cannot call admin
PASS  plaintext absent from database
Smoke test passed.
ExecutionPolicy hiệu lực SAU khi chạy = Restricted (không đổi cấu hình máy)
```

## 4. Khôi phục chế độ credential động và bằng chứng audit

Với `USE_VAULT_DB_CREDS=true`, API xin credential PostgreSQL động từ Vault mỗi lần cần, nên audit có dòng `database/creds/app-role`. Ảnh `vault_audit_transit_database.png` (22:36:33) cho thấy:

```text
time      type      path
15:35:53  request   database/creds/app-role
15:35:53  response  database/creds/app-role
15:36:10  request   transit/decrypt/app-data-key
15:36:10  response  transit/decrypt/app-data-key
Tổng dòng audit database/creds = 2
Tổng dòng audit transit/decrypt = 406
```

Số 406 là tổng tích lũy từ đầu phiên dựng lại 22:08 (gồm các burst T16 và các lượt decrypt của smoke/probe); không tách riêng từng nguồn trong biên bản này. Trước khi bật `true`, audit chỉ có `database/config/postgres` và `database/roles/app-role` (thao tác thiết lập), không có `database/creds` — đúng như cờ `false` giải thích, không phải lỗi chụp.

## 5. Các ảnh thật bổ sung ngày 14/11 (checklist README)

| Ảnh | Nội dung | Giờ chụp |
|---|---|---|
| `git_log_3_authors.png` | shortlog 3 email, graph, tag `v0.9.0-rc1`@`b333621`, HEAD `c69d124` | 22:13:32 |
| `smoke_ps1_2026-11-14.png` | smoke `.ps1` thật 9/9 + policy Restricted | 22:36:11 |
| `sensitive_records_schema.png` | `\d sensitive_records` chỉ ciphertext/nonce/encrypted_dek, 0 bản ghi | 22:17:48 |
| `pg_dump_no_plaintext.png` | probe duy nhất, 0 dòng pg_dump, dọn sạch sau dò | 22:17:53 |
| `rotation_lease_audit.png` | xoay KEK v1→v2 + rewrap (total=0 vì DB trống) + audit rotate + thu hồi lease | 22:18:17 |
| `k6_summary_median.png` | median p50/p95/p99/RPS/error + overhead H1 | 22:31:55 |
| `T16_alert_2026-11-14.png` | burst 200 decrypt, ALERT latency 0,3s, EXIT=2 | 22:32:41 |
| `vault_audit_transit_database.png` | audit database/creds + transit/decrypt | 22:36:33 |
| `pr10_ci_green.png` | PR #10 run #21 Success, gitleaks + unit-tests xanh | 22:38 |

Ảnh terminal chụp bằng helper chỉ lấy đúng vùng chữ nhật cửa sổ console đang chạy lệnh (ép topmost + kiểm tra foreground), kèm cổng kiểm tra số màu để loại ảnh nền/GUI; hai ảnh chụp nhầm cửa sổ riêng tư trong quá trình thử đã **xóa ngay, không commit**. `pr10_ci_green.png` chụp trang GitHub công khai (không đăng nhập) bằng trình duyệt.

## 6. Giới hạn và việc chưa kiểm chứng

- Ảnh k6 là bảng **median** của `bench/analyze.py` từ các phiên đo 31/10–11/11, không phải một lần chạy k6 mới ngày 14/11; không đo lại benchmark trong phiên này.
- T16 ngày 14/11 chạy lại burst 200 và alert (EXIT=2) trên stack hiện tại; không lặp lại phép tải nền 10 phút của bản 31/10.
- Xoay KEK ngày 14/11 đưa KEK lên v2 và rewrap total=0 (DB trống tại thời điểm xoay); trạng thái này khác phiên demo 31/10 (có bản ghi). Khi demo cần seeded data, gieo lại bằng smoke/record API.
- Chưa chụp ảnh mở rộng ruleset `main-1` (mục approval + status checks); việc đó cần thành viên ngồi trước máy.

## 7. Tái lập

```powershell
# tại gốc repo, stack đang chạy
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
Get-ExecutionPolicy -List          # mọi scope Undefined
Get-ExecutionPolicy                # Restricted
docker compose exec -T api python -c "from app.config import settings; print(settings.use_vault_db_creds)"
```