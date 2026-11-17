# Kịch bản trình diễn trực tiếp — Đề tài 20

**Thời lượng:** 15–20 phút (mục tiêu 18 phút, chừa 2 phút dự phòng)
**Hình thức:** trình diễn trực tiếp trước giảng viên, **không dùng video**. Đề bài cho phép "Video demo 8–12 phút **hoặc** trình diễn trực tiếp 15–20 phút, có kịch bản và phân công rõ"; nhóm chọn phương án trực tiếp.
**Phiên bản áp dụng:** worktree `wt-hoanthien` trên nền `origin/main` `dd287d1` + cherry-pick `3e22065` (fix D-05 của PR #14 đang chờ merge). TLS đã có từ 16/11/2026 (biên bản `docs/evidence/T13_2026-11-16.md`); thẻ nghiệm thu hiện tại `v0.9.0-rc1`. Lịch demo đã đổi so với kế hoạch 11/11; ngày mới chưa chốt — rehearsal kỹ thuật chạy 14/11/2026 (mục 8.1), rehearsal có người dẫn **chưa chạy**.
**Nguyên tắc:** mỗi người dẫn phần của mình, chạy lệnh thật trên máy thật, và **tự trả lời được quyết định kỹ thuật** trong phần phản biện. Ảnh chụp chỉ bổ trợ; log và số liệu mới là bằng chứng.

## 1. Phân công

| Ký hiệu | Thành viên | GitHub | Dẫn cảnh |
|---|---|---|---|
| **SV3** | Bùi Ngô Anh Quang (nhóm trưởng) | `beloncuaem` | Mở đầu, kiến trúc, T10, số liệu benchmark, CI/ruleset, kết luận |
| **SV2** | Nguyễn Minh Hiếu | `Hieu0408` | Luồng mã hóa bình thường, T02, T03/T04, T06, T08 |
| **SV1** | SV1 | `hothienphu` | Hạ tầng, T13 (TLS đã đạt 16/11; at-rest risk-accepted), dọn tài nguyên |

## 2. Chuẩn bị trước giờ demo (T−30 phút, SV3 điều phối)

Đây là phần **bắt buộc**, vì hai ràng buộc bảo mật của chính đồ án có thể làm demo hỏng nếu bỏ qua:

1. **API key chỉ đọc từ môi trường (PR #9).** Thiếu `API_KEY` hoặc `ADMIN_API_KEY` thì `docker compose` thoát ngay và API từ chối khởi động.
2. **SecretID của workload chỉ dùng 1 lần và hết hạn sau 10 phút (D-02).** Mỗi lần API khởi động lại phải cấp SecretID mới bằng danh tính operator, nếu không API sẽ không đăng nhập được Vault.
3. **Chứng chỉ lab phải tồn tại trước khi dựng stack** (nginx và PostgreSQL đọc từ `infrastructure/certs/out/`, đã gitignore). Nếu `out/` trống hoặc bị xóa, sinh lại trong Git Bash:

```bash
MSYS_NO_PATHCONV=1 bash infrastructure/certs/gen-certs.sh
```

```powershell
# (a) Dựng stack sạch — chạy trước, để kịp thời gian build
docker compose down -v
docker compose up -d --build
docker inspect detai20-vault-init-1 --format '{{.State.ExitCode}}'   # phải = 0
docker compose ps                                                   # api/postgres/vault/nginx đều healthy

# (a2) Kiểm tra TLS trước khi demo — nginx terminator phải sống (cert tự ký nên cần -k)
curl.exe -sk https://127.0.0.1:8443/health          # phải trả {"status":"ok"}
curl.exe -sk https://127.0.0.1:8200/v1/sys/health   # Vault qua TLS, "initialized":true

# (b) Nạp khóa vào phiên PowerShell (không in giá trị khóa ra màn hình)
Get-Content .env | ForEach-Object { if ($_ -match '^([A-Z_]+)=(.*)$') { Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2] } }
$API = "https://127.0.0.1:8443"   # mọi cảnh demo đi qua TLS (nginx terminator)
$Headers = @{ "X-API-Key" = $env:API_KEY; "Content-Type" = "application/json" }
$AdminHeaders = @{ "X-Admin-Key" = $env:ADMIN_API_KEY }

# (b2) Tin CA lab trong store người dùng để Invoke-RestMethod chấp nhận cert tự ký.
# PowerShell 5.1 không có -SkipCertificateCheck; chỉ tin đúng CA của lab, gỡ sau demo (mục 7).
Import-Certificate -FilePath infrastructure/certs/out/ca.crt -CertStoreLocation Cert:\CurrentUser\Root

# (c) Smoke test 9/9 qua TLS — nếu hỏng ở đây thì KHÔNG demo, sửa trước
./scripts/smoke-test.ps1 -BaseUrl $API

# (d) Nếu API đã restart sau khi dựng: cấp SecretID mới rồi restart API
docker compose run --rm --no-deps --entrypoint python vault-init scripts/issue_workload_secret.py
docker compose restart api
# chờ api healthy rồi chạy lại smoke test

# (e) Kiểm tra trạng thái khóa trước khi demo T08
docker compose exec -T vault vault read -field=latest_version transit/keys/app-data-key
docker compose exec -T vault vault read -field=min_decryption_version transit/keys/app-data-key
```

Bổ sung cho (a2) — xác nhận protocol/cipher thật của biên TLS bằng `openssl` trong Git Bash:

```bash
MSYS_NO_PATHCONV=1 openssl s_client -connect 127.0.0.1:8443 -servername localhost -tls1_2 </dev/null
MSYS_NO_PATHCONV=1 openssl s_client -connect 127.0.0.1:8443 -servername localhost -tls1_3 </dev/null
```

Phải thấy `Protocol: TLSv1.2` (cipher ECDHE-RSA-AES128-GCM-SHA256) và `Protocol: TLSv1.3` (TLS_AES_256_GCM_SHA384). `Verify return code: 21` là **đúng kỳ vọng lab**: CA tự ký chưa nằm trong trust store của máy (đã tin riêng cho phiên demo ở bước b2).

**Ghi chú về (e):** nếu `min_decryption_version` đã > 1 từ lần chạy trước, bản ghi tạo mới vẫn ở version mới nhất nên luồng bình thường không ảnh hưởng; nhưng cảnh T08 cần bắt đầu từ một bản ghi ở version hiện hành. Muốn trạng thái hoàn toàn sạch thì lặp lại (a).

**Chuẩn bị màn hình:** 3 cửa sổ PowerShell đặt cạnh nhau (SV3 / SV2 / SV1), font ≥ 16, nền sáng. Cửa sổ SV2 để sẵn ở thư mục gốc repo. Tắt thông báo Windows. Mở sẵn `docs/report/bao-cao-ky-thuat.pdf` ở trang bảng benchmark và `docs/evidence/T06_T08_T15_2026-11-11.md`; SV1 mở thêm `docs/evidence/T13_2026-11-16.md` cho cảnh TLS.

**Phương án lỗi tổng:** nếu stack không dựng được trước giờ demo, chuyển sang trình chiếu biên bản `docs/evidence/*.md` + `bench/results/*_summary.json` và nói thẳng "đây là log đã ghi, không phải chạy trực tiếp". Không giả vờ chạy live.

## 3. Kịch bản theo phút

| Phút | Nội dung | Người dẫn | Lệnh / cảnh | Kết quả phải thấy |
|---|---|---|---|---|
| 0–2 | Vấn đề và kiến trúc: mã hóa dữ liệu là chưa đủ nếu khóa và secret nằm cùng chỗ với dữ liệu. Sơ đồ client → nginx (TLS) → API (2 worker) → Vault (KEK, HTTP nội bộ) → PostgreSQL (ssl=on, ciphertext + DEK bọc). Giới thiệu 3 thành viên và phần việc | SV3 | `docker compose ps` | api/postgres/vault/nginx healthy; `vault-init`/`pgcerts` exit 0; chỉ vào cột STATUS |
| 2–4 | Luồng bình thường: tạo bản ghi, đọc lại, rồi mở DB cho thấy **chỉ có ciphertext** | SV2 | `POST /records` → `GET /records/{id}` → `psql` | HTTP 201/200; bảng chỉ có `ciphertext`, `nonce`, `encrypted_dek`, `kek_version` |
| 4–5 | Không có plaintext ở cả 4 vị trí: bảng, `pg_dump`, log/thư mục app, image | SV2 | T02 (4 lệnh probe) | cả 4 đều `0` / không dòng nào |
| 5–7 | **Tình huống lỗi 1:** sửa 1 byte ciphertext → từ chối; tráo payload giữa 2 bản ghi (AAD) → từ chối | SV2 | T03 rồi T04 | HTTP **503**; audit `record.read` / `failure` / `decrypt_failed` |
| 7–9 | **Least privilege + tách nhiệm vụ:** ma trận quyền AppRole, rồi thử xoay KEK bằng danh tính ứng dụng | SV2 | T06: `check_approle_privileges.py`, `prove_rotate_forbidden.py`, `POST /admin/rotation/transit-key` | 9/9 `PASS` exit 0; rotate → **403** |
| 9–12 | **Vòng đời khóa (trọng tâm đề tài):** xoay KEK → đọc lại bản ghi cũ → rewrap DEK → đặt `min_decryption_version` → ciphertext version cũ bị chặn | SV2 dẫn lệnh, SV3 giải thích vì sao thứ tự này | T08 đủ 7 bước | `kek_version` 1→2; prefix `vault:v1:`→`vault:v2:`; v1 bị **400**; bản ghi đã rewrap vẫn 200 |
| 12–14 | **Tình huống lỗi 2:** thu hồi lease credential DB → credential chết ngay; SecretID dùng lại bị từ chối | SV3 | T10 + `prove_secret_id_reuse.py` | trước revoke: `SELECT current_user` OK; sau revoke: `FATAL: role ... does not exist` (hoặc `password authentication failed`, tùy bản ghi lease); reuse → `PASS` |
| 14–16 | **TLS và at rest** — TLS ĐẠT 16/11; at-rest cấp volume risk-accepted (xem mục 4) | SV1 | `curl.exe -k https://...` / `openssl s_client` / `SHOW ssl;` | xem mục 4 |
| 16–18 | Số liệu: bảng p50/p95/p99 A vs D-lab, **H1 bị bác bỏ**, trần ~110 RPS, sụp ở 100 VUs, H2 đạt | SV3 | `python bench/analyze.py "bench/results/*.csv.gz"`; mở Hình 4 | overhead +122,21% / +131,21% (gộp 5 lần/mức); D-lab 100 VUs lỗi tối đa ≈61% — số liệu D-lab 31/10–11/11 (HTTP, 1 worker/pool 5+10); phiên đo mới qua TLS chưa có biên bản |
| 18–20 | DevSecOps và kết luận: CI chặn secret, ruleset chặn push thẳng, D-05/D-08 đã đóng (15/11), T13 đạt phần TLS (16/11) + at-rest risk-accepted, thẻ `v0.9.0-rc1`, hướng hoàn thiện | SV3 | `git log --oneline --graph -15`; `git shortlog -sne --all`; ảnh ruleset | 2 job CI xanh; 3 tác giả; tag `v0.9.0-rc1` |

Tổng: 20 phút. Nếu cần rút còn 15 phút: bỏ cảnh T04 (phút 5–7 chỉ giữ T03), rút T02 còn 2 vị trí (bảng + `pg_dump`), và gộp phút 18–20 vào 16–18.

## 4. Cảnh phút 14–16: TLS đã đạt, at-rest risk-accepted

**Phương án A — mặc định (TLS đã nghiệm thu 16/11/2026, `docs/evidence/T13_2026-11-16.md`):**

```powershell
curl.exe -k https://localhost:8200/v1/sys/health
curl.exe -k https://localhost:8443/health
docker compose exec -T postgres psql -U postgres -d encryption_db -c "SHOW ssl;"
```

```bash
# Git Bash — xem protocol/cipher thật của biên TLS
MSYS_NO_PATHCONV=1 openssl s_client -connect localhost:8443 -servername localhost -tls1_2 </dev/null
MSYS_NO_PATHCONV=1 openssl s_client -connect localhost:8443 -servername localhost -tls1_3 </dev/null
```

Phải thấy: Vault trả JSON có `"initialized":true` qua nginx, API trả 200 `{"status":"ok"}`, `SHOW ssl;` = `on`, `s_client` ra TLSv1.2 (ECDHE-RSA-AES128-GCM-SHA256) và TLSv1.3 (TLS_AES_256_GCM_SHA384). `Verify return code: 21` là đúng kỳ vọng lab: CA tự ký chưa nằm trong trust store của máy.

SV1 giải thích:
- nginx 1.27-alpine là TLS terminator cho cả ba ranh giới: 8200→vault:8200, 8443→api:8000, 8444→baseline:8001; TLSv1.2/1.3, cipher ECDHE.
- Vault vẫn HTTP **nội bộ** trong network Docker — chủ đích lab (D-04); TLS chỉ ở biên ngoài. Biến thể production-intent dùng TLS native (`infrastructure/vault/config/vault.hcl`) nhưng chưa nghiệm thu.
- Chứng chỉ tự ký sinh bởi `infrastructure/certs/gen-certs.sh` (CA riêng, SAN localhost/nginx/api/127.0.0.1), nằm trong `infrastructure/certs/out/` (gitignore). PostgreSQL đọc cert/key từ named volume `pgcerts` (container one-shot copy + chmod 600 + chown 70:70 vì bind mount Windows không giữ permission key).
- At-rest cấp volume: BitLocker Off (probe UAC 16/11), **risk-accepted bằng văn bản**: không tự bật vì cần admin + recovery key, rủi ro khóa máy; dữ liệu vẫn được bảo vệ ở cấp ứng dụng (envelope encryption, ciphertext trong DB) và trên đường truyền (TLS). Không đo cấu hình C; điều kiện đóng là bật BitLocker cho ổ chứa VHDX của Docker hoặc chuyển PostgreSQL sang volume LUKS rồi đo lại C.

**Phương án B — dự phòng khi stack TLS không dựng được trước giờ demo:**

Chuyển sang trình chiếu biên bản `docs/evidence/T13_2026-11-16.md` + `bench/results/*_summary.json` và nói thẳng "đây là log đã ghi, không phải chạy trực tiếp". Không giả vờ chạy live. Nếu bị hỏi vì sao chưa bật BitLocker, trả lời đúng mục risk-accepted ở trên, không tuyên bố at-rest cấp volume đã đạt.

SV3 không được dẫn `infrastructure/docker-compose.yml` như bằng chứng TLS đã nghiệm thu: biến thể production-intent này đã sửa để chạy độc lập nhưng chưa nghiệm thu (T13 nghiệm thu trên stack gốc). Ghi chú lịch sử: PR #7 từng có tiêu đề nhắc TLS nhưng nội dung file là dev mode không TLS — điểm đã được ghi nhận công khai trong báo cáo.

## 5. Lệnh chi tiết cho từng cảnh (copy-paste được)

Tất cả lệnh dưới đây giả định đã chạy mục 2(b)–(b2) để có `$API` (`https://127.0.0.1:8443`), `$Headers`, `$AdminHeaders` và CA lab đã được tin trong store người dùng. Nếu không tin CA, thay các lệnh `Invoke-RestMethod` bằng `curl.exe -k` tương đương (truyền `-H "X-API-Key: ..."`).

### 5.1. Phút 2–4 — luồng bình thường (SV2)

```powershell
$r = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "demo_phone"; value = "0901234567" } | ConvertTo-Json)
$r.id
(Invoke-RestMethod -Uri "$API/records/$($r.id)" -Headers $Headers).value

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT record_type, octet_length(ciphertext) AS ct_bytes, octet_length(nonce) AS nonce_bytes,
          left(encrypted_dek, 10) AS dek_prefix, kek_version
   FROM sensitive_records WHERE id = '$($r.id)';"
```

Câu chốt khi thầy hỏi "vì sao không lưu khóa trong DB?": DEK nằm trong DB nhưng **đã bị bọc bởi KEK chỉ tồn tại trong Vault**; tách được nơi lưu dữ liệu và nơi giữ quyền giải mã. AES-256-GCM cho cả confidentiality và integrity.

### 5.2. Phút 4–5 — T02 probe (SV2)

```powershell
$TestValue = "t02-demo-0901234567"
$t = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "plaintext_probe"; value = $TestValue } | ConvertTo-Json)

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT count(*) AS plaintext_hits FROM sensitive_records
   WHERE encode(ciphertext, 'escape') LIKE '%$TestValue%' OR encrypted_dek LIKE '%$TestValue%';"

docker compose exec -T postgres sh -c `
  "pg_dump -U postgres -d encryption_db | grep -a -c '$TestValue' || true"

docker compose exec -T api sh -c `
  "grep -R -a '$TestValue' /app /tmp 2>/dev/null | head -n 5 || true"

docker run --rm detai20-api:local sh -c `
  "grep -R -a '$TestValue' /app 2>/dev/null | head -n 5 || true"

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "DELETE FROM sensitive_records WHERE id = '$($t.id)';"
```

Dùng chuỗi `t02-demo-...` chứ không dùng `0901234567` trần, vì giá trị đó có trong fixture của unit test → dễ báo nhầm.

### 5.3. Phút 5–7 — T03 và T04 (SV2)

```powershell
# T03: sửa 1 byte ciphertext
$x = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "tamper_test"; value = "tamper-0901234567" } | ConvertTo-Json)

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "UPDATE sensitive_records SET ciphertext = set_byte(ciphertext, 0, (get_byte(ciphertext, 0) # 1))
   WHERE id = '$($x.id)';"

