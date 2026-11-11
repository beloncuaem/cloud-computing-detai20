# Benchmark — k6

Thư mục này chứa kịch bản đo và kết quả thô cho Chương 4. Kết quả phải đo trên cùng một máy, cùng dữ liệu và cùng tài nguyên container; ghi lại phiên bản Docker, Vault, PostgreSQL, k6 và cấu hình CPU/RAM.

## 1. Kịch bản

`k6/mixed.js` mô phỏng 70% ghi và 30% đọc:

- Ghi: `POST /records` với `record_type = bench_phone`, giá trị tổng hợp `090xxxxxxx`.
- Đọc: `GET /records/{id}` của một bản ghi được tạo trong `setup()`.
- Header `X-API-Key` lấy từ biến môi trường `API_KEY`.
- `SLEEP` (giây, mặc định `0`) giãn nhịp sau mỗi vòng lặp. Benchmark hiệu năng để mặc định; T16 dùng `SLEEP>0` để tải nền không vượt ngưỡng cảnh báo.

Chạy qua Docker để không cần cài k6 trên máy:

```powershell
New-Item -ItemType Directory -Force bench/results | Out-Null

# Warm-up 60 giây, không ghi CSV
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=$env:API_KEY `
  -e VUS=10 -e DURATION=1m bench/k6/mixed.js

# Đo chính thức (ví dụ D-lab, 50 VUs, lần 1)
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=$env:API_KEY `
  -e VUS=50 -e DURATION=3m `
  --out csv=bench/results/D-lab_50_run1.csv bench/k6/mixed.js
```

Nếu API chạy native trên Windows (không qua Docker), dùng `BASE_URL=http://127.0.0.1:8000`; nếu k6 chạy trong container thì `host.docker.internal` trỏ về máy host trên Docker Desktop.

Với T16 (kiểm tra false positive của cảnh báo giải mã), chạy tải nền chậm trong 10 phút: `VUS=5`, `SLEEP=2`, `DURATION=10m`. Lượng decrypt ~90/phút, thấp hơn ngưỡng 200/phút. Nếu chạy k6 trong cùng network Compose thì dùng `BASE_URL=http://api:8000` thay cho `host.docker.internal`.

## 2. Ma trận cấu hình

| Mã | Cấu hình | Ghi chú |
|---|---|---|
| A | Plaintext, HTTP | Baseline `bench/baseline/server.py`, cổng 8001; chỉ dùng benchmark, không merge vào app |
| B | TLS | Chờ SV1 cấu hình TLS |
| C | TLS + mã hóa volume | Chờ SV1 + BitLocker/volume encryption |
| D | TLS + envelope encryption | Đo được phần envelope; nếu chưa có TLS thì ghi là `D-lab` |
| E | D + rotation | Kết quả hiện tại là `E-lab` (envelope qua HTTP + xoay DB credential/KEK) |
| D' | D sau tối ưu | Sau khi SV2 cache DEK/giảm gọi Vault |

Không được ghi `D-lab` thành `D` trong báo cáo. Mỗi cấu hình chạy tối thiểu 5 lần; mỗi lần 3–5 phút; lặp lại ở 10, 50, 100 VUs. Khởi động lại stack trước mỗi cấu hình.

### 2.1. Baseline plaintext (cấu hình A) — chỉ dùng cho benchmark

`bench/baseline/server.py` là một API tối giản, **cố ý lưu plaintext**, dùng để đo H1. Nó không thuộc ứng dụng và không được deploy. API này mô phỏng cùng khối lượng DB với target: mỗi POST ghi 1 bản ghi + 1 audit trong một transaction; mỗi GET đọc bản ghi + ghi 1 audit.

