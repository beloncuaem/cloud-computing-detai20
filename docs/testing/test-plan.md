# Kế hoạch kiểm thử và nghiệm thu — Đề tài 20

**Chủ đề:** Bảo vệ dữ liệu bằng mã hóa, quản lý khóa và vòng đời bí mật  
**Phiên bản:** 1.0 — 31/10/2026  
**Người phụ trách:** SV3 (Tester / DevSecOps)  
**Phạm vi:** API FastAPI, PostgreSQL, Vault Transit, Vault Database Secrets Engine, AppRole, rotation, CI và quy tắc bảo vệ nhánh.

Tài liệu này là checklist thực thi. Kết quả chỉ được coi là đạt khi có bằng chứng lưu trong `docs/evidence/` hoặc `bench/results/` và có thể đối chiếu lại bằng lệnh đã ghi.

## 1. Mục tiêu

1. Chứng minh dữ liệu nhạy cảm chỉ tồn tại dưới dạng ciphertext trong PostgreSQL, log, image và repository.
2. Chứng minh khóa và secret có vòng đời: cấp phát, sử dụng, gia hạn, xoay vòng, thu hồi.
3. Chứng minh ứng dụng chỉ có quyền tối thiểu và không thể tự xoay/export KEK.
4. Chứng minh xoay vòng KEK và mật khẩu DB không làm gián đoạn dịch vụ.
5. Đo độ trễ, throughput và tỷ lệ lỗi để kiểm chứng H1–H2.
6. Chứng minh pipeline chặn secret và quy tắc bảo vệ `main` có hiệu lực.
7. Ghi nhận trung thực các giới hạn của môi trường lab.

## 2. Giả thuyết và ngưỡng chấp nhận

| Mã | Giả thuyết | Chỉ số chấp nhận | Ca kiểm thử |
|---|---|---|---|
| H1 | Envelope encryption có overhead chấp nhận được | p95 tăng không quá 30% so với baseline | T14 |
| H2 | Xoay vòng KEK và mật khẩu DB không gián đoạn dịch vụ | Tỷ lệ lỗi 0% (hoặc dưới 0,1%) trong lúc rotation | T09, T14 |
| H3 | Pipeline chặn được secret bị commit nhầm | 100% secret giả gieo vào bị chặn | T11 |
| H4 | Plaintext và secret không nằm trong DB, image, log, repo | Quét ra 0 phát hiện | T02, T11, T13 |

Ngưỡng cảnh báo giải mã bất thường: **200 request `transit/decrypt` trong 60 giây từ cùng một danh tính** (theo cẩm nang). Ca T16 kiểm tra cả false positive trên tải bình thường và true positive khi gieo 200 lần giải mã.

## 3. Môi trường kiểm thử

### 3.1. Stack dự phòng bằng Docker (dùng để chạy T01–T16)

Stack này nằm trong PR hạ tầng đi kèm và dùng Vault dev mode. Đây là môi trường **lab**, không thay thế stack Vault file storage + TLS của SV1.

