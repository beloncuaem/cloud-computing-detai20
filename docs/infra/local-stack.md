# Stack Docker dự phòng — hướng dẫn vận hành

Stack này dựng PostgreSQL, Vault, API và nginx (TLS terminator) bằng một lệnh để cả nhóm chạy T01–T16. Từ 16/11/2026 stack đã có TLS ở biên ngoài (nginx 8200/8443/8444, chứng chỉ tự ký) và PostgreSQL `ssl=on`; biến thể Vault file storage + TLS native (production-intent, `infrastructure/`) vẫn chưa nghiệm thu. **Đây là môi trường lab**, không dùng cho dữ liệu thật.

## 1. Thành phần và giới hạn

| Thành phần | Image | Vai trò | Giới hạn lab |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | Lưu ciphertext, audit_events; `ssl=on`, cert/key từ volume `pgcerts` | Mật khẩu demo; không publish cổng 5432 ra host |
| `vault` | `hashicorp/vault:1.20` | Transit, Database engine, AppRole | Dev mode, storage trong RAM, HTTP **nội bộ** (D-04), root token `root`; TLS ở biên qua nginx 8200 |
| `vault-audit` | `hashicorp/vault:1.20` | Bật audit file `/tmp/vault-audit.log` | Log mất khi container Vault bị xóa |
| `vault-init` | build từ `api` | Chạy `setup_vault.py` một lần | Có root token + mật khẩu `vault_admin` |
| `api` | build từ `api` | FastAPI, 2 Uvicorn worker; plaintext 8000 (fallback lab), TLS qua nginx 8443 | Chạy root trong container; không nhận root token |
| `pgcerts` | `alpine:3.20` | One-shot copy cert vào named volume `pgcerts`, chmod 600 + chown 70:70 cho key | Bind mount Windows không giữ được permission key mà PostgreSQL đòi hỏi |
| `nginx` | `nginx:1.27-alpine` | TLS terminator: 8200→vault:8200, 8443→api:8000, 8444→baseline:8001; TLSv1.2/1.3, cipher ECDHE | Chứng chỉ tự ký; container baseline có thể chưa chạy (cổng 8444) |