```powershell
# Chạy trên network của compose, dùng image API (đã có FastAPI/psycopg)
docker run -d --name detai20-baseline --network detai20_default `
  -p 8001:8001 -v "${PWD}/bench/baseline:/baseline:ro" -w /baseline `
  -e BASELINE_DB_DSN="postgresql://postgres:local_demo_postgres_password@postgres:5432/encryption_db" `
  -e API_KEY="$env:API_KEY" `
  detai20-api:local uvicorn server:app --host 0.0.0.0 --port 8001

# Kiểm tra
curl.exe -s http://127.0.0.1:8001/ready

# Đo: dùng cùng mixed.js, chỉ đổi BASE_URL và tên file A_...
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8001 `
  -e API_KEY=$env:API_KEY `
  -e VUS=50 -e DURATION=3m `
  --out csv=bench/results/A_50_run1.csv bench/k6/mixed.js

docker rm -f detai20-baseline
```

Bảng `bench_plaintext_records`/`bench_plaintext_audit` được tạo tự động trong `encryption_db`; chúng chỉ phục vụ đo đạc, không phải dữ liệu của ứng dụng. Ghi rõ trong báo cáo đây là baseline dựng riêng, không merge vào `main`.

## 3. Đặt tên và phân tích

Mẫu tên: `<config>_<vus>_run<N>.csv`, ví dụ `D-lab_50_run3.csv`. Khi lưu vào Git, nén lossless thành `.csv.gz` để giảm dung lượng (một lượt 3 phút có thể tạo 100–300 MB CSV thô; `.gz` thường còn 3–10%). `analyze.py` đọc trực tiếp file `.csv.gz`.

Mỗi lượt nên kèm `--summary-export=bench/results/<config>_<vus>_run<N>_summary.json` (vài KB) để đối chiếu nhanh p50/p95/p99 và error rate kể cả khi CSV bị lược bớt.

```powershell
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python bench/analyze.py "bench/results/*.csv.gz"
```

Script in bảng p50/p95/p99, trung vị p95 theo cấu hình/VUs và overhead so với baseline A nếu có. Đây là số liệu để điền bảng Chương 4, không thay thế việc lưu dữ liệu thô.

## 4. Đo trong lúc rotation (E)

```powershell
# Terminal 1: chạy k6 50 VUs trong 3 phút
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=$env:API_KEY `
  -e VUS=50 -e DURATION=3m `
  --out csv=bench/results/E-lab_50_run1.csv bench/k6/mixed.js

# Terminal 2: sau khi k6 đã chạy khoảng 60 giây
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/admin/rotation/database" `
  -Headers @{ "X-Admin-Key" = $env:ADMIN_API_KEY }
docker compose run --rm --no-deps --entrypoint python vault-init scripts/rotate_transit_key.py
```

Ghi lại thời điểm bắt đầu/kết thúc rotation và cửa sổ lỗi (nếu có). H2 yêu cầu tỷ lệ lỗi dưới 0,1% trong cửa sổ này. API phải chạy với `USE_VAULT_DB_CREDS=true` để phép xoay credential DB có ý nghĩa. Xoay KEK trong cửa sổ đo bằng danh tính operator. Không gọi `POST /admin/rotation/transit-key` để xoay: endpoint đó dùng AppRole của ứng dụng và phải trả 403. Không đặt `min_decryption_version` trong lúc k6 còn chạy, vì bản ghi chưa rewrap sẽ bị từ chối giải mã.

## 5. Bằng chứng cần lưu

- CSV thô nén `.csv.gz` trong `bench/results/`; kèm `_summary.json` cho từng lượt. Commit CSV + summary (dữ liệu tổng hợp giả), không commit file `.log` và không commit secret.
- Ảnh summary k6 của mỗi cấu hình.
- Ảnh thời điểm rotation và kết quả API rotation.
- Bảng tổng hợp do `analyze.py` in ra.
- Mô tả máy: CPU, RAM, phiên bản Docker/Vault/PostgreSQL/k6.
- Nêu rõ giới hạn: máy cá nhân, không suy diễn sang production; `D-lab` khác `D` nếu thiếu TLS.