```powershell
# Từ thư mục gốc repository
docker compose up -d --build
docker compose ps
docker compose exec -T api python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

Thông tin cần ghi vào báo cáo: phiên bản Docker, Docker Compose, Python image, PostgreSQL, Vault, k6, CPU/RAM của máy.

```powershell
docker version
docker compose version
Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
```

### 3.2. Biến dùng chung cho các lệnh PowerShell

```powershell
$API       = "http://127.0.0.1:8000"
$ApiKey    = "local-demo-api-key-change-me"
$AdminKey  = "local-demo-admin-key-change-me"
$Headers   = @{ "X-API-Key" = $ApiKey; "Content-Type" = "application/json" }
$Admin     = @{ "X-Admin-Key" = $AdminKey; "Content-Type" = "application/json" }
```

Các lệnh `docker compose ...` chạy từ thư mục gốc repository. Nếu dùng stack native Windows của SV2, thay `docker compose exec -T postgres psql -U postgres -d encryption_db` bằng `psql` trên máy và giữ nguyên phần còn lại.

### 3.3. Quy ước bằng chứng

- Ảnh: `docs/evidence/Txx_<mô_tả>_<yyyy-mm-dd>.png`, che token, mật khẩu, secret ID và thông tin cá nhân.
- Dữ liệu thô: `bench/results/` (CSV k6, log audit đã lọc). Không đưa secret thật vào tên tệp.
- Mỗi ảnh phải thấy được **lệnh đã chạy** hoặc **kết quả cuối**, không chỉ thấy một phần màn hình không có ngữ cảnh.
- Không chụp `vault-credentials.json`, `.env`, token root hoặc secret ID chưa che.
- Ghi ngày, người chạy, phiên bản stack cạnh mỗi kết quả.

## 4. Ma trận kiểm thử

| ID | Hạng mục | Mục tiêu | Kỳ vọng | Trạng thái ban đầu |
|---|---|---|---|---|
| T01 | Envelope encryption | Round-trip create/read | Giá trị đọc lại khớp; DB chỉ có ciphertext, nonce, encrypted DEK | Chưa chạy |
| T02 | Plaintext leakage | Không có plaintext trong DB/dump | 0 kết quả khi tìm chuỗi test | Chưa chạy |
| T03 | Tamper detection | Sửa ciphertext bị phát hiện | HTTP 503, audit ghi failure | Chưa chạy |
| T04 | AAD binding | Hoán đổi ciphertext giữa 2 bản ghi bị phát hiện | HTTP 503 | Chưa chạy |
| T05 | API authentication | Thiếu/sai API key bị chặn | 401; key đúng 201 | Chưa chạy |
| T06 | AppRole least privilege | App không rotate/export KEK | Checker PASS; rotate/export bị 403 | Có defect D-01 |
| T07 | Audit | Ghi nhận Transit/Database | Audit log có `transit/decrypt`, `database/creds`; không có plaintext | Chưa chạy |
| T08 | KEK rotation + rewrap | Xoay KEK, rewrap, chặn version cũ | Rewrap sang version mới; `min_decryption_version` chặn v1 | Có defect D-03 |
| T09 | DB credential rotation | Xoay mật khẩu DB dưới tải | Lỗi < 0,1%; pool mới hoạt động | Chưa chạy |
| T10 | Lease lifecycle | Gia hạn/thu hồi lease | Credential bị thu hồi không đăng nhập được | Có defect D-02 |
| T11 | Secret scanning | Gitleaks chặn secret | 0 finding trên repo; secret giả bị phát hiện | Chưa chạy |
| T12 | Branch protection | Chặn push trực tiếp/force push; bắt buộc PR + approval | GitHub từ chối; PR chỉ merge sau approval | Đã có bằng chứng một phần |
| T13 | TLS / at rest | Bảo vệ trên đường truyền và ổ đĩa | TLS bật; BitLocker/volume encryption bật | Chưa đạt — thiếu TLS |
| T14 | Benchmark | Đo p50/p95/p99, RPS, lỗi | Đủ 10/50/100 VUs, 5 lần; H1, H2 | Chưa chạy |
| T15 | Cost / cleanup / reproducibility | Dựng lại và dọn sạch | Lệnh dựng lại chạy được; không còn tài nguyên | Chưa chạy |
| T16 | Anomaly alert | Cảnh báo giải mã bất thường | 200 decrypt/phút sinh cảnh báo; tải thường không báo | Chưa chạy |

## 5. Chi tiết ca kiểm thử

### T01 — Envelope encryption round-trip

**Mục tiêu:** Chứng minh plaintext chỉ được mã hóa tại ứng dụng, DEK được Vault bọc, và đọc lại đúng.

**Tiền điều kiện:** Stack đã chạy; `/ready` trả `ready`.

**Các bước:**

```powershell
$created = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "customer_phone"; value = "0901234567" } | ConvertTo-Json)
$created | Format-List

$read = Invoke-RestMethod -Uri "$API/records/$($created.id)" -Headers $Headers
$meta = Invoke-RestMethod -Uri "$API/records/$($created.id)/metadata" -Headers $Headers
$read.value
$meta | Format-List

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT record_type, octet_length(ciphertext) AS ciphertext_bytes, nonce,
          left(encrypted_dek, 12) AS dek_prefix, kek_name, kek_version
   FROM sensitive_records WHERE id = '$($created.id)';"
```

**Kỳ vọng:**

- POST trả 201, có `id`, `status = encrypted_and_stored`.
- GET trả đúng `0901234567`.
- `ciphertext_bytes` lớn hơn 0; `nonce` có 12 byte; `encrypted_dek` bắt đầu bằng `vault:vN:`; `kek_version` khớp N.
- Bảng không có cột plaintext.

**Bằng chứng:** ảnh response POST/GET, ảnh metadata, ảnh kết quả SQL.

### T02 — Không có plaintext trong DB, dump, log và image

**Mục tiêu:** Kiểm chứng H4 ở phạm vi dữ liệu đã lưu.

**Các bước:**

```powershell
# 1) Tìm chuỗi test trong bảng
docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT count(*) AS plaintext_hits FROM sensitive_records
   WHERE encode(ciphertext, 'escape') LIKE '%0901234567%'
      OR encrypted_dek LIKE '%0901234567%';"

# 2) Tìm trong pg_dump
docker compose exec -T postgres sh -c `
  "pg_dump -U postgres -d encryption_db | grep -a -c '0901234567' || true"

# 3) Tìm trong thư mục ứng dụng và log container
docker compose exec -T api sh -c `
  "grep -R -a '0901234567' /app /tmp 2>/dev/null | head -n 5 || true"

