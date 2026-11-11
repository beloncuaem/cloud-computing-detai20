# Kịch bản trình diễn trực tiếp — Đề tài 20

**Thời lượng:** 15–20 phút (mục tiêu 18 phút, chừa 2 phút dự phòng)
**Hình thức:** trình diễn trực tiếp trước giảng viên, **không dùng video**. Đề bài cho phép "Video demo 8–12 phút **hoặc** trình diễn trực tiếp 15–20 phút, có kịch bản và phân công rõ"; nhóm chọn phương án trực tiếp.
**Phiên bản áp dụng:** `main` sau PR #9, thẻ nghiệm thu `v0.9.0-rc1`.
**Nguyên tắc:** mỗi người dẫn phần của mình, chạy lệnh thật trên máy thật, và **tự trả lời được quyết định kỹ thuật** trong phần phản biện. Ảnh chụp chỉ bổ trợ; log và số liệu mới là bằng chứng.

## 1. Phân công

| Ký hiệu | Thành viên | GitHub | Dẫn cảnh |
|---|---|---|---|
| **SV3** | Bùi Ngô Anh Quang (nhóm trưởng) | `beloncuaem` | Mở đầu, kiến trúc, T10, số liệu benchmark, CI/ruleset, kết luận |
| **SV2** | Nguyễn Minh Hiếu | `Hieu0408` | Luồng mã hóa bình thường, T02, T03/T04, T06, T08 |
| **SV1** | SV1 | `hothienphu` | Hạ tầng, T13 (hoặc cảnh "vì sao chưa đạt"), dọn tài nguyên |

## 2. Chuẩn bị trước giờ demo (T−30 phút, SV3 điều phối)

Đây là phần **bắt buộc**, vì hai ràng buộc bảo mật của chính đồ án có thể làm demo hỏng nếu bỏ qua:

