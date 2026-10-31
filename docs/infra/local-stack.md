# Stack Docker dự phòng — hướng dẫn vận hành

Stack này dựng PostgreSQL, Vault và API bằng một lệnh để SV3 có thể chạy T01–T16 trong lúc chờ SV1 bàn giao hạ tầng Vault file storage + TLS. **Đây là môi trường lab**, không thay thế stack của SV1 và không dùng cho dữ liệu thật.

## 1. Thành phần và giới hạn

| Thành phần | Image | Vai trò | Giới hạn lab |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | Lưu ciphertext, audit_events | Mật khẩu demo; không publish cổng ra host |
| `vault` | `hashicorp/vault:1.20` | Transit, Database engine, AppRole | Dev mode, storage trong RAM, HTTP, root token `root` |
| `vault-audit` | `hashicorp/vault:1.20` | Bật audit file `/tmp/vault-audit.log` | Log mất khi container Vault bị xóa |
| `vault-init` | build từ `student2_project_windows` | Chạy `setup_vault.py` một lần | Có root token + mật khẩu `vault_admin` |
| `api` | build từ `student2_project_windows` | FastAPI tại cổng 8000 | Chạy root trong container; không nhận root token |

Các rủi ro còn lại phải ghi vào báo cáo: Vault dev mode, TLS chưa bật, `vault_admin` là SUPERUSER, image chạy root, audit log tạm thời. Stack này không dùng để tuyên bố đã đạt T13.

## 2. Yêu cầu

- Docker Desktop đang chạy, Docker Compose v2 trở lên.
- Cổng 8000 còn trống (hoặc đặt `API_PORT` khác).
- Repository ở trạng thái có `docker-compose.yml`, `student2_project_windows/Dockerfile` và `scripts/smoke-test.ps1`.

Không cần cài Python, PostgreSQL hay Vault trên Windows.

## 3. Chạy stack

```powershell
# Từ thư mục gốc repository
docker compose up -d --build
docker compose ps
docker compose logs -f api
```

Lần đầu sẽ build image, pull PostgreSQL/Vault và chạy `vault-init`. Khi `api` healthy:

- API: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Ready: http://127.0.0.1:8000/ready

Kiểm tra nhanh:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

Smoke test kiểm tra health/ready, tạo bản ghi, đọc lại, metadata, 401/403 và tìm plaintext trong DB; sau đó xóa bản ghi test.

## 4. Biến môi trường

Compose đọc biến từ file `.env` ở thư mục gốc (đã bị `.gitignore`) hoặc từ môi trường shell:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `API_PORT` | `8000` | Cổng host của API |
| `API_KEY` | `local-demo-api-key-change-me` | API key cho `/records` |
| `ADMIN_API_KEY` | `local-demo-admin-key-change-me` | Admin key cho `/admin` |
| `USE_VAULT_DB_CREDS` | `false` | `true` để app dùng credential động của Vault |

Ví dụ bật dynamic DB credentials:

```powershell
"USE_VAULT_DB_CREDS=true" | Set-Content -Path .env -Encoding ascii
docker compose up -d --force-recreate api
docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/ready').read().decode())"
```

Tắt lại: sửa `.env` thành `false` rồi `docker compose up -d --force-recreate api`.

Không đặt mật khẩu thật trong `.env` của lab. Không commit `.env`.

## 5. Truy cập PostgreSQL và Vault

Cổng 5432/8200 không publish ra host để tránh xung đột với PostgreSQL/Vault native. Dùng `exec`:

```powershell
# PostgreSQL
docker compose exec -T postgres psql -U postgres -d encryption_db -c "\dt"
docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT id, record_type, octet_length(ciphertext) AS bytes, kek_version FROM sensitive_records LIMIT 5;"

# Vault (VAULT_TOKEN=root đã có trong container vault)
docker compose exec -T vault vault status
docker compose exec -T vault vault secrets list
docker compose exec -T vault vault read transit/keys/app-data-key
```

Muốn mở Vault UI tạm thời, thêm `ports: ["8201:8200"]` vào service `vault` trong một lần chạy cục bộ; không commit thay đổi đó.

## 6. Audit log

```powershell
docker compose exec -T vault sh -c "tail -n 5 /tmp/vault-audit.log"
docker compose exec -T vault sh -c "grep -a 'transit/decrypt' /tmp/vault-audit.log | tail -n 3"
docker compose cp vault:/tmp/vault-audit.log bench/results/audit_snapshot.log
```

Log audit có thể chứa token đã băm và metadata; không commit nguyên file. Chỉ trích đoạn đã lọc vào báo cáo.

## 7. Kiểm tra quyền AppRole