# 4) Tìm trong image (không mount volume dữ liệu)
docker run --rm detai20-api:local sh -c `
  "grep -R -a '0901234567' /app 2>/dev/null | head -n 5 || true"
```

**Kỳ vọng:** cả bốn lệnh trả `0` hoặc không có dòng kết quả. Nếu có, dừng và điều tra ngay.

**Lưu ý:** `grep -c` trả 0 khi không khớp; `|| true` để PowerShell không dừng khi grep trả mã 1.

**Bằng chứng:** ảnh 4 kết quả, ghi rõ ngày và ID bản ghi test.

### T03 — Phát hiện ciphertext bị sửa

**Mục tiêu:** AES-256-GCM phải từ chối ciphertext bị thay đổi.

**Các bước:**

```powershell
$r = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "tamper_test"; value = "tamper-0901234567" } | ConvertTo-Json)

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "UPDATE sensitive_records
   SET ciphertext = set_byte(ciphertext, 0, (get_byte(ciphertext, 0) # 1))
   WHERE id = '$($r.id)';"

try {
  Invoke-RestMethod -Uri "$API/records/$($r.id)" -Headers $Headers
  "UNEXPECTED: decrypt succeeded"
} catch {
  "HTTP status: $($_.Exception.Response.StatusCode.value__)"
}

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT event_type, outcome, details, occurred_at
   FROM audit_events WHERE record_id = '$($r.id)' ORDER BY id DESC LIMIT 3;"

# Dọn bản ghi test
docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "DELETE FROM audit_events WHERE record_id = '$($r.id)';
   DELETE FROM sensitive_records WHERE id = '$($r.id)';"
```

**Kỳ vọng:** HTTP 503; audit có `record.read` / `failure` / `decrypt_failed`. Không có plaintext trong log.

### T04 — AAD binding: hoán đổi ciphertext giữa hai bản ghi

**Mục tiêu:** Chứng minh AAD `record_id:record_type` ngăn việc tráo dữ liệu đã mã hóa.

**Các bước:**

```powershell
$a = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "aad_a"; value = "value-a" } | ConvertTo-Json)
$b = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "aad_b"; value = "value-b" } | ConvertTo-Json)

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "UPDATE sensitive_records b
   SET ciphertext = a.ciphertext, nonce = a.nonce, encrypted_dek = a.encrypted_dek,
       kek_name = a.kek_name, kek_version = a.kek_version
   FROM sensitive_records a
   WHERE b.id = '$($b.id)' AND a.id = '$($a.id)';"

try {
  Invoke-RestMethod -Uri "$API/records/$($b.id)" -Headers $Headers
  "UNEXPECTED: swapped payload decrypted"
} catch {
  "HTTP status: $($_.Exception.Response.StatusCode.value__)"
}
```

**Kỳ vọng:** HTTP 503 vì AAD của bản ghi B không khớp ciphertext của A. Dọn hai bản ghi sau test.

### T05 — Xác thực API key và admin key

**Mục tiêu:** Endpoint ghi/đọc chỉ cho phép client có API key; endpoint quản trị chỉ cho phép admin key.

**Các bước:**

```powershell
# Thiếu key
try { Invoke-RestMethod -Uri "$API/records" } catch { "missing: $($_.Exception.Response.StatusCode.value__)" }

# Sai key
try {
  Invoke-RestMethod -Uri "$API/records" -Headers @{ "X-API-Key" = "wrong-key" }
} catch { "wrong: $($_.Exception.Response.StatusCode.value__)" }

# Dùng API key thường cho endpoint admin
try {
  Invoke-RestMethod -Method Post -Uri "$API/admin/rotation/transit-key" -Headers $Headers
} catch { "admin with record key: $($_.Exception.Response.StatusCode.value__)" }
```

**Kỳ vọng:** hai trường hợp đầu trả 401; trường hợp admin trả 403 vì `require_admin_key` dùng 403. Chỉ gọi endpoint admin với `$Admin` khi thực hiện T08/T09.

### T06 — AppRole chỉ có quyền tối thiểu

**Mục tiêu:** Token của ứng dụng không được rotate, export hoặc sửa cấu hình KEK.

**Các bước:**

```powershell
docker compose exec -T api python scripts/check_approle_privileges.py
```

Script kiểm tra `sys/capabilities-self` cho các path:

- Được phép: `transit/datakey/plaintext/app-data-key`, `transit/decrypt/app-data-key`, `database/creds/app-role`.
- Bị cấm: `transit/keys/app-data-key/rotate`, `transit/keys/app-data-key` (đọc metadata/version), `transit/export/app-data-key`, `transit/keys/app-data-key/config`.