1. **API key chỉ đọc từ môi trường (PR #9).** Thiếu `API_KEY` hoặc `ADMIN_API_KEY` thì `docker compose` thoát ngay và API từ chối khởi động.
2. **SecretID của workload chỉ dùng 1 lần và hết hạn sau 10 phút (D-02).** Mỗi lần API khởi động lại phải cấp SecretID mới bằng danh tính operator, nếu không API sẽ không đăng nhập được Vault.

```powershell
# (a) Dựng stack sạch — chạy trước, để kịp thời gian build
docker compose down -v
docker compose up -d --build
docker inspect detai20-vault-init-1 --format '{{.State.ExitCode}}'   # phải = 0
docker compose ps                                                   # api/postgres/vault đều healthy

# (b) Nạp khóa vào phiên PowerShell (không in giá trị khóa ra màn hình)
Get-Content .env | ForEach-Object { if ($_ -match '^([A-Z_]+)=(.*)$') { Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2] } }
$API = "http://127.0.0.1:8000"
$Headers = @{ "X-API-Key" = $env:API_KEY; "Content-Type" = "application/json" }
$AdminHeaders = @{ "X-Admin-Key" = $env:ADMIN_API_KEY }

# (c) Smoke test 9/9 — nếu hỏng ở đây thì KHÔNG demo, sửa trước
./scripts/smoke-test.ps1

# (d) Nếu API đã restart sau khi dựng: cấp SecretID mới rồi restart API
docker compose run --rm --no-deps --entrypoint python vault-init scripts/issue_workload_secret.py
docker compose restart api
# chờ api healthy rồi chạy lại smoke test

# (e) Kiểm tra trạng thái khóa trước khi demo T08
docker compose exec -T vault vault read -field=latest_version transit/keys/app-data-key
docker compose exec -T vault vault read -field=min_decryption_version transit/keys/app-data-key
```

**Ghi chú về (e):** nếu `min_decryption_version` đã > 1 từ lần chạy trước, bản ghi tạo mới vẫn ở version mới nhất nên luồng bình thường không ảnh hưởng; nhưng cảnh T08 cần bắt đầu từ một bản ghi ở version hiện hành. Muốn trạng thái hoàn toàn sạch thì lặp lại (a).

**Chuẩn bị màn hình:** 3 cửa sổ PowerShell đặt cạnh nhau (SV3 / SV2 / SV1), font ≥ 16, nền sáng. Cửa sổ SV2 để sẵn ở thư mục gốc repo. Tắt thông báo Windows. Mở sẵn `docs/report/bao-cao-ky-thuat.pdf` ở trang bảng benchmark và `docs/evidence/T06_T08_T15_2026-11-11.md`.

**Phương án lỗi tổng:** nếu stack không dựng được trước giờ demo, chuyển sang trình chiếu biên bản `docs/evidence/*.md` + `bench/results/*_summary.json` và nói thẳng "đây là log đã ghi, không phải chạy trực tiếp". Không giả vờ chạy live.

## 3. Kịch bản theo phút

| Phút | Nội dung | Người dẫn | Lệnh / cảnh | Kết quả phải thấy |
|---|---|---|---|---|
| 0–2 | Vấn đề và kiến trúc: mã hóa dữ liệu là chưa đủ nếu khóa và secret nằm cùng chỗ với dữ liệu. Sơ đồ client → API → Vault (KEK) → PostgreSQL (ciphertext + DEK bọc). Giới thiệu 3 thành viên và phần việc | SV3 | `docker compose ps` | 3 service healthy; chỉ vào cột STATUS |
| 2–4 | Luồng bình thường: tạo bản ghi, đọc lại, rồi mở DB cho thấy **chỉ có ciphertext** | SV2 | `POST /records` → `GET /records/{id}` → `psql` | HTTP 201/200; bảng chỉ có `ciphertext`, `nonce`, `encrypted_dek`, `kek_version` |
| 4–5 | Không có plaintext ở cả 4 vị trí: bảng, `pg_dump`, log/thư mục app, image | SV2 | T02 (4 lệnh probe) | cả 4 đều `0` / không dòng nào |
| 5–7 | **Tình huống lỗi 1:** sửa 1 byte ciphertext → từ chối; tráo payload giữa 2 bản ghi (AAD) → từ chối | SV2 | T03 rồi T04 | HTTP **503**; audit `record.read` / `failure` / `decrypt_failed` |
| 7–9 | **Least privilege + tách nhiệm vụ:** ma trận quyền AppRole, rồi thử xoay KEK bằng danh tính ứng dụng | SV2 | T06: `check_approle_privileges.py`, `prove_rotate_forbidden.py`, `POST /admin/rotation/transit-key` | 9/9 `PASS` exit 0; rotate → **403** |
| 9–12 | **Vòng đời khóa (trọng tâm đề tài):** xoay KEK → đọc lại bản ghi cũ → rewrap DEK → đặt `min_decryption_version` → ciphertext version cũ bị chặn | SV2 dẫn lệnh, SV3 giải thích vì sao thứ tự này | T08 đủ 7 bước | `kek_version` 1→2; prefix `vault:v1:`→`vault:v2:`; v1 bị **400**; bản ghi đã rewrap vẫn 200 |
| 12–14 | **Tình huống lỗi 2:** thu hồi lease credential DB → credential chết ngay; SecretID dùng lại bị từ chối | SV3 | T10 + `prove_secret_id_reuse.py` | trước revoke: `SELECT current_user` OK; sau revoke: `password authentication failed`; reuse → `PASS` |
| 14–16 | **TLS và at rest** — xem mục 4 bên dưới (hai phương án tùy SV1 có bàn giao hay không) | SV1 | `curl.exe -k https://...` / `SHOW ssl;` **hoặc** cảnh "vì sao chưa đạt" | xem mục 4 |
| 16–18 | Số liệu: bảng p50/p95/p99 A vs D-lab, **H1 bị bác bỏ**, trần ~110 RPS, sụp ở 100 VUs, H2 đạt | SV3 | `python bench/analyze.py "bench/results/*.csv.gz"`; mở Hình 4 | overhead +122,21% / +124,91%; D-lab 100 VUs lỗi ~50% |
| 18–20 | DevSecOps và kết luận: CI chặn secret, ruleset chặn push thẳng, defect công khai D-05/D-08/T13, thẻ `v0.9.0-rc1`, hướng hoàn thiện | SV3 | `git log --oneline --graph -15`; `git shortlog -sne --all`; ảnh ruleset | 2 job CI xanh; 3 tác giả; tag `v0.9.0-rc1` |

Tổng: 20 phút. Nếu cần rút còn 15 phút: bỏ cảnh T04 (phút 5–7 chỉ giữ T03), rút T02 còn 2 vị trí (bảng + `pg_dump`), và gộp phút 18–20 vào 16–18.

## 4. Cảnh phút 14–16: hai phương án, chọn theo thực tế

**Phương án A — SV1 đã bàn giao TLS (chỉ dùng khi chạy thật được):**

```powershell
curl.exe -k https://localhost:8200/v1/sys/health
curl.exe -k https://localhost:8443/health
docker compose exec -T postgres psql -U postgres -d encryption_db -c "SHOW ssl;"
```

Phải thấy: Vault trả JSON có `"initialized":true`, reverse proxy trả 200, `SHOW ssl;` = `on`. SV1 giải thích vì sao chọn TLS 1.2 trở lên, chứng chỉ lưu ở đâu, và vì sao Vault phải chuyển sang file storage.

**Phương án B — T13 CHƯA ĐẠT (mặc định, theo trạng thái `main` hiện nay):**

SV1 nói thẳng, không vòng vo, theo sườn:

1. "T13 trong kế hoạch kiểm thử yêu cầu TLS cho Vault/API/PostgreSQL và mã hóa volume. **Nhóm chưa đạt ca này.**"
2. Chỉ vào bằng chứng: `docker-compose.yml` trên `main` vẫn là Vault **dev mode**, `VAULT_DEV_ROOT_TOKEN_ID`, HTTP, không file storage, không reverse proxy; `docs/evidence/T13_partial_2026-10-31.md` ghi rõ phần đã làm và phần chưa.
3. Nêu rủi ro còn lại một cách cụ thể: API key và ciphertext đi qua HTTP nội bộ nên có thể bị nghe lén trong lab; dev mode mất container là mất khóa.
4. Nêu việc cần làm để đạt: Vault file storage + TLS 1.2+, reverse proxy 8443, PostgreSQL `ssl=on`, BitLocker/volume encryption, và đo lại cấu hình **B**/**C** trong ma trận benchmark.
5. Chốt: "Vì T13 chưa đạt và D-05/D-08 còn mở, nhóm gắn thẻ **`v0.9.0-rc1`**, không phải `v1.0.0`."

SV3 không được dẫn `infrastructure/docker-compose.yml` như bằng chứng TLS: PR #7 có tiêu đề nhắc TLS nhưng nội dung file là dev mode không TLS. Đây là điểm đã được ghi nhận công khai trong báo cáo.

## 5. Lệnh chi tiết cho từng cảnh (copy-paste được)

Tất cả lệnh dưới đây giả định đã chạy mục 2(b) để có `$API`, `$Headers`, `$AdminHeaders`.

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

- **H1 bị bác bỏ:** overhead p95 **+122,21%** ở 10 VUs và **+124,91%** ở 50 VUs, ngưỡng đề ra là ≤30%. Nguyên nhân: mỗi request tạo gọi `transit/datakey`, mỗi request đọc gọi `transit/decrypt`; 70% tải là tạo; API một Uvicorn worker, pool 5+10.
- **Trần ~110 RPS:** D-lab chỉ tăng 106,87 → 110,55 RPS khi tải 10 → 50 VUs nhưng p95 tăng 123 → 839 ms. Ở 100 VUs log ghi `QueuePool limit of size 5 overflow 10 reached` và p95 xấp xỉ timeout 60 s của k6 → **sụp bão hòa**, không dùng để tính H1.
- **H2 đạt:** T09 0% lỗi ở 20 VUs/1 phút; E-lab 3 lần 50 VUs/3 phút, 6 thao tác xoay đều HTTP 200, 0,00% lỗi.
- **`D-lab` không phải `D`:** chưa có TLS nên đây là **cận dưới** của chi phí mã hóa. Cấu hình B/C chưa đo vì chờ T13.
- **D-09:** lần tái lập 11/11 phát hiện `vault-init` exit 1 do truyền `secret_id_ttl`/`secret_id_num_uses` vào `generate_secret_id` (hvac không nhận; hai tham số đó thuộc cấp role). Đã sửa + regression test. Bài học: biên bản "ĐẠT" phải tái lập được từ `main` sạch.
- Thẻ **`v0.9.0-rc1`**, không phải `v1.0.0`, vì T13 chưa đạt và D-05/D-08 còn mở.

## 6. Chuẩn bị phản biện — mỗi người tự trả lời phần mình

| Người | Câu hỏi dự kiến | Ý chính phải trả lời được |
|---|---|---|
| SV2 | Vì sao dùng envelope encryption thay vì mã hóa thẳng bằng KEK trong Vault? | Giảm gọi Vault cho payload lớn, DEK cục bộ theo bản ghi, xoay KEK không phải mã hóa lại toàn bộ dữ liệu |
| SV2 | AAD gồm những gì và chống được tấn công nào? | `record_id:record_type`; chống tráo ciphertext giữa bản ghi (T04) |
| SV2 | Vì sao `rewrap` không cần giải mã payload? | Vault bọc lại DEK bằng KEK version mới; payload vẫn mã hóa bằng DEK cũ không đổi |
| SV2 | SecretID `num_uses=1` gây bất tiện gì khi vận hành? | Mỗi lần restart API phải cấp SecretID mới bằng operator (`issue_workload_secret.py`) — đánh đổi có chủ ý |
| SV1 | Vì sao T13 chưa đạt và cần gì để đạt? | Xem mục 4 phương án B; nói rõ dev mode/HTTP và các bước còn thiếu |
| SV1 | `vault_admin` SUPERUSER rủi ro gì? | D-05: leo thang quyền trong lab; production phải dùng role tối thiểu, tách quyền tạo role |
| SV3 | Vì sao H1 bị bác bỏ mà vẫn nộp? | Kết quả đo trung thực có giá trị hơn kết quả đẹp; đã chỉ ra nguyên nhân và cấu hình D' cần đo |
| SV3 | CI chặn được những gì, không chặn được gì? | Gitleaks quét toàn bộ lịch sử (`--all`) + unit test; không chặn được secret đã encode tinh vi hoặc lộ qua kênh khác |
| SV3 | Vì sao ruleset cần 1 approval và trưởng nhóm không tự approve được? | Tách người viết và người duyệt; PR #5 từng bị chặn merge dù CI xanh |

## 7. Dọn tài nguyên sau demo (SV1)

```powershell
docker compose down -v
docker rm -f detai20-baseline 2>$null
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