try { Invoke-RestMethod -Uri "$API/records/$($x.id)" -Headers $Headers; "UNEXPECTED: decrypt succeeded" }
catch { "HTTP status: $($_.Exception.Response.StatusCode.value__)" }

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT event_type, outcome, details FROM audit_events
   WHERE record_id = '$($x.id)' ORDER BY id DESC LIMIT 3;"

# T04: tráo payload giữa hai bản ghi (AAD binding)
$a = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "aad_a"; value = "value-a" } | ConvertTo-Json)
$b = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "aad_b"; value = "value-b" } | ConvertTo-Json)

docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "UPDATE sensitive_records b
   SET ciphertext = a.ciphertext, nonce = a.nonce, encrypted_dek = a.encrypted_dek,
       kek_name = a.kek_name, kek_version = a.kek_version
   FROM sensitive_records a WHERE b.id = '$($b.id)' AND a.id = '$($a.id)';"

try { Invoke-RestMethod -Uri "$API/records/$($b.id)" -Headers $Headers; "UNEXPECTED: swapped payload decrypted" }
catch { "HTTP status: $($_.Exception.Response.StatusCode.value__)" }
```

Câu chốt: AAD là `record_id:record_type` nên ciphertext hợp lệ của bản ghi A vẫn bị từ chối khi gắn sang bản ghi B. Trả **503** thay vì 500 là chủ ý: lỗi phía hạ tầng giải mã, không phải lỗi client.

### 5.4. Phút 7–9 — T06 (SV2)

```powershell
docker compose exec -T api python scripts/check_approle_privileges.py
docker compose exec -T api python scripts/prove_rotate_forbidden.py