Ngoài ra, thử gọi trực tiếp (lệnh một dòng; lỗi 403 sẽ làm Python thoát khác 0 — đó là kết quả mong đợi):

```powershell
docker compose exec -T api python -c "import json,hvac; from pathlib import Path; c=json.loads(Path('/credentials/vault-credentials.json').read_text()); v=hvac.Client(url='http://vault:8200'); v.auth.approle.login(role_id=c['role_id'], secret_id=c['secret_id']); v.secrets.transit.rotate_key(name='app-data-key', mount_point='transit')"
```

**Kỳ vọng:** checker PASS; rotate/export bị từ chối (403). Hiện tại policy trong `setup_vault.py` còn cấp `update` cho path rotate và `read` cho metadata khóa → **D-01** (đúng như output của checker), nên checker sẽ FAIL cho đến khi SV2 sửa. Sau khi sửa, phải chạy lại `vault-init` để ghi policy mới rồi chạy lại checker; đọc metadata khóa cũng không cần thiết cho luồng datakey/decrypt.

**Bằng chứng:** ảnh checker PASS/FAIL; ảnh lỗi 403 đã che token.

### T07 — Audit log của Vault

**Mục tiêu:** Chứng minh các thao tác Transit và Database được ghi nhận, không chứa plaintext.

**Các bước:**

```powershell
# Stack dự phòng bật audit tại /tmp/vault-audit.log trong container vault
docker compose exec -T vault vault audit list
docker compose exec -T vault sh -c "grep -a 'transit/decrypt' /tmp/vault-audit.log | tail -n 3"
docker compose exec -T vault sh -c "grep -a 'database/creds' /tmp/vault-audit.log | tail -n 3"
docker compose exec -T vault sh -c "grep -a -c '0901234567' /tmp/vault-audit.log || true"
```

**Kỳ vọng:** audit list có ít nhất một file device; log có request `transit/decrypt` và `database/creds`; số lần xuất hiện plaintext test là 0. Vault mặc định băm giá trị nhạy cảm trong audit; nếu thấy plaintext, dừng và báo cáo là lỗi cấu hình.

**Giới hạn:** audit trong dev mode mất khi container Vault bị xóa. Stack của SV1 phải dùng file storage và audit device bền vững.

### T08 — Xoay KEK, rewrap và chặn version cũ

**Mục tiêu:** Chứng minh vòng đời KEK: tạo version mới, rewrap DEK cũ, chặn giải mã version đã nghỉ hưu.

**Trạng thái:** ứng dụng hiện chỉ có `rotate_transit_key.py` (tạo version mới), chưa có rewrap và `min_decryption_version` → **D-03**. Ca này chỉ ĐẠT sau khi SV2 bổ sung.

**Các bước dự kiến:**

```powershell
# 1) Tạo bản ghi, ghi nhận kek_version = 1
$r = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "rotation_test"; value = "rotation-value" } | ConvertTo-Json)
$meta1 = Invoke-RestMethod -Uri "$API/records/$($r.id)/metadata" -Headers $Headers
$meta1.kek_version

# 2) Xoay KEK bằng danh tính operator (root trong lab), KHÔNG dùng AppRole của app
docker compose exec -T vault vault write -f transit/keys/app-data-key/rotate

# 3) Bản ghi cũ vẫn đọc được bằng version cũ
Invoke-RestMethod -Uri "$API/records/$($r.id)" -Headers $Headers

# 4) Rewrap (script SV2 bổ sung)
docker compose exec -T api python scripts/rewrap_dek.py

# 5) Kiểm tra DB đã chuyển sang version mới
docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT id, kek_version, left(encrypted_dek, 12) FROM sensitive_records WHERE id = '$($r.id)';"

# 6) Chặn version cũ
docker compose exec -T vault vault write transit/keys/app-data-key/config min_decryption_version=2

# 7) Một ciphertext v1 cũ phải bị từ chối
docker compose exec -T vault vault write transit/decrypt/app-data-key ciphertext="vault:v1:<ciphertext_cu>"
```

Sau khi sửa D-01, AppRole của app không còn quyền rotate; endpoint `/admin/rotation/transit-key` và `rotate_transit_key.py` phải chuyển sang danh tính operator riêng hoặc bị bỏ. Vì vậy ca này dùng lệnh `vault` của operator trong container (stack lab đặt `VAULT_TOKEN=root`), không dùng API key admin của app.

**Kỳ vọng:**

- Sau bước 2, bản ghi vẫn đọc được (Vault giữ version cũ).
- Sau bước 4, `kek_version` và prefix `encrypted_dek` là version mới; đọc lại thành công.
- Sau bước 6, ciphertext v1 bị từ chối; mọi bản ghi đã rewrap vẫn đọc được.
- Audit có `transit/keys/app-data-key/rotate` và `transit/rewrap/app-data-key`.