Các rủi ro còn lại phải ghi vào báo cáo: Vault dev mode (HTTP nội bộ sau nginx — chủ đích lab theo D-04), image chạy root, audit log tạm thời, chứng chỉ tự ký chưa có quy trình thu hồi. At-rest cấp volume: BitLocker Off (probe UAC 16/11), **risk-accepted bằng văn bản** — không đo cấu hình C. `vault_admin` không còn SUPERUSER (D-05): `LOGIN CREATEROLE NOINHERIT`, grant `app_writer TO vault_admin WITH ADMIN TRUE, SET FALSE` để chặn leo thang qua `SET ROLE` (sửa trong PR #14 đang chờ merge; worktree này đã cherry-pick). T13 **ĐẠT phần TLS** ngày 16/11 — bằng chứng `docs/evidence/T13_2026-11-16.md`.

## 2. Yêu cầu

- Docker Desktop đang chạy, Docker Compose v2 trở lên.
- Cổng 8000 (plaintext fallback, hoặc đặt `API_PORT` khác), 8200, 8443, 8444 còn trống.
- `openssl` >= 3 để sinh chứng chỉ lab (Git Bash có sẵn; cần `MSYS_NO_PATHCONV=1` để tham số dạng `/...` không bị đổi thành đường dẫn Windows).
- Repository ở trạng thái có `docker-compose.yml`, `api/Dockerfile`, `infrastructure/certs/gen-certs.sh` và `scripts/smoke-test.ps1`.

Không cần cài Python, PostgreSQL hay Vault trên Windows.

## 3. Chạy stack

Sinh chứng chỉ lab trước lần dựng đầu tiên (CA riêng + cert server cho nginx/postgres/vault, SAN `localhost`/`nginx`/`api`/`127.0.0.1`; output `infrastructure/certs/out/` đã gitignore, không commit key):

```bash
# Git Bash
MSYS_NO_PATHCONV=1 bash infrastructure/certs/gen-certs.sh
```

```powershell
# Từ thư mục gốc repository
Copy-Item .env.example .env   # rồi điền API_KEY / ADMIN_API_KEY vào file .env
docker compose up -d --build
docker compose ps
docker compose logs -f api
```

`docker compose` sẽ báo lỗi ngay nếu `API_KEY` hoặc `ADMIN_API_KEY` trống; mã nguồn không còn key cài sẵn.

Lần đầu sẽ build image, pull PostgreSQL/Vault/nginx, chạy one-shot `pgcerts` (copy cert vào named volume, chmod 600 + chown 70:70 cho key) và `vault-init`. Khi `api` healthy, các endpoint chính đi qua TLS (nginx terminator, chứng chỉ tự ký nên cần `-k`):

- API: https://127.0.0.1:8443/docs
- Health: https://127.0.0.1:8443/health
- Ready: https://127.0.0.1:8443/ready
- Vault API/UI: https://127.0.0.1:8200 (nginx → HTTP nội bộ tới vault:8200)
- Baseline benchmark: https://127.0.0.1:8444 (→ baseline:8001, chỉ khi container baseline chạy)

Cổng plaintext `http://127.0.0.1:8000` vẫn publish — **đây là fallback lab để debug, không phải biên production**; demo và đo đạc chính thức đi qua https 8443.

Kiểm tra nhanh qua TLS:

```powershell
curl.exe -k -i https://127.0.0.1:8443/health
curl.exe -k -i https://127.0.0.1:8443/ready
curl.exe -k -s https://127.0.0.1:8200/v1/sys/health
```

Smoke test đầy đủ (health/ready, tạo bản ghi, đọc lại, metadata, 401/403, tìm plaintext trong DB, xóa bản ghi test) mặc định chạy trên fallback plaintext 8000:

```powershell
$env:API_KEY = "<giá trị API_KEY trong file .env>"
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

Muốn smoke qua https bằng PowerShell 5.1 (không có `-SkipCertificateCheck`), tin CA lab trong store người dùng rồi truyền `-BaseUrl`:

```powershell
Import-Certificate -FilePath infrastructure/certs/out/ca.crt -CertStoreLocation Cert:\CurrentUser\Root
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 -BaseUrl https://127.0.0.1:8443
# Gỡ CA sau khi xong:
Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -eq "CN=UTH Lab CA" } | Remove-Item
```

## 4. Biến môi trường

Compose đọc biến từ file `.env` ở thư mục gốc (đã bị `.gitignore`) hoặc từ môi trường shell:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `API_PORT` | `8000` | Cổng host plaintext của API (fallback lab) |
| `API_KEY` | không có — bắt buộc | API key cho `/records` |
| `ADMIN_API_KEY` | không có — bắt buộc | Admin key cho `/admin` |
| `USE_VAULT_DB_CREDS` | `false` | `true` để app dùng credential động của Vault (bật khi đo) |
| `DB_SSLMODE` | `require` | SSL mode kết nối PostgreSQL (`DATABASE_URL` cũng gắn `?sslmode=require`) |
| `UVICORN_WORKERS` | `2` | Số Uvicorn worker của API |
| `DB_POOL_SIZE` | `20` | Kích thước pool connection SQLAlchemy |
| `DB_MAX_OVERFLOW` | `20` | Số connection vượt pool tối đa |
| `DEK_CACHE_TTL_SECONDS` | `0` | Cache DEK **tắt mặc định** (giữ T08 trung thực); đặt 120+ chỉ khi đo cấu hình D' |
| `DEK_CACHE_MAX_ENTRIES` | `1024` | Số entry tối đa của cache DEK |

Ví dụ bật dynamic DB credentials:

```powershell
@'
API_KEY=<key-cua-ban>
ADMIN_API_KEY=<admin-key-cua-ban>
USE_VAULT_DB_CREDS=true
'@ | Set-Content -Path .env -Encoding ascii
docker compose up -d --force-recreate api
docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/ready').read().decode())"
```

Tắt lại: sửa `.env` thành `false` rồi `docker compose up -d --force-recreate api`.

Không đặt mật khẩu thật trong `.env` của lab. Không commit `.env`.

## 5. Truy cập PostgreSQL và Vault

Cổng 5432 không publish ra host để tránh xung đột với PostgreSQL native. Vault đã truy cập được qua TLS tại https://localhost:8200 (nginx terminator); bản thân Vault vẫn HTTP nội bộ trong network Docker — chủ đích lab theo D-04. Dùng `exec` cho thao tác quản trị:

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

Vault UI/API dùng qua https://localhost:8200 (nginx → vault:8200), không cần mở thêm cổng. Biến thể production-intent dùng TLS native trong `infrastructure/vault/config/vault.hcl` (chưa nghiệm thu).

## 6. Audit log

```powershell
docker compose exec -T vault sh -c "tail -n 5 /tmp/vault-audit.log"
docker compose exec -T vault sh -c "grep -a 'transit/decrypt' /tmp/vault-audit.log | tail -n 3"
docker compose cp vault:/tmp/vault-audit.log bench/results/audit_snapshot.log
```

Log audit có thể chứa token đã băm và metadata; không commit nguyên file. Chỉ trích đoạn đã lọc vào báo cáo.

## 7. Kiểm tra quyền AppRole

```powershell
docker compose run --rm --no-deps --entrypoint python vault-init scripts/show_approle_lifecycle.py
docker compose exec -T api python scripts/check_approle_privileges.py
docker compose exec -T api python scripts/prove_rotate_forbidden.py
docker compose exec -T api python scripts/prove_secret_id_reuse.py
```

Policy workload không còn `update` trên rotate và không còn `read` trên metadata khóa. SecretID của workload là 10 phút và một lần dùng. Sau khi dựng lại stack (`docker compose up -d --build`, để `vault-init` ghi policy mới), cả bốn lệnh phải in PASS và thoát 0.

## 8. Xoay vòng

```powershell
# Xoay KEK bằng danh tính operator (file này không nằm trong container api)
docker compose run --rm --no-deps --entrypoint python vault-init scripts/rotate_transit_key.py