try { Invoke-RestMethod -Method Post -Uri "$API/admin/rotation/transit-key" -Headers $AdminHeaders }
catch { "HTTP status: $($_.Exception.Response.StatusCode.value__)" }
```

Câu chốt: đây là **separation of duties** — ứng dụng dùng khóa nhưng không quản trị khóa. Endpoint admin vẫn trả 403 vì nó dùng AppRole của ứng dụng; muốn xoay phải dùng danh tính operator (`vault-init`). Kể cả admin key đúng cũng không vượt được policy Vault.

### 5.5. Phút 9–12 — T08 đủ 7 bước (SV2 chạy, SV3 giải thích)

```powershell
# 1. Bản ghi ở version hiện hành
$r = Invoke-RestMethod -Method Post -Uri "$API/records" -Headers $Headers `
  -Body (@{ record_type = "rotation_test"; value = "secret-phone-0901234567" } | ConvertTo-Json)
$id = $r.id
(Invoke-RestMethod -Uri "$API/records/$id/metadata" -Headers $Headers).kek_version
$oldDek = docker compose exec -T postgres psql -U postgres -d encryption_db -tA -c `
  "SELECT encrypted_dek FROM sensitive_records WHERE id = '$id';"

# 2. Operator xoay KEK
docker compose run --rm --no-deps --entrypoint python vault-init scripts/rotate_transit_key.py