**Bằng chứng:** ảnh metadata trước/sau, ảnh DB, ảnh lỗi khi giải mã v1, ảnh `vault read transit/keys/app-data-key` (che thông tin không cần thiết).

### T09 — Xoay mật khẩu DB dưới tải, không gián đoạn

**Mục tiêu:** Kiểm chứng H2 cho database credential rotation.

**Tiền điều kiện:** App dùng dynamic credentials.

```powershell
# Tạo file .env ở thư mục gốc repository (đã bị .gitignore)
"USE_VAULT_DB_CREDS=true" | Set-Content -Path .env -Encoding ascii
docker compose up -d --force-recreate api
Invoke-RestMethod -Uri "$API/ready" | ConvertTo-Json
```

**Các bước:**

1. Chạy k6 50 VUs trong 3 phút (xem T14), xuất CSV `bench/results/E_rotation_run1.csv`.
2. Sau 60 giây, gọi:

```powershell
Invoke-RestMethod -Method Post -Uri "$API/admin/rotation/database" -Headers $Admin
```

3. Theo dõi k6 và lấy kết quả: `http_req_failed < 0.001`, p95 không tăng đột biến.
4. Kiểm tra role động:

```powershell
docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT rolname, rolvaliduntil FROM pg_roles
   WHERE rolname LIKE 'v-app-role-%' ORDER BY rolvaliduntil DESC;"
```

**Kỳ vọng:** API trả `status = rotated`, `new_lease_duration_seconds`; k6 không có lỗi 5xx; role mới xuất hiện; role cũ còn hiệu lực đến khi lease hết hạn (overlap có chủ đích). Ghi lại thời điểm rotation và cửa sổ ảnh hưởng.

### T10 — Vòng đời lease: gia hạn và thu hồi

**Mục tiêu:** Chứng minh credential động hết hiệu lực sau khi thu hồi; lease có TTL và gia hạn được.

**Các bước:**

```powershell
# Cấp một credential động và giữ nguyên JSON để dùng cả username/password
$lease = docker compose exec -T vault vault read -format=json database/creds/app-role | ConvertFrom-Json
$lease.data.username
$lease.lease_id
$lease.lease_duration

# Đăng nhập thử
docker compose exec -T -e PGPASSWORD=$lease.data.password postgres `
  psql -h 127.0.0.1 -U $lease.data.username -d encryption_db -c "SELECT current_user;"

# Gia hạn
docker compose exec -T vault vault lease renew -increment=60s $lease.lease_id

# Thu hồi
docker compose exec -T vault vault lease revoke $lease.lease_id

# Đăng nhập lại phải thất bại
docker compose exec -T -e PGPASSWORD=$lease.data.password postgres `
  psql -h 127.0.0.1 -U $lease.data.username -d encryption_db -c "SELECT 1;"
```

**Kỳ vọng:** đăng nhập trước thu hồi thành công; sau thu hồi báo `password authentication failed` hoặc role không tồn tại. Audit có `database/creds` và `lease/revoke`.

**Kiểm tra cấu hình AppRole:**

```powershell
docker compose exec -T vault vault read auth/approle/role/student2-app
```

Hiện tại `secret_id_ttl=0s`, `secret_id_num_uses=0` → **D-02** (secret ID không hết hạn, dùng lại vô hạn). Kỳ vọng sau sửa: TTL hữu hạn (ví dụ 1h) và `num_uses` giới hạn (ví dụ 1–5). Ghi rõ đây là cấu hình lab trước khi sửa.

### T11 — Gitleaks và kiểm tra secret trong lịch sử

**Mục tiêu:** Kiểm chứng H3/H4.

**Các bước:**

```powershell
# 1) Quét toàn bộ lịch sử bằng đúng image/config của CI
docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:v8.24.0 detect `
  --source=/repo --config=/repo/.gitleaks.toml --log-opts="--all" --redact --verbose

# 2) .env và file credential phải bị ignore
git check-ignore -v student2_project_windows/.env
git ls-files | Select-String -Pattern '(^|/)\.env$|vault-credentials\.json'

# 3) Gieo secret giả vào thư mục tạm, KHÔNG commit vào repo
$tmp = Join-Path $env:TEMP "gitleaks-test-$(Get-Random)"
New-Item -ItemType Directory -Path $tmp | Out-Null
$fake = "ghp_" + (-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 36 | ForEach-Object { [char]$_ }))
Set-Content -Path (Join-Path $tmp "fake.env") -Value "GITHUB_TOKEN=$fake" -Encoding ascii
docker run --rm -v "${PWD}:/repo" -v "${tmp}:/scan" ghcr.io/gitleaks/gitleaks:v8.24.0 `
  dir /scan --config=/repo/.gitleaks.toml --redact --verbose
Remove-Item -Recurse -Force $tmp
```

