# E-lab — Xoay credential DB và KEK dưới tải 50 VUs (31/10/2026)

**Mục tiêu:** kiểm chứng H2 (tỷ lệ lỗi < 0,1% khi xoay vòng) ở mức tải cao hơn T09, đồng thời ghi nhận giới hạn của kiến trúc một worker.

## 1. Môi trường

| Thành phần | Giá trị |
|---|---|
| Máy | Windows, Docker Desktop, cùng ổ đĩa với baseline A và D-lab |
| API | `detai20-api-1`, 1 Uvicorn worker, pool SQLAlchemy 5+10 |
| Xác thực DB | `USE_VAULT_DB_CREDS=true` → Vault Database secrets engine, role `app-role` |
| Vault | Dev mode, HTTP nội bộ, KEK `app-data-key` |
| k6 | 0.54.0, `constant-vus`, 50 VUs, 3 phút/lần, 3 lần |
| Dữ liệu | Bảng `sensitive_records` đã tích lũy khoảng 190.000 bản ghi từ các lần đo trước |

Trước khi đo, API được recreate để chắc chắn đang dùng credential động:

```text
2026-10-31 14:41:04,868 INFO app.database Database connection initialized (Vault dynamic credentials=True)
```

## 2. Cách chạy

Mỗi lần 50 VUs/3 phút, luân phiên:

- phút thứ 1: `POST /admin/rotation/database` — sinh credential mới, kiểm tra `SELECT 1`, đổi pool;
- phút thứ 2: `POST /admin/rotation/transit-key` — xoay version KEK.

Request tải là 70% tạo bản ghi, 30% đọc, dùng app API key. Script: `/c/tmp/run_elab.sh` (không commit; chứa khóa admin cục bộ).

## 3. Kết quả k6

| Lần | Request | RPS | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | Error |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 13.701 | 75,93 | 566,81 | 1.222,68 | 1.668,78 | 3.330,53 | 0,00% |
| 2 | 13.955 | 77,34 | 555,73 | 1.183,01 | 1.608,78 | 3.351,08 | 0,00% |
| 3 | 14.740 | 81,67 | 531,22 | 1.123,69 | 1.516,11 | 3.230,83 | 0,00% |
| **Trung vị** | — | **77,34** | **555,73** | **1.183,01** | **1.608,78** | — | **0,00%** |

Nguồn: `bench/results/E-lab_50_run{1,2,3}.csv.gz` và `_summary.json`, phân tích bằng `bench/analyze.py`.

## 4. Kết quả xoay vòng

| Lần | Thao tác | Thời điểm | HTTP | Thời gian |
|---:|---|---|---:|---:|
| 1 | Xoay credential DB | 21:43:08 | 200 | 0,517 s |
| 1 | Xoay KEK | 21:44:09 | 200 | 0,207 s |
| 2 | Xoay credential DB | 21:46:10 | 200 | 0,500 s |
| 2 | Xoay KEK | 21:47:11 | 200 | 0,165 s |
| 3 | Xoay credential DB | 21:49:12 | 200 | 0,414 s |
| 3 | Xoay KEK | 21:50:13 | 200 | 0,164 s |

Phản hồi DB rotation:

```json
{"status":"rotated","message":"New requests use the new pool; the previous Vault lease is allowed to expire for in-flight work.","new_lease_duration_seconds":3600,"previous_lease_duration_seconds":3600}
```

Phản hồi KEK rotation:

```json
{"status":"rotated","key_name":"app-data-key","note":"This rotates the KEK version. It does not create new DEKs or re-encrypt existing payloads."}
```

API ghi nhận đúng 3 lần đổi pool:

```text
$ docker logs detai20-api-1 | grep -c "Switched database pool"
3
```

Không có phản hồi 5xx trong toàn bộ thời gian đo:

```text
$ docker logs detai20-api-1 | grep -cE 'HTTP/1.1" 5[0-9][0-9]'
0
```

## 5. Kết luận

- **H2 đạt:** 3/3 lần ở 50 VUs/3 phút với 6 lần xoay (3 DB + 3 KEK) đều có `http_req_failed = 0,00%`; không có 5xx.
- Không quan sát downtime: request đang chạy dùng pool cũ, request mới dùng pool mới; lease cũ hết hạn tự nhiên.
- **Lưu ý về KEK:** xoay KEK chỉ tăng version; bản ghi cũ vẫn giải mã được bằng version cũ. Chưa có rewrap và `min_decryption_version`, tức D-03 vẫn mở. Vì vậy kết quả này chứng minh "xoay không gián đoạn", không chứng minh "hoàn tất vòng đời khóa".
- **Giới hạn hiệu năng:** E-lab đạt 77,34 RPS trung vị, thấp hơn D-lab 50 VUs (110,55 RPS) và p95 cao hơn (1.183 ms so với 839 ms). Nguyên nhân có thể gồm API vừa recreate (cache lạnh), bảng đã ~190.000 bản ghi, và mỗi request giữ connection trong lúc gọi Vault. PostgreSQL ghi nhận 9 kết nối `idle in transaction`, 5 `idle`, 1 `active` cho role động — dấu hiệu connection bị giữ qua thời gian gọi Vault. Đây là quan sát, chưa phải phép đo nhân quả; không dùng để suy ra production.
- Cơ chế đổi pool là process-local; nhiều worker/replica sẽ cần cơ chế phối hợp riêng.