# 3. Vẫn đọc được bản ghi cũ (tương thích ngược)
(Invoke-RestMethod -Uri "$API/records/$id" -Headers $Headers).value

# 4. Workload rewrap DEK — không giải mã payload
docker compose exec -T api python scripts/rewrap_dek.py

# 5. DB đã sang version mới
docker compose exec -T postgres psql -U postgres -d encryption_db -c `
  "SELECT id, kek_version, left(encrypted_dek, 12) FROM sensitive_records WHERE id = '$id';"
(Invoke-RestMethod -Uri "$API/records/$id" -Headers $Headers).value

# 6. Operator chặn version cũ
docker compose run --rm --no-deps --entrypoint python vault-init scripts/set_min_decryption_version.py 2

# 7a. Ciphertext v1 bị từ chối
docker compose exec -T vault vault write transit/decrypt/app-data-key ciphertext="$oldDek"
# 7b. Bản ghi đã rewrap vẫn đọc được
(Invoke-RestMethod -Uri "$API/records/$id" -Headers $Headers).value
```

Câu chốt về **thứ tự**: xoay KEK chỉ tăng version và giữ tương thích ngược; rewrap chuyển lớp bọc DEK sang version mới **mà không đụng tới payload**; chỉ sau khi rewrap xong mới đặt `min_decryption_version`. Đặt min version trước khi rewrap sẽ làm bản ghi chưa rewrap không giải mã được — đó là lý do `bench/README.md` cấm đặt min version trong lúc k6 đang chạy.