**Kỳ vọng:** bước 1 trả 0 leak, exit 0. Bước 2 in ra đường dẫn ignore; danh sách file tracked không có `.env`/`vault-credentials.json`. Bước 3 phát hiện secret giả, exit 1.

**Quan trọng:** không đẩy secret giả lên repository thật, kể cả trong nhánh tạm, vì nó sẽ nằm lại trong lịch sử Git. Thử nghiệm H3 dùng thư mục tạm với cùng image và config; bằng chứng CI chạy xanh lấy từ PR thật.

### T12 — Quy tắc bảo vệ nhánh `main`

**Mục tiêu:** Chứng minh không thể push trực tiếp/force push; PR cần approval và status check.

**Bằng chứng đã có:** `docs/evidence/ruleset_active.png`, `ruleset_rules.png`, `push_blocked_main.png`, `pr_review_merged.png`.

**Ca lặp lại (cẩn thận, không làm bẩn `main`):**

```powershell
# Tạo commit rỗng trên một nhánh tạm, mở PR, thử merge trước khi có approval
git switch -c test/ruleset-guard
git commit --allow-empty -m "test: ruleset guard"
git push -u origin test/ruleset-guard
# Mở PR trên GitHub; nút merge phải bị chặn khi chưa có approval.
# Đóng PR, xóa nhánh, quay lại main.

git switch main
git pull --ff-only
git commit --allow-empty -m "test: direct push must fail"
try { git push origin main } catch { "direct push rejected as expected" }
try { git push --force origin main } catch { "force push rejected as expected" }
git reset --hard origin/main   # chỉ dùng sau khi chắc chắn không có thay đổi cần giữ
```

**Kỳ vọng:** GitHub trả `GH013` / `Changes must be made through a pull request`; force push cũng bị chặn; PR chưa đủ approval không merge được.

**Đã cập nhật ruleset (31/10/2026):** `gitleaks` và `unit-tests` đã được thêm làm required status checks cho `main-1`. PR #5 đã chạy xanh cả hai job. Cần chụp lại màn hình Settings → Rules → `main-1` và ảnh PR có 2 check xanh làm bằng chứng T12.

### T13 — TLS và bảo vệ dữ liệu at rest

**Mục tiêu:** Kiểm chứng dữ liệu được bảo vệ trên đường truyền và trên ổ đĩa.

**Trạng thái:** stack dự phòng dùng Vault dev mode qua HTTP, chưa có TLS → **chưa đạt**. Đây là phần việc của SV1 (Vault file storage + TLS + reverse proxy cho API). Ghi rõ trong báo cáo là giới hạn lab, không tuyên bố đã đạt.

**Khi SV1 hoàn thành:**

```powershell
curl.exe -k -i https://localhost:8200/v1/sys/health
curl.exe -k -i https://localhost:8443/health
openssl s_client -connect localhost:8443 -servername localhost -tls1_2

docker compose exec -T postgres psql -U postgres -d encryption_db -c "SHOW ssl;"
manage-bde -status C:
```

**Kỳ vọng:** kết nối TLS thành công với chứng chỉ của lab; TLS 1.2+; `SHOW ssl` = on nếu bật PostgreSQL TLS; BitLocker `Protection On` hoặc volume được mã hóa. Nếu dùng Docker Desktop/WSL2, ghi rõ VHDX nằm trên ổ C: đã bật BitLocker.

**Kiểm tra secret không nằm trong image:**

```powershell
docker run --rm detai20-api:local sh -c `
  "find /app -maxdepth 3 \( -name '.env' -o -name 'vault-credentials.json' \) -print"
```

**Kỳ vọng:** không có kết quả. `vault-credentials.json` chỉ nằm trong volume `/credentials`, không nằm trong image.

### T14 — Benchmark k6 (10/50/100 VUs)

**Mục tiêu:** Đo p50/p95/p99, RPS, tỷ lệ lỗi; kiểm chứng H1, H2.

**Ma trận cấu hình (theo cẩm nang):**

| Mã | Cấu hình | Trạng thái với app hiện tại |
|---|---|---|
| A | Không mã hóa, HTTP (baseline) | Chưa có chế độ baseline; cần build benchmark riêng, không đưa vào `main` |
| B | TLS | Chờ SV1 |
| C | TLS + mã hóa volume | Chờ SV1 + BitLocker |
| D | TLS + envelope encryption | Đo được phần envelope; TLS chờ SV1 (tạm gọi D-lab nếu chạy HTTP) |
| E | D + đang xoay vòng khóa | Đo được D-lab + rotation; ghi rõ thiếu TLS |
| D' | D sau tối ưu (cache DEK) | Sau khi SV2 tối ưu |

Không được ghi kết quả D-lab thành D trong báo cáo. Nếu buộc phải đo trước khi có TLS, ghi tên `D-lab` và nêu rõ khác biệt.

**Quy trình:**

1. Đóng ứng dụng nặng; ghi cấu hình máy.
2. Khởi động lại stack trước mỗi cấu hình.
3. Warm-up 60 giây, không ghi vào CSV.
4. Chạy 5 lần cho mỗi mức 10/50/100 VUs, mỗi lần 3 phút (có thể 5 phút nếu máy đủ khỏe).
5. Lưu CSV thô vào `bench/results/<config>_<vus>_run<N>.csv`.

```powershell
New-Item -ItemType Directory -Force bench/results | Out-Null