```powershell
docker compose exec -T api python scripts/check_approle_privileges.py
```

Hiện tại script sẽ FAIL vì policy trong `setup_vault.py` còn cấp `read` trên metadata khóa và `update` trên đường dẫn rotate (D-01). Đây là bằng chứng cho T06, không phải lỗi của stack. Sau khi SV2 sửa policy, chạy lại `docker compose run --rm vault-init` rồi chạy checker.

## 8. Xoay vòng

```powershell
# Xoay KEK (hiện app còn quyền; sau khi sửa D-01 nên dùng root/operator)
docker compose exec -T vault vault write -f transit/keys/app-data-key/rotate

# Rewrap sẽ do SV2 bổ sung; hiện chưa có
# docker compose exec -T api python scripts/rewrap_dek.py

# Xoay DEK cho toàn bộ bản ghi
docker compose exec -T api python scripts/rotate_dek.py

# Xoay credential DB động (cần USE_VAULT_DB_CREDS=true)
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/admin/rotation/database" `
  -Headers @{ "X-Admin-Key" = "local-demo-admin-key-change-me" }
```

Ghi lại thời điểm và theo dõi k6 trong lúc xoay. Không dùng `rotate_transit_key.py` để tuyên bố đã rewrap; script đó chỉ tạo version mới.

## 9. Sinh tải giải mã và cảnh báo

```powershell
# (tuỳ chọn) xoá log cũ để phép đo chỉ chứa lưu lượng của lần chạy này
docker compose exec -T vault sh -c "export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root; vault audit disable file/; rm -f /tmp/vault-audit.log; vault audit enable file file_path=/tmp/vault-audit.log"

# 1) Tải nền 10 phút qua API (identity audit = approle), phải KHÔNG cảnh báo
docker run --rm -i --network detai20_default -e BASE_URL=http://api:8000 `
  -e VUS=5 -e SLEEP=2 -e DURATION=10m `
  -v "${PWD}/bench/k6:/scripts" grafana/k6:0.54.0 run /scripts/mixed.js

# 2) Burst 200 lần giải mã bằng token root (identity tách khỏi AppRole của app)
docker compose run --rm --no-deps vault-init python scripts/generate_decrypt_load.py --count 200

docker compose cp vault:/tmp/vault-audit.log bench/results/audit_attack.log

docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python student2_project_windows/scripts/alert_decrypt_rate.py `
  --log bench/results/audit_attack.log --threshold 200 --window 60
```

`alert_decrypt_rate.py` trả mã 2 khi có cảnh báo. Lần chạy sạch sẽ cho kết quả `OK identity=approle ...` và `ALERT identity=token ...`: tải nền không gây false positive, burst bằng danh tính khác bị phát hiện. Nếu `approle` cũng vượt ngưỡng, ghi nhận false positive và hiệu chỉnh ngưỡng theo baseline T14 trước khi kết luận T16 đạt. Đặt `SLEEP` để giãn nhịp; `SLEEP=0` là mặc định cho benchmark hiệu năng.

## 10. Reset và khôi phục

```powershell
# Xóa toàn bộ container + volume (mất dữ liệu lab)
docker compose down -v --remove-orphans
docker compose up -d --build
```

Nếu chỉ Vault bị restart (mất state dev):

```powershell
docker compose up -d --force-recreate vault vault-audit
docker compose run --rm vault-init
docker compose restart api
```

Nếu `vault-init` báo lỗi đăng nhập PostgreSQL, kiểm tra `postgres` healthy và role `vault_admin` đã được tạo bởi `sql/00-create-roles.sql`. Nếu API không ready, xem `docker compose logs api` và `docker compose logs vault-init`.

## 11. Dọn dẹp

```powershell
docker compose down -v --remove-orphans
docker image rm detai20-api:local 2>$null
docker system df
```

Ghi lại thời gian dựng lại và dung lượng image/volume cho T15. Không xóa volume của dự án khác.

## 12. Liên kết với kế hoạch kiểm thử

- T01–T05, T07: chạy trực tiếp trên stack này.
- T06: `check_approle_privileges.py` (hiện FAIL do D-01).
- T08: cần SV2 bổ sung rewrap và `min_decryption_version`.
- T09–T10: bật `USE_VAULT_DB_CREDS=true`, dùng lệnh trong test plan.
- T11–T12: chạy trên Git/GitHub, không phụ thuộc stack.
- T13: **chưa đạt** với stack này; chờ SV1.
- T14: dùng `bench/k6/mixed.js`; ghi rõ `D-lab` nếu chưa có TLS.
- T15: mục 10–11 ở trên.
- T16: mục 9 ở trên.

Chi tiết từng ca nằm trong `docs/testing/test-plan.md`.