Lưu ý câu chữ lỗi: Vault 1.20 trả `ciphertext or signature version is disallowed by policy (too old)`. Biên bản 05/11 ghi một thông điệp dài hơn; cùng cơ chế, khác phiên bản. Nếu thầy hỏi, trả lời đúng chuỗi đang thấy trên màn hình.

### 5.6. Phút 12–14 — T10 (SV3)

```powershell
$lease = docker compose exec -T vault vault read -format=json database/creds/app-role | ConvertFrom-Json
$lease.data.username; $lease.lease_id; $lease.lease_duration

docker compose exec -T -e PGPASSWORD=$lease.data.password postgres `
  psql -h 127.0.0.1 -U $lease.data.username -d encryption_db -c "SELECT current_user;"

docker compose exec -T vault vault lease renew -increment=60s $lease.lease_id
docker compose exec -T vault vault lease revoke $lease.lease_id

docker compose exec -T -e PGPASSWORD=$lease.data.password postgres `
  psql -h 127.0.0.1 -U $lease.data.username -d encryption_db -c "SELECT 1;"

docker compose exec -T api python scripts/prove_secret_id_reuse.py
```

Câu chốt: credential DB là **dynamic secret** có lease; thu hồi là chết ngay, không cần đổi mật khẩu tĩnh hay restart app. SecretID của AppRole cũng vậy: `ttl=10m`, `num_uses=1`, dùng lại bị Vault từ chối.