# Warm-up (không xuất CSV)
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=local-demo-api-key-change-me `
  -e VUS=10 -e DURATION=1m bench/k6/mixed.js

# Lần đo chính thức: lặp run1..run5
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=local-demo-api-key-change-me `
  -e VUS=50 -e DURATION=3m `
  --out csv=bench/results/D-lab_50_run1.csv bench/k6/mixed.js
```

**Phân tích:**

```powershell
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python bench/analyze.py "bench/results/*.csv"
```

**Kỳ vọng:**

- H1: `(p95_D − p95_A) / p95_A ≤ 30%`. Nếu chưa có A, ghi rõ H1 chưa kết luận.
- H2: trong cửa sổ rotation, `http_req_failed < 0.001` và không có 5xx.
- Báo cáo bảng p50/p95/p99, RPS, error rate, CPU; nêu sai số và giới hạn máy cá nhân.

**Bằng chứng:** CSV thô, bảng Markdown do `analyze.py` xuất, ảnh summary k6, ảnh thời điểm rotation, mô tả máy.

### T15 — Chi phí, dọn tài nguyên, khả năng tái lập và kế hoạch mất khóa

**Mục tiêu:** Chứng minh có thể dựng lại, dọn sạch và có phương án khi mất khóa.

**Các bước:**

```powershell
# Dọn stack và volume
docker compose down -v --remove-orphans
docker image rm detai20-api:local 2>$null
docker system df

# Tái lập từ bản sạch (thư mục tạm)
$tmp = Join-Path $env:TEMP "detai20-repro-$(Get-Random)"
git clone https://github.com/beloncuaem/cloud-computing-detai20 $tmp
Push-Location $tmp
docker compose up -d --build
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
docker compose down -v
Pop-Location
Remove-Item -Recurse -Force $tmp
```

**Kỳ vọng:** lệnh dựng lại chạy không lỗi; smoke test PASS; sau `down -v` không còn container/volume của dự án; thời gian dựng lại được ghi lại.

**Chi phí:** lab chạy cục bộ nên chi phí cloud là 0. Nếu triển khai cloud, lập bảng theo bảng giá hiện hành (VM, ổ đĩa, băng thông, Vault/KMS); không dùng số liệu ước lượng không nguồn. Ghi rõ tài nguyên đã dọn.

**Kế hoạch mất khóa (tóm tắt, đưa vào Chương 5):**

- Unseal key/shamir shares: lưu offline, tách người giữ; không commit, không gửi chat.
- Nếu mất unseal key: Vault không mở được; dữ liệu coi như không thể giải mã. Phục hồi từ backup DB + snapshot Vault đã mã hóa, hoặc chấp nhận mất dữ liệu theo chính sách.
- Nếu lộ AppRole secret ID: thu hồi secret ID/lease, xoay role, kiểm tra audit.
- Nếu lộ KEK: rotate KEK + rewrap toàn bộ, đặt `min_decryption_version`, điều tra phạm vi.
- Dev mode không có backup bền vững; chỉ dùng lab.

### T16 — Cảnh báo giải mã bất thường

**Mục tiêu:** Phát hiện 200 request `transit/decrypt` trong 60 giây từ một danh tính; không báo nhầm trên tải thường.

**Công cụ:**

- `student2_project_windows/scripts/generate_decrypt_load.py`: gieo 200 lần giải mã bằng một token.
- `student2_project_windows/scripts/alert_decrypt_rate.py`: đọc audit log JSON, đếm cửa sổ trượt 60 giây theo danh tính, in `ALERT` và exit 2 khi vượt ngưỡng.

**Các bước:**

```powershell
# (0) Làm sạch audit để phép đo chỉ chứa lưu lượng của lần chạy này
docker compose exec -T vault sh -c "export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root; vault audit disable file/; rm -f /tmp/vault-audit.log; vault audit enable file file_path=/tmp/vault-audit.log"

# (a) Tải bình thường 10 phút qua API (identity audit = approle)
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=local-demo-api-key-change-me `
  -e VUS=5 -e SLEEP=2 -e DURATION=10m bench/k6/mixed.js