# Rewrap DEK sang version KEK mới, bằng quyền rewrap của workload
docker compose exec -T api python scripts/rewrap_dek.py

# Chặn giải mã ciphertext của version cũ
docker compose run --rm --no-deps --entrypoint python vault-init scripts/set_min_decryption_version.py 2

# Xoay DEK cho toàn bộ bản ghi (giải mã payload và mã hóa lại, khác rewrap)
docker compose exec -T api python scripts/rotate_dek.py

# Xoay credential DB động (cần USE_VAULT_DB_CREDS=true) — qua TLS, cert tự ký nên dùng curl -k
curl.exe -k -X POST https://127.0.0.1:8443/admin/rotation/database -H "X-Admin-Key: $env:ADMIN_API_KEY"
```

Ghi lại thời điểm và theo dõi k6 trong lúc xoay. Không dùng `rotate_transit_key.py` để tuyên bố đã rewrap; script đó chỉ tạo version mới.

## 9. Sinh tải giải mã và cảnh báo

```powershell
# (tuỳ chọn) xoá log cũ để phép đo chỉ chứa lưu lượng của lần chạy này
docker compose exec -T vault sh -c "export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root; vault audit disable file/; rm -f /tmp/vault-audit.log; vault audit enable file file_path=/tmp/vault-audit.log"

# 1) Tải nền 10 phút qua API (identity audit = approle), phải KHÔNG cảnh báo
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=https://host.docker.internal:8443 `
  -e API_KEY=$env:API_KEY `
  -e VUS=5 -e SLEEP=2 -e DURATION=10m bench/k6/mixed.js

# 2) Burst 200 lần giải mã bằng token root (identity tách khỏi AppRole của app)
docker compose run --rm --no-deps vault-init python scripts/generate_decrypt_load.py --count 200

docker compose cp vault:/tmp/vault-audit.log bench/results/audit_attack.log

docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python api/scripts/alert_decrypt_rate.py `
  --log bench/results/audit_attack.log --threshold 200 --window 60
```

`bench/k6/mixed.js` đặt `insecureSkipTLSVerify: true` nên chấp nhận CA tự ký của lab khi chạy qua https; baseline (cấu hình B) đo qua `https://host.docker.internal:8444`.

`alert_decrypt_rate.py` trả mã 2 khi có cảnh báo. Lần chạy sạch sẽ cho kết quả `OK identity=approle ...` và `ALERT identity=token ...`: tải nền không gây false positive, burst bằng danh tính khác bị phát hiện. Nếu `approle` cũng vượt ngưỡng, ghi nhận false positive và hiệu chỉnh ngưỡng theo baseline T14 trước khi kết luận T16 đạt. Đặt `SLEEP` để giãn nhịp; `SLEEP=0` là mặc định cho benchmark hiệu năng.

## 10. Reset và khôi phục

```powershell
# Xóa toàn bộ container + volume (mất dữ liệu lab)
docker compose down -v --remove-orphans
docker compose up -d --build
```

Nếu `infrastructure/certs/out/` đã bị xóa, sinh lại cert (mục 3) trước khi `up`; container one-shot `pgcerts` sẽ copy lại cert vào named volume sau mỗi lần dựng.

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
- T06: `check_approle_privileges.py` và `prove_rotate_forbidden.py`.
- T08: `rotate_transit_key.py` (operator), `rewrap_dek.py`, `set_min_decryption_version.py`.
- T09–T10: bật `USE_VAULT_DB_CREDS=true`, dùng lệnh trong test plan.
- T11–T12: chạy trên Git/GitHub, không phụ thuộc stack.
- T13: **ĐẠT phần TLS** (16/11, nginx terminator 8200/8443/8444, TLSv1.2/1.3, PostgreSQL `ssl=on`); at-rest cấp volume risk-accepted (BitLocker Off, probe UAC) — `docs/evidence/T13_2026-11-16.md`. Biến thể Vault file storage của SV1 chưa nghiệm thu.
- T14: dùng `bench/k6/mixed.js` qua https 8443 (baseline qua 8444); số liệu 31/10–11/11 là `D-lab` (HTTP, trước TLS) — không ghi thành `D`. Cấu hình C không đo (BitLocker Off, risk-accepted).
- T15: mục 10–11 ở trên.
- T16: mục 9 ở trên.

Chi tiết từng ca nằm trong `docs/testing/test-plan.md`.