### 5.7. Phút 16–20 — số liệu và DevSecOps (SV3)

```powershell
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python bench/analyze.py "bench/results/*.csv.gz"

git log --oneline --graph -15
git shortlog -sne --all
git tag --list
```

Điểm phải nói ra, không né:

- **H1 bị bác bỏ:** overhead p95 **+122,21%** ở 10 VUs và **+131,21%** ở 50 VUs (gộp 5 lần/mức sau bổ sung 11/11; riêng phiên 31/10 là +124,91%), ngưỡng đề ra là ≤30%. Nguyên nhân: mỗi request tạo gọi `transit/datakey`, mỗi request đọc gọi `transit/decrypt`; 70% tải là tạo; thời điểm đo (31/10–11/11) API chạy **một Uvicorn worker, pool 5+10** — cấu hình cũ. Từ 15/11 (D-08 đóng) là **2 worker, pool 20+20**, connection không giữ khi gọi Vault; số liệu trên chưa phản ánh cấu hình mới.
- **Trần ~110 RPS:** D-lab chỉ tăng 106,87 → 110,55 RPS khi tải 10 → 50 VUs nhưng p95 tăng 123 → 839 ms. Ở 100 VUs log ghi `QueuePool limit of size 5 overflow 10 reached` (pool cũ 5+10; hiện tại 20+20) và p95 xấp xỉ timeout 60 s của k6 → **sụp bão hòa**, không dùng để tính H1.
- **H2 đạt:** T09 0% lỗi ở 20 VUs/1 phút; E-lab 3 lần 50 VUs/3 phút, 6 thao tác xoay đều HTTP 200, 0,00% lỗi.
- **`D-lab` không phải `D`:** các số liệu trên đo 31/10–11/11 qua HTTP, trước khi có TLS, nên là **cận dưới** của chi phí mã hóa. Từ 16/11 stack đã có TLS (k6 chạy `insecureSkipTLSVerify: true` qua 8443, baseline qua 8444); kết quả B/D mới chỉ được đưa vào khi có biên bản. Cấu hình C không đo (BitLocker Off, risk-accepted).
- **D-09:** lần tái lập 11/11 phát hiện `vault-init` exit 1 do truyền `secret_id_ttl`/`secret_id_num_uses` vào `generate_secret_id` (hvac không nhận; hai tham số đó thuộc cấp role). Đã sửa + regression test. Bài học: biên bản "ĐẠT" phải tái lập được từ `main` sạch.
- Thẻ **`v0.9.0-rc1`**, không phải `v1.0.0`: D-05/D-08 đã đóng (15/11) và T13 đã đạt phần TLS (16/11), nhưng at-rest cấp volume mới risk-accepted, T14 chưa đủ B/C/D đầy đủ và D' chưa đo benchmark.