docker compose cp vault:/tmp/vault-audit.log bench/results/audit_normal.log
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python student2_project_windows/scripts/alert_decrypt_rate.py `
  --log bench/results/audit_normal.log --threshold 200 --window 60

# (b) Gieo 200 lần giải mã bằng token demo/root (identity audit = token, tách khỏi app)
docker compose run --rm --no-deps vault-init python scripts/generate_decrypt_load.py --count 200
docker compose cp vault:/tmp/vault-audit.log bench/results/audit_attack.log
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python student2_project_windows/scripts/alert_decrypt_rate.py `
  --log bench/results/audit_attack.log --threshold 200 --window 60
```

`VUS=5, SLEEP=2` giãn nhịp để tải nền chỉ có ~90 decrypt/phút, thấp hơn ngưỡng 200. Không chạy burst qua API container: API cố ý không giữ token root, nên script dùng `vault-init` với `VAULT_DEMO_TOKEN=root`. Trong audit, app có `auth.display_name = approle`, burst có `display_name = token`; vì vậy phép phân tích theo danh tính không trộn hai nguồn.

**Kỳ vọng:**

- (a) không có `ALERT` cho danh tính `approle` trong 10 phút; ghi lại số decrypt/phút thực tế và số cảnh báo giả (mục tiêu 0).
- (b) có `ALERT` cho danh tính `token`; ghi thời điểm bắt đầu, thời điểm đạt ngưỡng trong log, và độ trễ phát hiện.
- Nếu tải thường đã vượt 200/phút, threshold phải được hiệu chỉnh theo baseline và ghi rõ lý do; không che giấu false positive.

## 6. Nhật ký defect và việc cần sửa

| Mã | Mức | Mô tả | Bằng chứng | Người sửa | Trạng thái |
|---|---|---|---|---|---|
| D-01 | Cao | Policy app cấp `update` cho `transit/keys/app-data-key/rotate` và `read` cho metadata khóa | `setup_vault.py` | SV2 | Mở |
| D-02 | Cao | AppRole `secret_id_ttl=0s`, `secret_id_num_uses=0` | `setup_vault.py` | SV2 | Mở |
| D-03 | Cao | Chưa có rewrap và `min_decryption_version` sau khi xoay KEK | `rotate_transit_key.py` | SV2 | Mở |
| D-04 | Trung bình | Stack dự phòng dùng Vault dev mode, HTTP, root token; không dùng cho production | `docker-compose.yml` | SV1/SV3 | Chấp nhận trong lab, ghi rõ |
| D-05 | Trung bình | `vault_admin` là PostgreSQL SUPERUSER | `sql/00-create-roles.sql` | SV1 | Chấp nhận trong lab, ghi rõ |
| D-06 | Thấp | `.vscode/settings.json` còn tracked; `.gitignore` từng bỏ qua CSV benchmark | repo | SV2/SV3 | CSV đã sửa trong PR này; `.vscode` chờ dọn |
| D-07 | Trung bình | Chưa có cấu hình baseline plaintext (A) cho H1 | `bench/` | SV2/SV3 | Mở |

## 7. Điều kiện nghiệm thu

Chỉ tag `v1.0.0` khi:

- T01–T05, T07, T09–T12, T15, T16 đạt.
- T06 và T08 đạt sau khi D-01/D-03 được sửa; nếu chưa, ghi rõ là "chưa đạt" và không tuyên bố đã kiểm chứng least privilege/rewrap.
- T13 đạt sau khi SV1 bàn giao TLS; nếu không, ghi rõ giới hạn.
- T14 có đủ dữ liệu cho ít nhất D/E và nêu rõ A/B/C; H1 chỉ kết luận khi có A; H2 kết luận từ E.
- Không còn secret thật trong repo/history; Gitleaks xanh trên PR cuối.
- Ruleset yêu cầu `gitleaks` và 1 approval; push trực tiếp bị chặn.
- Báo cáo có bảng kết quả, ảnh bằng chứng, phần rủi ro còn lại và kế hoạch mất khóa.

## 8. Lịch thực thi đề xuất

| Ngày | Việc chính | Người |
|---|---|---|
| 31/10 | Chốt test plan, CI, stack dự phòng; chạy T01–T07 | SV3 |
| 01/11 | SV2 sửa D-01/D-02/D-03; SV1 bàn giao TLS hoặc chốt phương án dự phòng | SV2, SV1 |
| 02/11 | Chạy T08–T10; đo T14 lần đầu | SV3, SV2 |
| 03/11 | T16, đo lại T14 sau tối ưu; thu bằng chứng | SV3 |
| 04/11 | Viết Chương 3–4; rà soát số liệu | SV3 |
| 05/11 | Quay video 8–12 phút; kiểm tra T13/T15 | Cả nhóm |
| 06/11 | Đóng băng, tag `v1.0.0`, nộp | Cả nhóm |
| 07/11 | Dự phòng | Cả nhóm |