## 6. Chuẩn bị phản biện — mỗi người tự trả lời phần mình

| Người | Câu hỏi dự kiến | Ý chính phải trả lời được |
|---|---|---|
| SV2 | Vì sao dùng envelope encryption thay vì mã hóa thẳng bằng KEK trong Vault? | Giảm gọi Vault cho payload lớn, DEK cục bộ theo bản ghi, xoay KEK không phải mã hóa lại toàn bộ dữ liệu |
| SV2 | AAD gồm những gì và chống được tấn công nào? | `record_id:record_type`; chống tráo ciphertext giữa bản ghi (T04) |
| SV2 | Vì sao `rewrap` không cần giải mã payload? | Vault bọc lại DEK bằng KEK version mới; payload vẫn mã hóa bằng DEK cũ không đổi |
| SV2 | SecretID `num_uses=1` gây bất tiện gì khi vận hành? | Mỗi lần restart API phải cấp SecretID mới bằng operator (`issue_workload_secret.py`) — đánh đổi có chủ ý |
| SV1 | T13 đạt phần TLS thế nào, vì sao at-rest chỉ risk-accepted? | nginx terminator 3 cổng (8200/8443/8444), TLS 1.2/1.3, PG ssl=on; Vault HTTP nội bộ là chủ đích D-04; BitLocker Off không tự bật (rủi ro khóa máy), điều kiện đóng: bật BitLocker/LUKS rồi đo lại C |
| SV1 | `vault_admin` bỏ SUPERUSER và `SET FALSE` chặn được gì? | D-05 đã đóng: `LOGIN CREATEROLE NOINHERIT`, grant `app_writer ... WITH ADMIN TRUE, SET FALSE` chặn leo thang qua `SET ROLE`; kiểm chứng 15/11, fix nằm trong PR #14 (worktree đã cherry-pick) |
| SV3 | Vì sao H1 bị bác bỏ mà vẫn nộp? | Kết quả đo trung thực có giá trị hơn kết quả đẹp; đã chỉ ra nguyên nhân, sửa D-08 (2 worker, pool 20+20) và cấu hình D' cần đo |
| SV3 | CI chặn được những gì, không chặn được gì? | Gitleaks quét toàn bộ lịch sử (`--all`) + unit test; không chặn được secret đã encode tinh vi hoặc lộ qua kênh khác |
| SV3 | Vì sao ruleset cần 1 approval và trưởng nhóm không tự approve được? | Tách người viết và người duyệt; PR #5 từng bị chặn merge dù CI xanh |

## 7. Dọn tài nguyên sau demo (SV1)

```powershell
docker compose down -v
docker rm -f detai20-baseline 2>$null
# Gỡ CA lab khỏi store người dùng (đã tin ở mục 2(b2))
Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -eq "CN=UTH Lab CA" } | Remove-Item
docker volume ls
docker ps -a
```

Báo cáo ước tính chi phí lab = 0 (máy cá nhân, image mã nguồn mở); mục 5.3 của báo cáo liệt kê các thành phần phải tính nếu chuyển lên cloud.

## 8. Nhật ký rehearsal (điền sau mỗi lần chạy thử)

| Lần | Ngày | Tổng thời gian | Cảnh bị trễ | Sự cố | Đã sửa |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |

Quy tắc: rehearsal 1 bấm giờ toàn bộ; rehearsal 2 chạy đúng thứ tự và **cố tình gây một lỗi** (tắt Vault giữa chừng) để tập phương án dự phòng. Nếu tổng thời gian vượt 20 phút, cắt theo hướng dẫn ở cuối mục 3.

### 8.1. Dry-run kỹ thuật 14/11/2026 (SV3, chạy thật từng cảnh, chưa bấm giờ người)

Chạy thật toàn bộ lệnh mục 5.1–5.7 trên stack dựng sạch (`down -v` → `up -d --build`, `vault-init` exit 0, KEK bắt đầu v1/min1) bằng một script PowerShell chạy Bypass phạm vi tiến trình. Tổng thời gian lệnh **54,9s** (không gồm thời gian dẫn/giải thích của người). Kết quả từng cảnh:

| Cảnh | Thời gian | Kết quả quan sát | Đạt kỳ vọng |
|---|---:|---|---|
| 5.1 luồng bình thường | 0,5s | POST 201 / GET 200; `ct_bytes=26`, `nonce_bytes=12`, `dek_prefix=vault:v1:`, `kek_version=1` | Có |
| 5.2 T02 probe | 2,2s | bảng=0, pg_dump=0, app/tmp=rỗng, image=rỗng | Có |
| 5.3 T03+T04 | 0,7s | cả hai trả **503** | Có |
| 5.4 T06 | 1,6s | checker PASS exit 0; `prove_rotate_forbidden` PASS; admin rotate **403** | Có |
| 5.5 T08 7 bước | 5,2s | kek 1→2; đọc bản ghi cũ OK; rewrap 5/5; min=2; ciphertext v1 bị chặn; bản ghi rewrap đọc OK | Có |
| 5.6 T10 | 2,5s | lease `duration=3600`; trước revoke `current_user` OK; sau revoke `FATAL: role ... does not exist`; reuse SecretID PASS | Có |
| 5.7 số liệu + git | 41,9s | overhead +122,21%/+131,21%; 3 email tác giả; tag `v0.9.0-rc1`; HEAD `c69d124` | Có |

Hai hiệu chỉnh rút ra từ dry-run (đã sửa trong kịch bản này):

1. Overhead 50 VUs phải đọc **+131,21%** (gộp 5 lần/mức sau bổ sung 11/11), không phải +124,91% (con số riêng phiên 31/10). Lỗi tối đa D-lab 100 VUs là **≈61%**, không phải ~50%.
2. Sau `vault lease revoke`, thông điệp thật trên PostgreSQL bản hiện tại là `FATAL: role ... does not exist` (role động bị xóa), không nhất thiết `password authentication failed`; kịch bản và test-plan chấp nhận cả hai.

Việc còn lại trước demo: hai lần rehearsal **bấm giờ có người dẫn** (bảng mục 8) và chốt ngày demo mới; dry-run này chỉ chứng minh lệnh chạy đúng, không thay thế rehearsal người.